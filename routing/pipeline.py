"""
Routing pipeline orchestrator.
Consumes IngestionResult → runs FeatureMerger → WeightedScorer → Router
→ returns RoutingDecision.
"""

import logging
from ingestion.models import IngestionResult
from routing.feature_merger import FeatureMerger
from routing.weighted_score import WeightedScorer
from routing.router import Router
from routing.models import RoutingDecision

logger = logging.getLogger(__name__)


class RoutingPipeline:
    """
    Orchestrates the three routing stages:
        Stage 1 — FeatureMerger   (normalise + concatenate features)
        Stage 2 — WeightedScorer  (compute weighted_score)
        Stage 3 — Router          (apply thresholds + confidence bump)
    """

    def __init__(self):
        self._merger  = FeatureMerger()
        self._scorer  = WeightedScorer()
        self._router  = Router()

    def run(self, ingestion_result: IngestionResult) -> RoutingDecision:
        """
        Run the full routing pipeline.

        Args:
            ingestion_result: Output of IngestionPipeline.run()

        Returns:
            RoutingDecision with final tier and full audit trail.
        """
        # Stage 1: Normalise and merge features
        features = self._merger.merge(
            ingestion_result.rule_features,
            ingestion_result.llm_scores,
        )

        # Stage 2: Compute weighted score
        scorer_breakdown = self._scorer.score(features)

        # Stage 3: Route to tier
        decision = self._router.route(
            features=features,
            scorer_breakdown=scorer_breakdown,
            router_confidence=ingestion_result.llm_scores.router_confidence,
        )

        logger.info(
            "Routing complete | query_preview=%r final_tier=%s score=%.4f",
            ingestion_result.query_text[:60],
            decision.final_tier.value,
            decision.weighted_score,
        )

        return decision