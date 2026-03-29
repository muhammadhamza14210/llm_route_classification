import pytest
from unittest.mock import MagicMock, patch
from routing.models import ModelTier, RoutingDecision, NormalisedFeatures
from response.models import ModelResponse, QualityScores, FinalResponse
from response.quality_evaluator import QualityEvaluator, QUALITY_THRESHOLD, _rule_based_check
from response.escalation_engine import AdaptiveEscalationEngine
from response.pipeline import ResponsePipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_model_response(tier=ModelTier.SMALL, cost=0.000002, latency=310.0) -> ModelResponse:
    return ModelResponse(
        content="This is a test response.",
        model_tier=tier,
        deployment_name="test-deployment",
        latency_ms=latency,
        input_tokens=10,
        output_tokens=20,
        cost_usd=cost,
    )

def make_quality_scores(score=0.85) -> QualityScores:
    return QualityScores(
        relevance=score,
        completeness=score,
        accuracy=score,
        quality_score=score,
        rationale="Test quality scores",
    )

def make_routing_decision(tier=ModelTier.SMALL) -> RoutingDecision:
    features = NormalisedFeatures(
        has_code_block=0.0, asks_high_precision=0.0,
        asks_compare=0.0, asks_reasoning=0.0,
        has_json_like_text=0.0, num_distinct_requests_norm=0.2,
        input_token_count_norm=0.02, ambiguity=0.1,
        domain_specificity=0.1, multi_step=0.1,
    )
    return RoutingDecision(
        tier=tier, final_tier=tier,
        was_bumped=False, weighted_score=0.10,
        router_confidence=0.85, rule_score=0.05,
        llm_score=0.10, normalised_features=features,
    )


# ---------------------------------------------------------------------------
# QualityEvaluator tests
# ---------------------------------------------------------------------------

class TestQualityEvaluator:

    def test_large_tier_uses_rule_based_check(self):
        evaluator = QualityEvaluator.__new__(QualityEvaluator)
        result = evaluator.evaluate("query", "This is a response " * 20, ModelTier.LARGE)
        assert result.quality_score > 0.0
        assert "rule-based" in result.rationale.lower()

    def test_short_large_response_scores_low(self):
        result = _rule_based_check("Too short")
        assert result.quality_score < QUALITY_THRESHOLD

    def test_long_large_response_scores_high(self):
        result = _rule_based_check("word " * 100)
        assert result.quality_score >= QUALITY_THRESHOLD

    def test_quality_score_in_range(self):
        scores = make_quality_scores(0.80)
        assert 0.0 <= scores.quality_score <= 1.0


# ---------------------------------------------------------------------------
# EscalationEngine tests
# ---------------------------------------------------------------------------

class TestEscalationEngine:

    def setup_method(self):
        self.engine = AdaptiveEscalationEngine()

    def test_good_quality_no_escalation(self):
        result = self.engine.evaluate(make_quality_scores(0.80), ModelTier.SMALL)
        assert result.should_escalate is False
        assert result.flag_for_review is False

    def test_poor_quality_small_escalates_to_medium(self):
        result = self.engine.evaluate(make_quality_scores(0.50), ModelTier.SMALL)
        assert result.should_escalate is True
        assert result.next_tier == ModelTier.MEDIUM
        assert result.flag_for_review is False

    def test_poor_quality_medium_escalates_to_large(self):
        result = self.engine.evaluate(make_quality_scores(0.50), ModelTier.MEDIUM)
        assert result.should_escalate is True
        assert result.next_tier == ModelTier.LARGE

    def test_poor_quality_large_flags_for_review(self):
        result = self.engine.evaluate(make_quality_scores(0.50), ModelTier.LARGE)
        assert result.should_escalate is False
        assert result.flag_for_review is True
        assert result.flag_reason is not None

    def test_exact_threshold_no_escalation(self):
        result = self.engine.evaluate(make_quality_scores(QUALITY_THRESHOLD), ModelTier.SMALL)
        assert result.should_escalate is False

    def test_just_below_threshold_escalates(self):
        result = self.engine.evaluate(make_quality_scores(QUALITY_THRESHOLD - 0.01), ModelTier.SMALL)
        assert result.should_escalate is True

    def test_escalation_record_built_correctly(self):
        record = self.engine.build_escalation_record(
            original_tier=ModelTier.SMALL,
            escalated_tier=ModelTier.MEDIUM,
            original_quality=0.50,
            escalated_quality=0.82,
        )
        assert record.original_tier == ModelTier.SMALL
        assert record.escalated_tier == ModelTier.MEDIUM
        assert record.quality_delta == pytest.approx(0.32)


# ---------------------------------------------------------------------------
# ResponsePipeline tests (fully mocked)
# ---------------------------------------------------------------------------

class TestResponsePipeline:

    def _make_pipeline(self, quality_score=0.85, tier=ModelTier.SMALL):
        pipeline = ResponsePipeline.__new__(ResponsePipeline)
        pipeline._generator  = MagicMock()
        pipeline._evaluator  = MagicMock()
        pipeline._escalation = AdaptiveEscalationEngine()

        pipeline._generator.generate.return_value = make_model_response(tier=tier)
        pipeline._generator.estimate_large_cost.return_value = 0.000089
        pipeline._evaluator.evaluate.return_value = make_quality_scores(quality_score)

        return pipeline

    def test_returns_final_response(self):
        pipeline = self._make_pipeline()
        result = pipeline.run("What is Python?", make_routing_decision())
        assert isinstance(result, FinalResponse)

    def test_no_escalation_when_quality_good(self):
        pipeline = self._make_pipeline(quality_score=0.85)
        result = pipeline.run("What is Python?", make_routing_decision())
        assert result.was_escalated is False
        assert result.escalation is None

    def test_escalation_triggered_when_quality_poor(self):
        pipeline = self._make_pipeline(quality_score=0.45)
        result = pipeline.run("What is Python?", make_routing_decision(ModelTier.SMALL))
        assert result.was_escalated is True
        assert result.escalation is not None
        assert result.escalation.original_tier == ModelTier.SMALL

    def test_cost_saved_computed(self):
        pipeline = self._make_pipeline()
        result = pipeline.run("What is Python?", make_routing_decision())
        assert result.cost_if_always_large > 0
        assert result.cost_saved >= 0

    def test_model_routed_vs_final(self):
        pipeline = self._make_pipeline(quality_score=0.45)
        result = pipeline.run("query", make_routing_decision(ModelTier.SMALL))
        assert result.model_routed == ModelTier.SMALL
        # final should be escalated tier
        assert result.was_escalated is True

    def test_large_flagged_for_review_on_poor_quality(self):
        pipeline = self._make_pipeline(quality_score=0.45, tier=ModelTier.LARGE)
        result = pipeline.run("query", make_routing_decision(ModelTier.LARGE))
        assert result.flagged_for_review is True
        assert result.flag_reason is not None

    def test_content_populated(self):
        pipeline = self._make_pipeline()
        result = pipeline.run("What is Python?", make_routing_decision())
        assert result.content == "This is a test response."

    def test_query_text_preserved(self):
        pipeline = self._make_pipeline()
        result = pipeline.run("What is Python?", make_routing_decision())
        assert result.query_text == "What is Python?"