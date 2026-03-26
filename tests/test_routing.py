"""
tests/test_routing.py

Unit tests for the Routing Layer.
All tests are fully offline — no LLM API calls.
Ingestion results are constructed directly from Pydantic models.
"""

import pytest
from ingestion.models import RuleFeatures, LLMClassifierScores, IngestionResult
from routing.feature_merger import FeatureMerger
from routing.weighted_score import WeightedScorer
from routing.router import Router
from routing.pipeline import RoutingPipeline
from routing.models import ModelTier, NormalisedFeatures


# ---------------------------------------------------------------------------
# Helpers — build test fixtures without going through IngestionPipeline
# ---------------------------------------------------------------------------

def make_rule_features(**overrides) -> RuleFeatures:
    defaults = dict(
        has_code_block=False,
        asks_high_precision=False,
        asks_compare=False,
        asks_reasoning=False,
        has_json_like_text=False,
        num_distinct_requests=1,
        input_token_count=20,
    )
    defaults.update(overrides)
    return RuleFeatures(**defaults)


def make_llm_scores(**overrides) -> LLMClassifierScores:
    defaults = dict(
        ambiguity=0.2,
        domain_specificity=0.2,
        multi_step=0.2,
        router_confidence=0.85,
        rationale="test",
    )
    defaults.update(overrides)
    return LLMClassifierScores(**defaults)


def make_ingestion_result(rule_overrides=None, llm_overrides=None) -> IngestionResult:
    return IngestionResult(
        query_text="test query",
        rule_features=make_rule_features(**(rule_overrides or {})),
        llm_scores=make_llm_scores(**(llm_overrides or {})),
    )


# ---------------------------------------------------------------------------
# FeatureMerger tests
# ---------------------------------------------------------------------------

class TestFeatureMerger:
    def setup_method(self):
        self.merger = FeatureMerger()

    def test_booleans_map_to_float(self):
        rule = make_rule_features(has_code_block=True, asks_reasoning=False)
        llm = make_llm_scores()
        result = self.merger.merge(rule, llm)
        assert result.has_code_block == 1.0
        assert result.asks_reasoning == 0.0

    def test_all_false_rules_produce_zeros(self):
        rule = make_rule_features()  # all False by default
        llm = make_llm_scores(ambiguity=0.0, domain_specificity=0.0, multi_step=0.0)
        result = self.merger.merge(rule, llm)
        assert result.has_code_block == 0.0
        assert result.asks_compare == 0.0
        assert result.ambiguity == 0.0

    def test_token_count_normalised(self):
        rule = make_rule_features(input_token_count=250)
        result = self.merger.merge(rule, make_llm_scores())
        # 250 / 500 cap = 0.5
        assert result.input_token_count_norm == pytest.approx(0.5)

    def test_token_count_capped_at_one(self):
        rule = make_rule_features(input_token_count=10_000)
        result = self.merger.merge(rule, make_llm_scores())
        assert result.input_token_count_norm == 1.0

    def test_num_requests_normalised(self):
        rule = make_rule_features(num_distinct_requests=2)
        result = self.merger.merge(rule, make_llm_scores())
        # 2 / 5 cap = 0.4
        assert result.num_distinct_requests_norm == pytest.approx(0.4)

    def test_num_requests_capped_at_one(self):
        rule = make_rule_features(num_distinct_requests=100)
        result = self.merger.merge(rule, make_llm_scores())
        assert result.num_distinct_requests_norm == 1.0

    def test_llm_scores_pass_through(self):
        llm = make_llm_scores(ambiguity=0.7, domain_specificity=0.9, multi_step=0.4)
        result = self.merger.merge(make_rule_features(), llm)
        assert result.ambiguity == 0.7
        assert result.domain_specificity == 0.9
        assert result.multi_step == 0.4

    def test_all_features_in_range(self):
        rule = make_rule_features(
            has_code_block=True, asks_reasoning=True,
            num_distinct_requests=3, input_token_count=300,
        )
        llm = make_llm_scores(ambiguity=0.5, domain_specificity=0.8, multi_step=0.6)
        result = self.merger.merge(rule, llm)
        for field, value in result.model_dump().items():
            assert 0.0 <= value <= 1.0, f"Field {field}={value} out of [0,1]"


