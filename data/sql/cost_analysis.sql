
CREATE VIEW cost_analysis AS
SELECT
    query_date,
    model_final                                 AS tier,
    complexity_band,
    COUNT(*)                                    AS total_queries,
    ROUND(SUM(cost_usd), 6)                     AS total_actual_cost,
    ROUND(SUM(cost_if_always_large), 6)         AS total_large_cost,
    ROUND(SUM(cost_saved), 6)                   AS total_saved,
    ROUND(AVG(cost_usd), 6)                     AS avg_cost_per_query,
    ROUND(AVG(cost_if_always_large), 6)         AS avg_large_cost_per_query,
    ROUND(
        100.0 * SUM(cost_saved) /
        NULLIF(SUM(cost_if_always_large), 0), 2
    )                                           AS savings_pct,
    ROUND(AVG(CAST(input_tokens AS FLOAT)), 1)  AS avg_input_tokens,
    ROUND(AVG(CAST(output_tokens AS FLOAT)), 1) AS avg_output_tokens
FROM stg_queries
GROUP BY query_date, model_final, complexity_band;