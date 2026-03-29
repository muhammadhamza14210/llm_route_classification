"""
Computes the final weighted_score from a NormalisedFeatures vector.

Weight split (per architecture spec):
    Rules   = 60%  — deterministic, free, high signal-to-noise
    LLM     = 40%  — ambiguity, domain_specificity, multi_step

Within each group, features are averaged before the group weight is applied.
This means adding/removing features within a group doesn't require
rebalancing the 60/40 split.

reasoning_depth is excluded per architecture spec
("small model can't judge this reliably").
"""

from routing.models import NormalisedFeatures, ScorerBreakdown


class WeightedScorer:
    """
    Stateless scorer. Call score(features) → ScorerBreakdown.

    Constants:
        RULE_WEIGHT  — group weight for rule-based features (default 0.55)
        LLM_WEIGHT   — group weight for LLM scores (default 0.45)

    Within-group feature weights:
        All features within a group are equally weighted by default.
        To give a specific feature more influence, adjust its weight
        in _RULE_FEATURE_WEIGHTS or _LLM_FEATURE_WEIGHTS below.
    """

    RULE_WEIGHT: float = 0.6
    LLM_WEIGHT:  float = 0.4

    # Per-feature weights within the rules group.
    # These sum to 1.0 — adjust to emphasise specific signals.
    _RULE_FEATURE_WEIGHTS: dict[str, float] = {
        "has_code_block":           0.20,   # strong complexity signal
        "asks_high_precision":      0.15,
        "asks_compare":             0.15,
        "asks_reasoning":           0.20,   # strong complexity signal
        "has_json_like_text":       0.10,
        "num_distinct_requests_norm": 0.10,
        "input_token_count_norm":   0.10,
    }

    # Per-feature weights within the LLM group.
    # These sum to 1.0.
    _LLM_FEATURE_WEIGHTS: dict[str, float] = {
        "ambiguity":          0.30,
        "domain_specificity": 0.35,   # strongest signal for model capability
        "multi_step":         0.35,   # strongest signal for reasoning depth
    }

    def score(self, features: NormalisedFeatures) -> ScorerBreakdown:
        """
        Compute the weighted score from a normalised feature vector.

        Args:
            features: Output of FeatureMerger (all values in [0, 1]).

        Returns:
            ScorerBreakdown with rule_score, llm_score, and final weighted_score.
        """
        rule_score = self._weighted_avg(
            values={
                "has_code_block":             features.has_code_block,
                "asks_high_precision":        features.asks_high_precision,
                "asks_compare":               features.asks_compare,
                "asks_reasoning":             features.asks_reasoning,
                "has_json_like_text":         features.has_json_like_text,
                "num_distinct_requests_norm": features.num_distinct_requests_norm,
                "input_token_count_norm":     features.input_token_count_norm,
            },
            weights=self._RULE_FEATURE_WEIGHTS,
        )

        llm_score = self._weighted_avg(
            values={
                "ambiguity":          features.ambiguity,
                "domain_specificity": features.domain_specificity,
                "multi_step":         features.multi_step,
            },
            weights=self._LLM_FEATURE_WEIGHTS,
        )

        weighted_score = (rule_score * self.RULE_WEIGHT) + (llm_score * self.LLM_WEIGHT)

        return ScorerBreakdown(
            rule_score=round(rule_score, 4),
            llm_score=round(llm_score, 4),
            weighted_score=round(weighted_score, 4),
            rule_weight=self.RULE_WEIGHT,
            llm_weight=self.LLM_WEIGHT,
        )

    @staticmethod
    def _weighted_avg(values: dict[str, float], weights: dict[str, float]) -> float:
        """
        Compute a weighted average.
        Weights do not need to sum to 1 — they are normalised internally.
        This makes it safe to add/remove features without manual rebalancing.
        """
        total_weight = sum(weights[k] for k in values)
        if total_weight == 0:
            return 0.0
        return sum(values[k] * weights[k] for k in values) / total_weight