# ---------------------------------------------------------------------------
# WeightedScorer tests
# ---------------------------------------------------------------------------

class TestWeightedScorer:
    def setup_method(self):
        self.scorer = WeightedScorer()
        self.merger = FeatureMerger()

    def _score(self, rule_overrides=None, llm_overrides=None) -> float:
        features = self.merger.merge(
            make_rule_features(**(rule_overrides or {})),
            make_llm_scores(**(llm_overrides or {})),
        )
        return self.scorer.score(features).weighted_score

    def test_all_zero_features_scores_zero(self):
        features = self.merger.merge(
            make_rule_features(),
            make_llm_scores(ambiguity=0.0, domain_specificity=0.0, multi_step=0.0),
        )
        breakdown = self.scorer.score(features)
        # With all-false booleans and zero counts/llm scores → very low score
        assert breakdown.weighted_score < 0.10

    def test_all_max_features_scores_near_one(self):
        features = self.merger.merge(
            make_rule_features(
                has_code_block=True, asks_high_precision=True,
                asks_compare=True, asks_reasoning=True, has_json_like_text=True,
                num_distinct_requests=100, input_token_count=10_000,
            ),
            make_llm_scores(ambiguity=1.0, domain_specificity=1.0, multi_step=1.0),
        )
        breakdown = self.scorer.score(features)
        assert breakdown.weighted_score > 0.90

    def test_score_is_between_zero_and_one(self):
        score = self._score(
            rule_overrides=dict(has_reasoning=True, num_distinct_requests=3),
            llm_overrides=dict(ambiguity=0.5, domain_specificity=0.6),
        )
        assert 0.0 <= score <= 1.0

    def test_higher_complexity_gives_higher_score(self):
        low = self._score(
            llm_overrides=dict(ambiguity=0.1, domain_specificity=0.1, multi_step=0.1)
        )
        high = self._score(
            rule_overrides=dict(has_code_block=True, asks_reasoning=True),
            llm_overrides=dict(ambiguity=0.9, domain_specificity=0.9, multi_step=0.9)
        )
        assert high > low

    def test_breakdown_fields_present(self):
        features = self.merger.merge(make_rule_features(), make_llm_scores())
        breakdown = self.scorer.score(features)
        assert hasattr(breakdown, "rule_score")
        assert hasattr(breakdown, "llm_score")
        assert hasattr(breakdown, "weighted_score")
        assert breakdown.rule_weight == pytest.approx(0.55)
        assert breakdown.llm_weight  == pytest.approx(0.45)

    def test_weights_sum_to_one(self):
        scorer = WeightedScorer()
        assert scorer.RULE_WEIGHT + scorer.LLM_WEIGHT == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------

