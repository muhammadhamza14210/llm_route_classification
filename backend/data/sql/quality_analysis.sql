CREATE VIEW quality_analysis AS
SELECT
    query_date,
    model_final                                     AS tier,
    COUNT(*)                                        AS total_queries,
    ROUND(AVG(quality_score), 4)                    AS avg_quality_score,
    ROUND(AVG(quality_relevance), 4)                AS avg_relevance,
    ROUND(AVG(quality_completeness), 4)             AS avg_completeness,
    ROUND(AVG(quality_accuracy), 4)                 AS avg_accuracy,
    ROUND(MIN(quality_score), 4)                    AS min_quality_score,
    ROUND(MAX(quality_score), 4)                    AS max_quality_score,
    SUM(CASE WHEN quality_score < 0.65 THEN 1 ELSE 0 END)  AS below_threshold_count,
    ROUND(
        100.0 * SUM(CASE WHEN quality_score < 0.65 THEN 1 ELSE 0 END)
        / COUNT(*), 2
    )                                               AS below_threshold_pct,
    ROUND(AVG(CASE WHEN was_escalated = 1
        THEN quality_delta ELSE NULL END), 4)       AS avg_quality_delta_on_escalation
FROM stg_queries
GROUP BY query_date, model_final;