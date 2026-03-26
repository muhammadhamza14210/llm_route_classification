"""
Applies threshold logic and confidence bump to produce a final RoutingDecision.

Routing rules (per architecture spec):
    weighted_score < 0.35             → Small  (Haiku / GPT-3.5)
    weighted_score 0.35 – 0.65        → Medium (GPT-4o mini)
    weighted_score > 0.65             → Large  (Sonnet / GPT-4)

Confidence bump rule:
    router_confidence < 0.60 AND tier != Large → bump up one tier
    Rationale: when the classifier itself is uncertain, it's cheaper to
    over-route than to under-route and trigger a costly escalation later.
"""

import logging
from routing.models import ModelTier, RoutingDecision, NormalisedFeatures, ScorerBreakdown
from config.settings import settings

logger = logging.getLogger(__name__)


# Tier ordering for bump logic — index = tier rank
_TIER_ORDER = [ModelTier.SMALL, ModelTier.MEDIUM, ModelTier.LARGE]


class Router:
    """
    Stateless router.  Call route(features, scorer_breakdown, router_confidence).

    Thresholds are read from settings so they can be tuned via .env
    without code changes.
    """

    def __init__(self):
        self._small_max   = settings.ROUTER_SMALL_MAX             # default 0.35
        self._medium_max  = settings.ROUTER_MEDIUM_MAX            # default 0.65
        self._bump_thresh = settings.ROUTER_CONFIDENCE_BUMP_THRESHOLD  # default 0.60

    def route(
        self,
        features: NormalisedFeatures,
        scorer_breakdown: ScorerBreakdown,
        router_confidence: float,
    ) -> RoutingDecision:
        """
        Determine the model tier for a query.

        Args:
            features:          Normalised feature vector from FeatureMerger.
            scorer_breakdown:  Scores from WeightedScorer.
            router_confidence: Confidence value from LLMClassifierScores.

        Returns:
            RoutingDecision with tier, final_tier, bump flag, and full audit trail.
        """
        score = scorer_breakdown.weighted_score

        # --- Step 1: Apply score thresholds ---
        tier = self._score_to_tier(score)

        # --- Step 2: Apply confidence bump ---
        final_tier, was_bumped, bump_reason = self._apply_bump(tier, router_confidence)

        decision = RoutingDecision(
            tier=tier,
            final_tier=final_tier,
            was_bumped=was_bumped,
            weighted_score=score,
            router_confidence=router_confidence,
            rule_score=scorer_breakdown.rule_score,
            llm_score=scorer_breakdown.llm_score,
            normalised_features=features,
            bump_reason=bump_reason,
        )

        logger.info(
            "Routing decision | score=%.4f tier=%s final_tier=%s "
            "bumped=%s confidence=%.2f",
            score,
            tier.value,
            final_tier.value,
            was_bumped,
            router_confidence,
        )

        return decision

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _score_to_tier(self, score: float) -> ModelTier:
        """Map weighted_score to a ModelTier via configured thresholds."""
        if score < self._small_max:
            return ModelTier.SMALL
        elif score <= self._medium_max:
            return ModelTier.MEDIUM
        else:
            return ModelTier.LARGE

    def _apply_bump(
        self, tier: ModelTier, confidence: float
    ) -> tuple[ModelTier, bool, str | None]:
        """
        Bump up one tier if confidence < threshold and tier is not already LARGE.

        Returns:
            (final_tier, was_bumped, bump_reason)
        """
        if confidence >= self._bump_thresh or tier == ModelTier.LARGE:
            return tier, False, None

        current_idx = _TIER_ORDER.index(tier)
        bumped_tier = _TIER_ORDER[current_idx + 1]  # always safe: LARGE is excluded above

        reason = (
            f"router_confidence={confidence:.2f} < threshold={self._bump_thresh:.2f}; "
            f"bumped {tier.value} → {bumped_tier.value}"
        )
        logger.debug("Confidence bump applied: %s", reason)

        return bumped_tier, True, reason