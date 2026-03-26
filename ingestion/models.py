"""
Typed data contracts for everything the Ingestion layer produces.
The Routing Layer consumes these directly.
"""
from pydantic import BaseModel, Field
from typing import Optional


class RuleFeatures(BaseModel):
    """
    Output of RuleExtractor.
    All boolean flags are raw; numeric features are raw counts/values.
    Normalisation to 0-1 happens in the Routing Layer (FeatureMerger).
    """

    # --- Boolean flags ---
    has_code_block: bool = Field(
        description="Query contains a fenced code block (``` or ~~~)"
    )
    asks_high_precision: bool = Field(
        description="Query uses precision-demanding language (exact, precise, accurate, etc.)"
    )
    asks_compare: bool = Field(
        description="Query requests a comparison between two or more things"
    )
    asks_reasoning: bool = Field(
        description="Query explicitly requests reasoning, explanation, or step-by-step thinking"
    )
    has_json_like_text: bool = Field(
        description="Query contains JSON-like structure ({...} or [...])"
    )

    # --- Numeric features (raw, not yet normalised) ---
    num_distinct_requests: int = Field(
        description="Count of distinct questions/tasks in the query (split by '?' and imperative markers)"
    )
    input_token_count: int = Field(
        description="Approximate token count of the query"
    )


class LLMClassifierScores(BaseModel):
    """
    Output of LLMClassifier.
    Three float scores 0-1 + confidence + optional rationale string.
    """
    ambiguity: float = Field(ge=0.0, le=1.0, description="How ambiguous/underspecified the query is")
    domain_specificity: float = Field(ge=0.0, le=1.0, description="How specialised/technical the domain is")
    multi_step: float = Field(ge=0.0, le=1.0, description="Whether answering requires multiple reasoning steps")

    router_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Classifier's own confidence in its scores (used for tier-bump logic)"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="Short free-text explanation from the classifier (debug/logging only)"
    )


class IngestionResult(BaseModel):
    """
    Final output of the Ingestion pipeline.
    Contains raw rule features + LLM scores, ready for FeatureMerger.
    """
    query_text: str
    rule_features: RuleFeatures
    llm_scores: LLMClassifierScores