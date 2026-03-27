"""
Typed schema for the query_logs table.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class QueryLogRecord(BaseModel):
    """
    One complete record per query.
    Written by MetricsLogger after every response pipeline run.
    Maps 1:1 to the query_logs table in Azure SQL.
    """

    # --- Identity ---
    query_id:   str = Field(description="UUID for this query")
    query_text: str = Field(description="Raw user query string")
    timestamp:  datetime = Field(description="When the query was received")

    # --- Rule features ---
    has_code_block:            bool
    asks_high_precision:       bool
    asks_compare:              bool
    asks_reasoning:            bool
    has_json_like_text:        bool
    num_distinct_requests:     int
    input_token_count:         int

    # --- LLM classifier scores ---
    ambiguity:          float
    domain_specificity: float
    multi_step:         float
    router_confidence:  float
    classifier_rationale: Optional[str] = None

    # --- Routing ---
    rule_score:     float
    llm_score:      float
    weighted_score: float
    model_routed:   str   # small / medium / large
    model_final:    str   # small / medium / large (may differ if escalated)
    was_bumped:     bool
    bump_reason:    Optional[str] = None

    # --- Response performance ---
    latency_ms:    float
    input_tokens:  int
    output_tokens: int

    # --- Cost ---
    cost_usd:            float
    cost_if_always_large: float
    cost_saved:          float

    # --- Quality ---
    quality_relevance:    float
    quality_completeness: float
    quality_accuracy:     float
    quality_score:        float
    quality_rationale:    Optional[str] = None

    # --- Escalation ---
    was_escalated:       bool
    escalation_reason:   Optional[str] = None
    quality_delta:       Optional[float] = None   # quality improvement after escalation

    # --- Human review ---
    flagged_for_review: bool
    flag_reason:        Optional[str] = None