class TestRouter:
    def setup_method(self):
        self.merger = FeatureMerger()
        self.scorer = WeightedScorer()
        self.router = Router()

    def _route(self, rule_overrides=None, llm_overrides=None):
        features = self.merger.merge(
            make_rule_features(**(rule_overrides or {})),
            make_llm_scores(**(llm_overrides or {})),
        )
        breakdown = self.scorer.score(features)
        confidence = (llm_overrides or {}).get("router_confidence", 0.85)
        return self.router.route(features, breakdown, confidence)

    def test_low_score_routes_to_small(self):
        decision = self._route(
            llm_overrides=dict(ambiguity=0.0, domain_specificity=0.0, multi_step=0.0, router_confidence=0.9)
        )
        assert decision.final_tier == ModelTier.SMALL

    def test_high_score_routes_to_large(self):
        decision = self._route(
            rule_overrides=dict(
                has_code_block=True, asks_high_precision=True,
                asks_compare=True, asks_reasoning=True, has_json_like_text=True,
                num_distinct_requests=5, input_token_count=500,
            ),
            llm_overrides=dict(ambiguity=1.0, domain_specificity=1.0, multi_step=1.0, router_confidence=0.9)
        )
        assert decision.final_tier == ModelTier.LARGE

    def test_low_confidence_bumps_small_to_medium(self):
        decision = self._route(
            # Very low complexity → SMALL
            llm_overrides=dict(ambiguity=0.0, domain_specificity=0.0, multi_step=0.0, router_confidence=0.4)
        )
        # Should have been SMALL, bumped to MEDIUM
        assert decision.tier == ModelTier.SMALL
        assert decision.final_tier == ModelTier.MEDIUM
        assert decision.was_bumped is True

    def test_low_confidence_bumps_medium_to_large(self):
        decision = self._route(
            # Medium complexity
            rule_overrides=dict(asks_reasoning=True),
            llm_overrides=dict(ambiguity=0.5, domain_specificity=0.5, multi_step=0.5, router_confidence=0.3)
        )
        assert decision.was_bumped is True
        assert decision.final_tier.value in ("medium", "large")

    def test_large_not_bumped_even_with_low_confidence(self):
        decision = self._route(
            rule_overrides=dict(
                has_code_block=True, asks_reasoning=True, asks_compare=True,
                asks_high_precision=True, has_json_like_text=True,
                num_distinct_requests=5, input_token_count=500,
            ),
            llm_overrides=dict(ambiguity=1.0, domain_specificity=1.0, multi_step=1.0, router_confidence=0.1)
        )
        assert decision.final_tier == ModelTier.LARGE
        assert decision.was_bumped is False

    def test_high_confidence_no_bump(self):
        decision = self._route(
            llm_overrides=dict(ambiguity=0.1, domain_specificity=0.1, multi_step=0.1, router_confidence=0.95)
        )
        assert decision.was_bumped is False

    def test_bump_reason_set_when_bumped(self):
        decision = self._route(
            llm_overrides=dict(ambiguity=0.0, domain_specificity=0.0, multi_step=0.0, router_confidence=0.4)
        )
        if decision.was_bumped:
            assert decision.bump_reason is not None
            assert "bumped" in decision.bump_reason

    def test_no_bump_reason_when_not_bumped(self):
        decision = self._route(
            llm_overrides=dict(router_confidence=0.95)
        )
        if not decision.was_bumped:
            assert decision.bump_reason is None

    def test_decision_contains_audit_fields(self):
        decision = self._route()
        assert hasattr(decision, "weighted_score")
        assert hasattr(decision, "rule_score")
        assert hasattr(decision, "llm_score")
        assert hasattr(decision, "normalised_features")
        assert isinstance(decision.normalised_features, NormalisedFeatures)


# ---------------------------------------------------------------------------
# RoutingPipeline integration tests
# ---------------------------------------------------------------------------

class TestRoutingPipeline:
    def setup_method(self):
        self.pipeline = RoutingPipeline()

    def test_returns_routing_decision(self):
        result = self.pipeline.run(make_ingestion_result())
        from routing.models import RoutingDecision
        assert isinstance(result, RoutingDecision)

    def test_final_tier_is_valid(self):
        result = self.pipeline.run(make_ingestion_result())
        assert result.final_tier in list(ModelTier)

    def test_simple_query_routes_small_or_medium(self):
        result = self.pipeline.run(make_ingestion_result(
            llm_overrides=dict(ambiguity=0.1, domain_specificity=0.1, multi_step=0.1, router_confidence=0.9)
        ))
        assert result.final_tier in (ModelTier.SMALL, ModelTier.MEDIUM)

    def test_complex_query_routes_large(self):
        result = self.pipeline.run(make_ingestion_result(
            rule_overrides=dict(
                has_code_block=True, asks_reasoning=True, asks_compare=True,
                asks_high_precision=True, num_distinct_requests=5, input_token_count=500
            ),
            llm_overrides=dict(ambiguity=0.9, domain_specificity=0.9, multi_step=0.9, router_confidence=0.9)
        ))
        assert result.final_tier == ModelTier.LARGE