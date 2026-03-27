"""
Typed data contracts for the Response Layer.
"""
from pydantic import BaseModel, Field
from typing import Optional
from routing.models import ModelTier


class ModelResponse(BaseModel):
    """
    Raw output from a single model call.
    Produced by ResponseGenerator.
    """
    content: str
    model_tier: ModelTier
    deployment_name: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float


class QualityScores(BaseModel):
    """
    Output of QualityEvaluator.
    Three dimensions scored 0-1 + composite quality_score.
    """
    relevance: float = Field(ge=0.0, le=1.0,
        description="Does the response directly address the query?")
    completeness: float = Field(ge=0.0, le=1.0,
        description="Does it cover all parts of the query?")
    accuracy: float = Field(ge=0.0, le=1.0,
        description="Is the information correct and trustworthy?")
    quality_score: float = Field(ge=0.0, le=1.0,
        description="Weighted composite of the three dimensions")
    rationale: Optional[str] = Field(
        default=None,
        description="Short explanation from the evaluator")


class EscalationRecord(BaseModel):
    """
    Logged when a response is escalated to a higher tier.
    """
    original_tier: ModelTier
    escalated_tier: ModelTier
    original_quality: float
    escalated_quality: float
    quality_delta: float
    reason: str


class FinalResponse(BaseModel):
    """
    Complete output of the Response Layer.
    Contains everything the Metrics Logger needs to write one full record.
    """
    # Core response
    content: str
    query_text: str

    # Routing
    model_routed: ModelTier       # initial routing decision
    model_final: ModelTier        # model that produced the final response

    # Performance
    latency_ms: float
    input_tokens: int
    output_tokens: int

    # Cost
    cost_usd: float
    cost_if_always_large: float
    cost_saved: float

    # Quality
    quality_scores: QualityScores
    quality_score: float

    # Escalation
    was_escalated: bool
    escalation: Optional[EscalationRecord] = None

    # Human review flag
    flagged_for_review: bool = False
    flag_reason: Optional[str] = None