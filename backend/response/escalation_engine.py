"""
Adaptive Escalation Engine.

Rules per architecture spec:
    quality < 0.65 + model != large → retry on next tier up, log both attempts
    quality < 0.65 + model == large → flag for human review, no retry
"""

import logging
from routing.models import ModelTier
from response.models import ModelResponse, QualityScores, EscalationRecord
from response.quality_evaluator import QUALITY_THRESHOLD

logger = logging.getLogger(__name__)

# Tier order for escalation — index = rank
_TIER_ORDER = [ModelTier.SMALL, ModelTier.MEDIUM, ModelTier.LARGE]


class EscalationResult:
    """
    Internal result from the escalation engine.
    Not a Pydantic model — used only inside the Response pipeline.
    """
    def __init__(
        self,
        should_escalate: bool,
        next_tier: ModelTier | None,
        flag_for_review: bool,
        flag_reason: str | None,
    ):
        self.should_escalate  = should_escalate
        self.next_tier        = next_tier
        self.flag_for_review  = flag_for_review
        self.flag_reason      = flag_reason


class AdaptiveEscalationEngine:
    """
    Decides whether to escalate a response to the next tier.

    Stateless — call evaluate() on every response before returning to user.
    """

    def evaluate(
        self,
        quality_scores: QualityScores,
        current_tier: ModelTier,
    ) -> EscalationResult:
        """
        Decide if escalation is needed.

        Args:
            quality_scores: Output of QualityEvaluator.
            current_tier:   The tier that produced the response.

        Returns:
            EscalationResult with escalation decision and next tier if applicable.
        """
        score = quality_scores.quality_score

        # Quality is acceptable — no escalation needed
        if score >= QUALITY_THRESHOLD:
            logger.debug(
                "Quality %.2f >= threshold %.2f — no escalation",
                score, QUALITY_THRESHOLD,
            )
            return EscalationResult(
                should_escalate=False,
                next_tier=None,
                flag_for_review=False,
                flag_reason=None,
            )

        # Quality failed on Large — flag for human review, no retry
        if current_tier == ModelTier.LARGE:
            reason = (
                f"quality_score={score:.2f} < threshold={QUALITY_THRESHOLD} "
                f"on large model — escalation not possible"
            )
            logger.warning("Flagging for human review: %s", reason)
            return EscalationResult(
                should_escalate=False,
                next_tier=None,
                flag_for_review=True,
                flag_reason=reason,
            )

        # Quality failed on Small/Medium — escalate to next tier
        current_idx = _TIER_ORDER.index(current_tier)
        next_tier   = _TIER_ORDER[current_idx + 1]

        logger.info(
            "Escalating: quality %.2f < %.2f | %s → %s",
            score, QUALITY_THRESHOLD, current_tier.value, next_tier.value,
        )

        return EscalationResult(
            should_escalate=True,
            next_tier=next_tier,
            flag_for_review=False,
            flag_reason=None,
        )

    @staticmethod
    def build_escalation_record(
        original_tier: ModelTier,
        escalated_tier: ModelTier,
        original_quality: float,
        escalated_quality: float,
    ) -> EscalationRecord:
        """
        Build the escalation record for logging.
        Called after the escalated response is evaluated.
        """
        return EscalationRecord(
            original_tier=original_tier,
            escalated_tier=escalated_tier,
            original_quality=original_quality,
            escalated_quality=escalated_quality,
            quality_delta=round(escalated_quality - original_quality, 4),
            reason=(
                f"quality {original_quality:.2f} < {QUALITY_THRESHOLD} "
                f"on {original_tier.value} — retried on {escalated_tier.value}"
            ),
        )