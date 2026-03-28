CREATE VIEW stg_queries AS
SELECT
    query_id,
    query_text,
    timestamp,

    -- Rule features
    has_code_block,
    asks_high_precision,
    asks_compare,
    asks_reasoning,
    has_json_like_text,
    num_distinct_requests,
    input_token_count,

    -- LLM scores
    ambiguity,
    domain_specificity,
    multi_step,
    router_confidence,
    classifier_rationale,

    -- Routing
    rule_score,
    llm_score,
    weighted_score,
    model_routed,
    model_final,
    was_bumped,
    bump_reason,

    -- Performance
    latency_ms,
    input_tokens,
    output_tokens,

    -- Cost
    cost_usd,
    cost_if_always_large,
    cost_saved,

    -- Quality
    quality_relevance,
    quality_completeness,
    quality_accuracy,
    quality_score,
    quality_rationale,

    -- Escalation
    was_escalated,
    escalation_reason,
    quality_delta,

    -- Human review
    flagged_for_review,
    flag_reason,

    -- Derived columns
    CASE
        WHEN weighted_score < 0.15 THEN 'low'
        WHEN weighted_score < 0.32 THEN 'medium'
        ELSE 'high'
    END AS complexity_band,

    CASE
        WHEN model_routed = model_final THEN 'no_change'
        WHEN was_escalated = 1         THEN 'escalated'
        WHEN was_bumped = 1            THEN 'bumped'
        ELSE 'no_change'
    END AS routing_outcome,

    CAST(timestamp AS DATE) AS query_date,
    DATEPART(HOUR, timestamp) AS query_hour

FROM query_logs
WHERE query_text IS NOT NULL
  AND query_text != '';