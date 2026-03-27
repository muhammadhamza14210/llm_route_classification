"""
Writes one QueryLogRecord to Azure SQL after every query.
"""

import uuid
import logging
from datetime import datetime, timezone

import pymssql

from config.settings import settings
from data.models import QueryLogRecord
from ingestion.models import IngestionResult
from routing.models import RoutingDecision
from response.models import FinalResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Insert statement — matches schema.sql exactly
# ---------------------------------------------------------------------------
_INSERT_SQL = """
INSERT INTO query_logs (
    query_id, query_text, timestamp,
    has_code_block, asks_high_precision, asks_compare, asks_reasoning,
    has_json_like_text, num_distinct_requests, input_token_count,
    ambiguity, domain_specificity, multi_step, router_confidence,
    classifier_rationale,
    rule_score, llm_score, weighted_score,
    model_routed, model_final, was_bumped, bump_reason,
    latency_ms, input_tokens, output_tokens,
    cost_usd, cost_if_always_large, cost_saved,
    quality_relevance, quality_completeness, quality_accuracy,
    quality_score, quality_rationale,
    was_escalated, escalation_reason, quality_delta,
    flagged_for_review, flag_reason
) VALUES (
    %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s, %s,
    %s,
    %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s,
    %s, %s,
    %s, %s, %s,
    %s, %s
)
"""


class MetricsLogger:
    """
    Writes query log records to Azure SQL.
    One instance per application — reuses connection.
    """

    def __init__(self):
        self._conn = pymssql.connect(
            server=settings.AZURE_SQL_SERVER,
            user=settings.AZURE_SQL_USERNAME,
            password=settings.AZURE_SQL_PASSWORD,
            database=settings.AZURE_SQL_DATABASE,
        )
        logger.info("MetricsLogger connected to Azure SQL")

    def log(
        self,
        ingestion_result: IngestionResult,
        routing_decision: RoutingDecision,
        final_response: FinalResponse,
    ) -> str:
        """
        Build and insert a full QueryLogRecord.

        Args:
            ingestion_result: Output of IngestionPipeline.run()
            routing_decision: Output of RoutingPipeline.run()
            final_response:   Output of ResponsePipeline.run()

        Returns:
            query_id (UUID string) of the inserted record.
        """
        query_id = str(uuid.uuid4())
        record   = self._build_record(
            query_id, ingestion_result, routing_decision, final_response
        )
        self._insert(record)

        logger.info(
            "Logged query | id=%s tier=%s quality=%.2f cost_saved=$%.6f",
            query_id,
            final_response.model_final.value,
            final_response.quality_score,
            final_response.cost_saved,
        )
        return query_id

    def close(self):
        self._conn.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_record(
        query_id: str,
        ingestion: IngestionResult,
        routing: RoutingDecision,
        response: FinalResponse,
    ) -> QueryLogRecord:
        """Assemble all pipeline outputs into one flat QueryLogRecord."""
        rf  = ingestion.rule_features
        llm = ingestion.llm_scores
        qs  = response.quality_scores
        esc = response.escalation

        return QueryLogRecord(
            # Identity
            query_id   = query_id,
            query_text = ingestion.query_text,
            timestamp  = datetime.now(timezone.utc),

            # Rule features
            has_code_block        = rf.has_code_block,
            asks_high_precision   = rf.asks_high_precision,
            asks_compare          = rf.asks_compare,
            asks_reasoning        = rf.asks_reasoning,
            has_json_like_text    = rf.has_json_like_text,
            num_distinct_requests = rf.num_distinct_requests,
            input_token_count     = rf.input_token_count,

            # LLM scores
            ambiguity             = llm.ambiguity,
            domain_specificity    = llm.domain_specificity,
            multi_step            = llm.multi_step,
            router_confidence     = llm.router_confidence,
            classifier_rationale  = llm.rationale,

            # Routing
            rule_score     = routing.rule_score,
            llm_score      = routing.llm_score,
            weighted_score = routing.weighted_score,
            model_routed   = routing.final_tier.value,
            model_final    = response.model_final.value,
            was_bumped     = routing.was_bumped,
            bump_reason    = routing.bump_reason,

            # Performance
            latency_ms    = response.latency_ms,
            input_tokens  = response.input_tokens,
            output_tokens = response.output_tokens,

            # Cost
            cost_usd             = response.cost_usd,
            cost_if_always_large = response.cost_if_always_large,
            cost_saved           = response.cost_saved,

            # Quality
            quality_relevance    = qs.relevance,
            quality_completeness = qs.completeness,
            quality_accuracy     = qs.accuracy,
            quality_score        = response.quality_score,
            quality_rationale    = qs.rationale,

            # Escalation
            was_escalated     = response.was_escalated,
            escalation_reason = esc.reason        if esc else None,
            quality_delta     = esc.quality_delta if esc else None,

            # Human review
            flagged_for_review = response.flagged_for_review,
            flag_reason        = response.flag_reason,
        )

    def _insert(self, record: QueryLogRecord):
        """Execute the INSERT statement."""
        cursor = self._conn.cursor()
        cursor.execute(_INSERT_SQL, (
            record.query_id, record.query_text,
            record.timestamp.strftime("%Y-%m-%d %H:%M:%S"),

            int(record.has_code_block), int(record.asks_high_precision),
            int(record.asks_compare), int(record.asks_reasoning),
            int(record.has_json_like_text), record.num_distinct_requests,
            record.input_token_count,

            record.ambiguity, record.domain_specificity,
            record.multi_step, record.router_confidence,
            record.classifier_rationale,

            record.rule_score, record.llm_score, record.weighted_score,
            record.model_routed, record.model_final,
            int(record.was_bumped), record.bump_reason,

            record.latency_ms, record.input_tokens, record.output_tokens,

            record.cost_usd, record.cost_if_always_large, record.cost_saved,

            record.quality_relevance, record.quality_completeness,
            record.quality_accuracy, record.quality_score,
            record.quality_rationale,

            int(record.was_escalated), record.escalation_reason,
            record.quality_delta,

            int(record.flagged_for_review), record.flag_reason,
        ))
        self._conn.commit()
        cursor.close()