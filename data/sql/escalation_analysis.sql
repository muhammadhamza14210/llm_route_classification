
CREATE VIEW escalation_analysis AS
SELECT
    query_date,
    routing_outcome,
    COUNT(*)                                        AS total_queries,
    ROUND(AVG(weighted_score), 4)                   AS avg_weighted_score,
    ROUND(AVG(quality_score), 4)                    AS avg_quality_score,
    ROUND(AVG(CASE WHEN was_escalated = 1
        THEN quality_delta ELSE NULL END), 4)       AS avg_quality_delta,
    ROUND(AVG(CASE WHEN was_escalated = 1
        THEN latency_ms ELSE NULL END), 2)          AS avg_latency_on_escalation,
    ROUND(AVG(CASE WHEN was_escalated = 1
        THEN cost_usd ELSE NULL END), 6)            AS avg_cost_on_escalation,
    SUM(CAST(flagged_for_review AS INT))            AS total_flagged_for_review,
    ROUND(AVG(router_confidence), 4)                AS avg_router_confidence,
    SUM(CAST(was_bumped AS INT))                    AS total_bumped
FROM stg_queries
GROUP BY query_date, routing_outcome;