"""
Normalises raw RuleFeatures to [0, 1] and merges them with the
already-normalised LLMClassifierScores into a single NormalisedFeatures vector.

Design notes:
  - Booleans → 1.0 / 0.0 (no transformation needed)
  - Numeric features capped at a configurable max, then divided by that max
  - LLM scores pass through unchanged (already 0-1 by contract)
  - reasoning_depth is intentionally EXCLUDED per architecture spec
    ("small model can't judge this")
  - All caps are class-level constants — easy to tune without touching logic
"""

from ingestion.models import RuleFeatures, LLMClassifierScores
from routing.models import NormalisedFeatures


class FeatureMerger:
    """
    Stateless merger.  Call merge(rule_features, llm_scores) → NormalisedFeatures.

    Normalisation caps — tune these as you gather real traffic data:
        NUM_REQUESTS_CAP   : queries with more distinct requests than this → 1.0
        TOKEN_COUNT_CAP    : queries longer than this (tokens) → 1.0
    """

    # Empirically reasonable starting caps — adjust after seeing real traffic
    NUM_REQUESTS_CAP: int = 5      # 5+ distinct requests → max complexity signal
    TOKEN_COUNT_CAP:  int = 500    # 500+ tokens → max length signal

    def merge(
        self,
        rule_features: RuleFeatures,
        llm_scores: LLMClassifierScores,
    ) -> NormalisedFeatures:
        """
        Normalise rule features and merge with LLM scores.

        Args:
            rule_features:  Output of RuleExtractor (raw values).
            llm_scores:     Output of LLMClassifier (already 0-1).

        Returns:
            NormalisedFeatures — every field in [0, 1].
        """
        return NormalisedFeatures(
            # Boolean rule features — cast to float
            has_code_block      = float(rule_features.has_code_block),
            asks_high_precision = float(rule_features.asks_high_precision),
            asks_compare        = float(rule_features.asks_compare),
            asks_reasoning      = float(rule_features.asks_reasoning),
            has_json_like_text  = float(rule_features.has_json_like_text),

            # Numeric rule features — clip then normalise
            num_distinct_requests_norm = self._normalise(
                rule_features.num_distinct_requests,
                self.NUM_REQUESTS_CAP,
            ),
            input_token_count_norm = self._normalise(
                rule_features.input_token_count,
                self.TOKEN_COUNT_CAP,
            ),

            # LLM scores — pass through (already validated 0-1 by Pydantic)
            ambiguity          = llm_scores.ambiguity,
            domain_specificity = llm_scores.domain_specificity,
            multi_step         = llm_scores.multi_step,
        )

    @staticmethod
    def _normalise(value: float, cap: float) -> float:
        """Clip value to [0, cap] then scale to [0, 1]."""
        return min(value, cap) / cap