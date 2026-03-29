CREATE VIEW routing_summary AS
SELECT
    model_final                             AS tier,
    COUNT(*)                                AS total_queries,
    ROUND(AVG(weighted_score), 4)           AS avg_weighted_score,
    ROUND(MIN(weighted_score), 4)           AS min_weighted_score,
    ROUND(MAX(weighted_score), 4)           AS max_weighted_score,
    SUM(CAST(was_escalated AS INT))         AS total_escalated,
    SUM(CAST(was_bumped AS INT))            AS total_bumped,
    SUM(CAST(flagged_for_review AS INT))    AS total_flagged,
    ROUND(
        100.0 * SUM(CAST(was_escalated AS INT)) / COUNT(*), 2
    )                                       AS escalation_rate_pct,
    ROUND(AVG(router_confidence), 4)        AS avg_confidence,
    ROUND(AVG(quality_score), 4)            AS avg_quality_score,
    ROUND(AVG(latency_ms), 2)               AS avg_latency_ms
FROM stg_queries
GROUP BY model_final;