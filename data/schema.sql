
CREATE TABLE query_logs (

    -- Identity
    query_id        NVARCHAR(36)    NOT NULL PRIMARY KEY,
    query_text      NVARCHAR(2000)  NOT NULL,
    timestamp       DATETIME2       NOT NULL DEFAULT GETUTCDATE(),

    -- Rule features
    has_code_block          BIT         NOT NULL,
    asks_high_precision     BIT         NOT NULL,
    asks_compare            BIT         NOT NULL,
    asks_reasoning          BIT         NOT NULL,
    has_json_like_text      BIT         NOT NULL,
    num_distinct_requests   INT         NOT NULL,
    input_token_count       INT         NOT NULL,

    -- LLM classifier scores
    ambiguity               FLOAT       NOT NULL,
    domain_specificity      FLOAT       NOT NULL,
    multi_step              FLOAT       NOT NULL,
    router_confidence       FLOAT       NOT NULL,
    classifier_rationale    NVARCHAR(500)   NULL,

    -- Routing
    rule_score              FLOAT       NOT NULL,
    llm_score               FLOAT       NOT NULL,
    weighted_score          FLOAT       NOT NULL,
    model_routed            NVARCHAR(10)    NOT NULL,
    model_final             NVARCHAR(10)    NOT NULL,
    was_bumped              BIT         NOT NULL,
    bump_reason             NVARCHAR(500)   NULL,

    -- Response performance
    latency_ms              FLOAT       NOT NULL,
    input_tokens            INT         NOT NULL,
    output_tokens           INT         NOT NULL,

    -- Cost
    cost_usd                FLOAT       NOT NULL,
    cost_if_always_large    FLOAT       NOT NULL,
    cost_saved              FLOAT       NOT NULL,

    -- Quality
    quality_relevance       FLOAT       NOT NULL,
    quality_completeness    FLOAT       NOT NULL,
    quality_accuracy        FLOAT       NOT NULL,
    quality_score           FLOAT       NOT NULL,
    quality_rationale       NVARCHAR(500)   NULL,

    -- Escalation
    was_escalated           BIT         NOT NULL,
    escalation_reason       NVARCHAR(500)   NULL,
    quality_delta           FLOAT           NULL,

    -- Human review
    flagged_for_review      BIT         NOT NULL,
    flag_reason             NVARCHAR(500)   NULL
);

-- Indexes for the analytical views
CREATE INDEX idx_timestamp      ON query_logs(timestamp);
CREATE INDEX idx_model_final    ON query_logs(model_final);
CREATE INDEX idx_was_escalated  ON query_logs(was_escalated);
CREATE INDEX idx_weighted_score ON query_logs(weighted_score);