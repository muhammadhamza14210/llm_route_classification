"""
Typed data contracts for the Routing Layer.
"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class ModelTier(str, Enum):
    """
    The three routing tiers.
    String values match the model labels used throughout the system.
    """
    SMALL  = "small"   # Haiku / GPT-3.5  — weighted_score < 0.35
    MEDIUM = "medium"  # GPT-4o mini       — weighted_score 0.35-0.65
    LARGE  = "large"   # Sonnet / GPT-4    — weighted_score > 0.65


class NormalisedFeatures(BaseModel):
    """
    Output of FeatureMerger.
    Every field is a float in [0, 1].
    Boolean rule features → 1.0 / 0.0
    Numeric rule features → normalised against configured caps
    LLM scores are already 0-1, passed through unchanged.
    """
    # --- Rule-based (normalised) ---
    has_code_block: float
    asks_high_precision: float
    asks_compare: float
    asks_reasoning: float
    has_json_like_text: float
    num_distinct_requests_norm: float   # raw count / cap
    input_token_count_norm: float       # raw count / cap

    # --- LLM scores (pass-through, already 0-1) ---
    ambiguity: float
    domain_specificity: float
    multi_step: float
    # router_confidence is NOT included in the scoring vector (used separately)


class ScorerBreakdown(BaseModel):
    """
    Output of WeightedScorer.
    Contains the weighted_score + an audit trail for observability.
    """
    rule_score: float = Field(
        description="Weighted average of the 7 rule features (pre-weight)"
    )
    llm_score: float = Field(
        description="Weighted average of the 3 LLM scores (pre-weight)"
    )
    weighted_score: float = Field(
        description="Final combined score: rule_score*0.55 + llm_score*0.45"
    )
    rule_weight: float = Field(default=0.55)
    llm_weight: float  = Field(default=0.45)


class RoutingDecision(BaseModel):
    """
    Final output of the Router — everything the Response Layer needs.
    Also logged in full to PostgreSQL by the Metrics Logger.
    """
    tier: ModelTier = Field(description="Routed tier before confidence bump")
    final_tier: ModelTier = Field(description="Tier after applying confidence bump (may differ)")
    was_bumped: bool = Field(description="True if confidence bump changed the tier")

    weighted_score: float
    router_confidence: float

    rule_score: float
    llm_score: float

    normalised_features: NormalisedFeatures
    bump_reason: Optional[str] = Field(
        default=None,
        description="Human-readable reason for bump, if applied"
    )