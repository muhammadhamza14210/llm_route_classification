"""
Calls the Azure model deployment for the routed tier.
Tracks latency, token usage, and cost per call.
"""

import time
import logging
from openai import AzureOpenAI
from routing.models import ModelTier
from response.models import ModelResponse
from config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cost rates per token (USD)
# Keys match deployment names in settings
# ---------------------------------------------------------------------------
_COST_RATES = {
    settings.AZURE_DEPLOYMENT_SMALL: {
        "input":  0.165 / 1_000_000,    # gpt-4o-mini
        "output": 0.660 / 1_000_000,
    },
    settings.AZURE_DEPLOYMENT_MEDIUM: {
        "input":  1.210 / 1_000_000,    # o3-mini
        "output": 4.840 / 1_000_000,
    },
    settings.AZURE_DEPLOYMENT_LARGE: {
        "input":  2.750 / 1_000_000,    # gpt-4o
        "output": 11.00 / 1_000_000,
    },
}

# Always-large cost rates for KPI calculation
_LARGE_COST_RATES = _COST_RATES[settings.AZURE_DEPLOYMENT_LARGE]

# Map tier → deployment name
_TIER_TO_DEPLOYMENT = {
    ModelTier.SMALL:  settings.AZURE_DEPLOYMENT_SMALL,
    ModelTier.MEDIUM: settings.AZURE_DEPLOYMENT_MEDIUM,
    ModelTier.LARGE:  settings.AZURE_DEPLOYMENT_LARGE,
}


class ResponseGenerator:
    """
    Calls the Azure model for a given tier and returns a ModelResponse
    with full cost and latency tracking.
    """

    def __init__(self):
        self._client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )

    def generate(self, query: str, tier: ModelTier) -> ModelResponse:
        """
        Call the model deployment for the given tier.

        Args:
            query: The user query to answer.
            tier:  The routed model tier.

        Returns:
            ModelResponse with content, latency, tokens, and cost.
        """
        deployment = _TIER_TO_DEPLOYMENT[tier]

        logger.info("Calling %s (%s) for query: %r", tier.value, deployment, query[:60])

        t0 = time.perf_counter()

        response = self._client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": query}],
        )

        latency_ms = (time.perf_counter() - t0) * 1000

        content       = response.choices[0].message.content.strip()
        input_tokens  = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        rates    = _COST_RATES.get(deployment, _COST_RATES[settings.AZURE_DEPLOYMENT_SMALL])
        cost_usd = (input_tokens * rates["input"]) + (output_tokens * rates["output"])

        logger.info(
            "Response received | tier=%s latency=%.0fms "
            "tokens=%d+%d cost=$%.6f",
            tier.value, latency_ms, input_tokens, output_tokens, cost_usd,
        )

        return ModelResponse(
            content=content,
            model_tier=tier,
            deployment_name=deployment,
            latency_ms=round(latency_ms, 2),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost_usd, 8),
        )

    @staticmethod
    def estimate_large_cost(input_tokens: int, output_tokens: int) -> float:
        """
        Estimate what this query would have cost on the Large model.
        Used for cost_saved KPI — no API call needed.
        """
        return (
            input_tokens  * _LARGE_COST_RATES["input"] +
            output_tokens * _LARGE_COST_RATES["output"]
        )