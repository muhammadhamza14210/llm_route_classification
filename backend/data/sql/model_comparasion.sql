CREATE VIEW model_comparison AS
SELECT
    model_final                                         AS tier,
    COUNT(*)                                            AS total_queries,

    -- Latency
    ROUND(AVG(latency_ms), 2)                           AS avg_latency_ms,
    ROUND(MIN(latency_ms), 2)                           AS min_latency_ms,
    ROUND(MAX(latency_ms), 2)                           AS max_latency_ms,

    -- Cost
    ROUND(AVG(cost_usd), 6)                             AS avg_cost_usd,
    ROUND(SUM(cost_usd), 6)                             AS total_cost_usd,
    ROUND(SUM(cost_saved), 6)                           AS total_saved_usd,

    -- Quality
    ROUND(AVG(quality_score), 4)                        AS avg_quality_score,
    ROUND(AVG(quality_relevance), 4)                    AS avg_relevance,
    ROUND(AVG(quality_completeness), 4)                 AS avg_completeness,
    ROUND(AVG(quality_accuracy), 4)                     AS avg_accuracy,

    -- Efficiency ratio
    ROUND(AVG(quality_score) / NULLIF(AVG(cost_usd), 0), 2) AS quality_per_dollar,

    -- Token usage
    ROUND(AVG(CAST(input_tokens AS FLOAT)), 1)          AS avg_input_tokens,
    ROUND(AVG(CAST(output_tokens AS FLOAT)), 1)         AS avg_output_tokens

FROM stg_queries
GROUP BY model_final;