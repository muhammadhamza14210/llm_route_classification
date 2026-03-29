"""
Response pipeline orchestrator.
Consumes RoutingDecision → generates response → evaluates quality
→ escalates if needed → returns FinalResponse.
"""

import logging
from routing.models import RoutingDecision
from response.models import FinalResponse
from response.response_generator import ResponseGenerator
from response.quality_evaluator import QualityEvaluator
from response.escalation_engine import AdaptiveEscalationEngine

logger = logging.getLogger(__name__)


class ResponsePipeline:
    """
    Orchestrates the three response stages:
        Stage 1 — ResponseGenerator    (call routed model)
        Stage 2 — QualityEvaluator     (score the response)
        Stage 3 — EscalationEngine     (retry if quality < 0.65)
    """

    def __init__(self):
        self._generator  = ResponseGenerator()
        self._evaluator  = QualityEvaluator()
        self._escalation = AdaptiveEscalationEngine()

    def run(self, query: str, routing_decision: RoutingDecision) -> FinalResponse:
        """
        Run the full response pipeline.

        Args:
            query:            Raw user query string.
            routing_decision: Output of RoutingPipeline.run()

        Returns:
            FinalResponse with content, quality scores, cost, and escalation info.
        """
        routed_tier = routing_decision.final_tier

        # ------------------------------------------------------------------
        # Stage 1: Generate initial response on routed tier
        # ------------------------------------------------------------------
        response = self._generator.generate(query, routed_tier)

        # ------------------------------------------------------------------
        # Stage 2: Evaluate quality
        # ------------------------------------------------------------------
        quality = self._evaluator.evaluate(query, response.content, routed_tier)

        # ------------------------------------------------------------------
        # Stage 3: Check if escalation needed
        # ------------------------------------------------------------------
        escalation_check = self._escalation.evaluate(quality, routed_tier)

        escalation_record = None
        final_response    = response
        final_quality     = quality
        flagged           = escalation_check.flag_for_review
        flag_reason       = escalation_check.flag_reason

        if escalation_check.should_escalate:
            logger.info(
                "Escalating from %s to %s",
                routed_tier.value,
                escalation_check.next_tier.value,
            )

            # Call next tier
            escalated_response = self._generator.generate(
                query, escalation_check.next_tier
            )

            # Evaluate escalated response
            escalated_quality = self._evaluator.evaluate(
                query,
                escalated_response.content,
                escalation_check.next_tier,
            )

            # Check if escalated Large response also failed
            if escalated_quality.quality_score < 0.65 and escalation_check.next_tier.value == "large":
                flagged     = True
                flag_reason = (
                    f"quality {escalated_quality.quality_score:.2f} < 0.65 "
                    f"even after escalation to large — flagged for human review"
                )

            # Build escalation record for logging
            escalation_record = self._escalation.build_escalation_record(
                original_tier=routed_tier,
                escalated_tier=escalation_check.next_tier,
                original_quality=quality.quality_score,
                escalated_quality=escalated_quality.quality_score,
            )

            final_response = escalated_response
            final_quality  = escalated_quality

        # ------------------------------------------------------------------
        # Compute cost KPIs
        # ------------------------------------------------------------------
        cost_if_large = self._generator.estimate_large_cost(
            final_response.input_tokens,
            final_response.output_tokens,
        )
        cost_saved = max(0.0, cost_if_large - final_response.cost_usd)

        logger.info(
            "Response pipeline complete | routed=%s final=%s "
            "quality=%.2f escalated=%s cost_saved=$%.6f",
            routed_tier.value,
            final_response.model_tier.value,
            final_quality.quality_score,
            escalation_record is not None,
            cost_saved,
        )

        return FinalResponse(
            content=final_response.content,
            query_text=query,
            model_routed=routed_tier,
            model_final=final_response.model_tier,
            latency_ms=final_response.latency_ms,
            input_tokens=final_response.input_tokens,
            output_tokens=final_response.output_tokens,
            cost_usd=final_response.cost_usd,
            cost_if_always_large=round(cost_if_large, 8),
            cost_saved=round(cost_saved, 8),
            quality_scores=final_quality,
            quality_score=final_quality.quality_score,
            was_escalated=escalation_record is not None,
            escalation=escalation_record,
            flagged_for_review=flagged,
            flag_reason=flag_reason,
        )