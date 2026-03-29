"""
Ingestion pipeline orchestrator.
Runs RuleExtractor + LLMClassifier in sequence and returns IngestionResult.
"""

import time
import logging
from typing import Optional

from ingestion.models import IngestionResult
from ingestion.rule_extract import RuleExtractor
from ingestion.llm_classifier import BaseLLMClassifier, get_classifier

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Orchestrates the two-stage ingestion process:
        Stage 1 — RuleExtractor  (sync, deterministic, <1ms)
        Stage 2 — LLMClassifier  (sync, LLM call, ~500-1500ms)

    Both stages run on every query. Rule features are passed into the
    LLM Classifier as context to avoid redundant scoring.
    """

    def __init__(self, classifier: Optional[BaseLLMClassifier] = None):
        """
        Args:
            classifier: Optional pre-built classifier. If None, built from settings.
        """
        self._rule_extractor = RuleExtractor()
        self._classifier = classifier or get_classifier()

    def run(self, query: str) -> IngestionResult:
        """
        Run the full ingestion pipeline on a query.

        Args:
            query: Raw user query string.

        Returns:
            IngestionResult containing rule_features + llm_scores.

        Raises:
            ValueError: If query is empty.
            Exception: Propagates LLM API errors — handle at call site.
        """
        if not query or not query.strip():
            raise ValueError("Query must be a non-empty string.")

        query = query.strip()

        # ------------------------------------------------------------------
        # Stage 1: Rule extraction (deterministic, free)
        # ------------------------------------------------------------------
        t0 = time.perf_counter()
        rule_features = self._rule_extractor.extract(query)
        rule_ms = (time.perf_counter() - t0) * 1000

        logger.debug(
            "Rule extraction complete in %.2fms | features=%s",
            rule_ms,
            rule_features.model_dump(),
        )

        # ------------------------------------------------------------------
        # Stage 2: LLM classification (scores what rules can't)
        # ------------------------------------------------------------------
        t1 = time.perf_counter()
        llm_scores = self._classifier.classify(query, rule_features)
        llm_ms = (time.perf_counter() - t1) * 1000

        logger.debug(
            "LLM classification complete in %.0fms | scores=%s",
            llm_ms,
            llm_scores.model_dump(),
        )

        logger.info(
            "Ingestion complete | rule_ms=%.2f llm_ms=%.0f "
            "confidence=%.2f rationale=%r",
            rule_ms,
            llm_ms,
            llm_scores.router_confidence,
            llm_scores.rationale,
        )

        return IngestionResult(
            query_text=query,
            rule_features=rule_features,
            llm_scores=llm_scores,
        )