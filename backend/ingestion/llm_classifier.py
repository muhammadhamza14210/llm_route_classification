"""
LLM-based classifier using Azure OpenAI via Microsoft Foundry.
Scores three signals that rules cannot detect:
    - ambiguity
    - domain_specificity
    - multi_step
"""

import json
import re
from abc import ABC, abstractmethod
from ingestion.models import LLMClassifierScores, RuleFeatures
from config.settings import settings
from openai import AzureOpenAI


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(query: str, rule_features: RuleFeatures) -> str:
    """
    Build the classification prompt.
    Rule features are injected as context so the LLM only scores what
    the rules cannot already detect — no redundant work.
    """
    rule_context = (
        f"- has_code_block: {rule_features.has_code_block}\n"
        f"- asks_high_precision: {rule_features.asks_high_precision}\n"
        f"- asks_compare: {rule_features.asks_compare}\n"
        f"- asks_reasoning: {rule_features.asks_reasoning}\n"
        f"- has_json_like_text: {rule_features.has_json_like_text}\n"
        f"- num_distinct_requests: {rule_features.num_distinct_requests}\n"
        f"- input_token_count: {rule_features.input_token_count}"
    )

    return f"""You are a query complexity classifier for an LLM routing system.

Rule-based features have already been extracted from this query:
{rule_context}

Your job is to score ONLY the three signals that rules cannot detect:

1. ambiguity (0.0-1.0)
   How underspecified or ambiguous is the query?
   0 = completely clear | 1 = very vague, missing critical context

2. domain_specificity (0.0-1.0)
   How specialised or technical is the domain?
   0 = general knowledge | 1 = highly specialised (finance, medicine, law, systems)

3. multi_step (0.0-1.0)
   Does answering correctly require multiple chained reasoning steps?
   0 = single direct answer | 1 = requires planning and sequential reasoning

Also provide:
4. router_confidence (0.0-1.0)
   How confident are you in your own scores?
   Use < 0.60 if the query is genuinely hard to classify.

5. rationale
   One sentence explaining the key factor driving your scores.

Respond with ONLY valid JSON. No markdown, no explanation outside the JSON.

{{
  "ambiguity": <float>,
  "domain_specificity": <float>,
  "multi_step": <float>,
  "router_confidence": <float>,
  "rationale": "<string>"
}}

Query to classify:
\"\"\"
{query}
\"\"\""""


def _parse_scores(raw: str) -> LLMClassifierScores:
    """Parse JSON response into LLMClassifierScores. Strips markdown fences if present."""
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    data = json.loads(cleaned)
    return LLMClassifierScores(
        ambiguity=float(data["ambiguity"]),
        domain_specificity=float(data["domain_specificity"]),
        multi_step=float(data["multi_step"]),
        router_confidence=float(data["router_confidence"]),
        rationale=data.get("rationale"),
    )


# ---------------------------------------------------------------------------
# Base class — keep this so tests can mock it cleanly
# ---------------------------------------------------------------------------

class BaseLLMClassifier(ABC):
    @abstractmethod
    def classify(self, query: str, rule_features: RuleFeatures) -> LLMClassifierScores:
        ...


# ---------------------------------------------------------------------------
# Azure OpenAI implementation
# ---------------------------------------------------------------------------

class AzureOpenAIClassifier(BaseLLMClassifier):
    """
    LLM classifier backed by Azure OpenAI (Microsoft Foundry).
    Uses the SMALL deployment — gpt-4o-mini by default.

    The AzureOpenAI client is identical to the standard OpenAI client
    except it points at your Foundry endpoint and uses your deployment
    name instead of the model name.
    """

    def __init__(self):
        if not settings.AZURE_OPENAI_API_KEY:
            raise ValueError(
                "AZURE_OPENAI_API_KEY is not set. "
                "Add it to your .env file."
            )
        if not settings.AZURE_OPENAI_ENDPOINT:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT is not set. "
                "Add it to your .env file (e.g. https://your-resource.openai.azure.com/)"
            )

        self._client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
        # Classifier always uses the cheap small deployment
        self._deployment = settings.AZURE_DEPLOYMENT_SMALL

    def classify(self, query: str, rule_features: RuleFeatures) -> LLMClassifierScores:
        prompt = _build_prompt(query, rule_features)

        response = self._client.chat.completions.create(
            model=self._deployment,          # Azure: deployment name, not model name
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},  # forces clean JSON output
        )

        raw = response.choices[0].message.content
        return _parse_scores(raw)


# ---------------------------------------------------------------------------
# Factory — returns the one classifier we support
# ---------------------------------------------------------------------------

def get_classifier() -> BaseLLMClassifier:
    """
    Return the AzureOpenAIClassifier.
    Kept as a factory function so tests can inject a mock without
    changing the pipeline code.
    """
    return AzureOpenAIClassifier()