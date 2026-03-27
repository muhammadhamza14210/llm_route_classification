"""
Evaluates response quality on three dimensions:
    relevance     — does it address the query?
    completeness  — does it cover all parts?
    accuracy      — is the information correct?

Design decisions per architecture spec:
    - Runs on Small + Medium responses only (LLM eval)
    - Large responses: rule-based sanity check only
      (length + structure no LLM eval needed, too expensive)
    - Always uses the Small deployment (cheap, fast)
    - Returns composite quality_score = weighted avg of 3 dimensions
"""

import json
import re
import logging
from openai import AzureOpenAI
from routing.models import ModelTier
from response.models import QualityScores
from config.settings import settings

logger = logging.getLogger(__name__)

# Quality threshold — below this triggers escalation
QUALITY_THRESHOLD = 0.65

# Dimension weights for composite quality_score
_WEIGHTS = {
    "relevance":    0.40,   # most important — did it answer the question?
    "completeness": 0.35,   # did it cover everything asked?
    "accuracy":     0.25,   # is it correct? (hard to verify automatically)
}

def _build_eval_prompt(query: str, response: str) -> str:
    return f"""You are a strict response quality evaluator.

You MUST use the full range 0.0 to 1.0. Here are concrete score meanings:

relevance:
  0.2 = completely off topic
  0.4 = addresses topic but not the actual question
  0.6 = answers the question but misses key aspects
  0.8 = answers well with minor gaps
  1.0 = perfectly addresses exactly what was asked

completeness:
  0.2 = one line answer to a complex question
  0.4 = covers the surface, misses depth
  0.6 = covers main points, missing details
  0.8 = thorough, minor things missing
  1.0 = exhaustive coverage of all aspects

accuracy:
  0.2 = contains significant errors
  0.4 = mostly wrong or misleading
  0.6 = mostly correct, some errors
  0.8 = accurate with minor imprecisions
  1.0 = completely correct

Additional rules:
- A one sentence answer to a complex question = completeness 0.2-0.3
- A long answer to a simple question = completeness 0.9-1.0
- If you cannot verify accuracy due to domain complexity, score accuracy 0.7
- relevance and completeness should vary MORE than accuracy
- Do NOT cluster scores around 0.9

Respond with ONLY valid JSON:
{{
  "relevance": <float>,
  "completeness": <float>,
  "accuracy": <float>,
  "rationale": "<main weakness in one sentence>"
}}

Query:
\"\"\"
{query}
\"\"\"

Response:
\"\"\"
{response[:1500]}
\"\"\""""

def _parse_quality(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    return json.loads(cleaned)

def _length_penalty(query: str, response: str) -> float:
    """
    Penalise completeness if response is too short for a complex query.
    Simple queries (< 10 tokens) don't need long responses.
    Complex queries (> 10 tokens) that get short responses lose completeness.
    """
    query_tokens    = len(query.split())
    response_tokens = len(response.split())

    # Simple query — no penalty
    if query_tokens <= 10:
        return 1.0

    # Complex query with very short response — penalise
    ratio = response_tokens / max(query_tokens * 5, 50)
    return min(ratio, 1.0)


def _compute_quality_score(relevance: float, completeness: float, accuracy: float) -> float:
    total_weight = sum(_WEIGHTS.values())
    return (
        relevance    * _WEIGHTS["relevance"] +
        completeness * _WEIGHTS["completeness"] +
        accuracy     * _WEIGHTS["accuracy"]
    ) / total_weight


def _rule_based_check(response: str) -> QualityScores:
    """
    Sanity check for Large responses — no LLM call.
    Checks length and basic structure only.
    """
    word_count = len(response.split())

    # Too short — probably an error or refusal
    if word_count < 20:
        return QualityScores(
            relevance=0.40, completeness=0.30, accuracy=0.50,
            quality_score=0.38,
            rationale="Response too short — possible refusal or error",
        )

    # Reasonable length — assume quality is good
    # Large model responses are trusted without LLM eval
    quality_score = min(0.75 + (word_count / 2000), 0.95)

    return QualityScores(
        relevance=0.90, completeness=0.85, accuracy=0.90,
        quality_score=round(quality_score, 4),
        rationale="Large model response — rule-based check passed",
    )


class QualityEvaluator:
    """
    Evaluates response quality.
    Uses LLM eval for Small/Medium, rule-based check for Large.
    """

    def __init__(self):
        self._client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )

    def evaluate(
        self,
        query: str,
        response: str,
        model_tier: ModelTier,
    ) -> QualityScores:
        """
        Evaluate the quality of a model response.

        Args:
            query:      The original user query.
            response:   The model's response text.
            model_tier: The tier that produced the response.

        Returns:
            QualityScores with all dimensions + composite score.
        """
        # Large responses — rule-based check only
        if model_tier == ModelTier.LARGE:
            logger.debug("Large tier — using rule-based quality check")
            return _rule_based_check(response)

        # Small/Medium — LLM evaluation
        logger.debug("Evaluating %s tier response with LLM", model_tier.value)

        prompt = _build_eval_prompt(query, response)

        result = self._client.chat.completions.create(
            model=settings.AZURE_DEPLOYMENT_SMALL,   # always cheap model
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        raw  = result.choices[0].message.content
        data = _parse_quality(raw)

        relevance    = float(data["relevance"])
        penalty      = _length_penalty(query, response)
        completeness = float(data["completeness"]) * penalty
        accuracy     = float(data["accuracy"])
        quality_score = _compute_quality_score(relevance, completeness, accuracy)

        logger.info(
            "Quality scores | tier=%s relevance=%.2f completeness=%.2f "
            "accuracy=%.2f composite=%.2f",
            model_tier.value, relevance, completeness, accuracy, quality_score,
        )

        return QualityScores(
            relevance=relevance,
            completeness=completeness,
            accuracy=accuracy,
            quality_score=round(quality_score, 4),
            rationale=data.get("rationale"),
        )