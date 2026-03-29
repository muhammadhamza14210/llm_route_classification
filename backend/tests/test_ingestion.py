"""
tests/test_ingestion.py

Unit tests for the Ingestion layer.
RuleExtractor tests: fully offline, no API calls.
LLMClassifier tests: covered by interface contract only (mock used).
"""

import pytest
from unittest.mock import MagicMock

from ingestion.rule_extract import RuleExtractor
from ingestion.models import RuleFeatures, LLMClassifierScores, IngestionResult
from ingestion.pipeline import IngestionPipeline


# ---------------------------------------------------------------------------
# RuleExtractor tests
# ---------------------------------------------------------------------------

class TestRuleExtractor:
    def setup_method(self):
        self.extractor = RuleExtractor()

    def extract(self, text: str) -> RuleFeatures:
        return self.extractor.extract(text)

    # has_code_block
    def test_code_block_backticks(self):
        assert self.extract("```python\nprint('hi')\n```").has_code_block is True

    def test_code_block_tildes(self):
        assert self.extract("~~~bash\nls -la\n~~~").has_code_block is True

    def test_no_code_block(self):
        assert self.extract("What is a binary tree?").has_code_block is False

    # asks_high_precision
    def test_high_precision_exact(self):
        assert self.extract("Give me the exact SQL query").asks_high_precision is True

    def test_high_precision_verbatim(self):
        assert self.extract("Reproduce verbatim").asks_high_precision is True

    def test_no_high_precision(self):
        assert self.extract("Tell me about Python").asks_high_precision is False

    # asks_compare
    def test_compare_versus(self):
        assert self.extract("Compare BERT vs GPT").asks_compare is True

    def test_compare_difference(self):
        assert self.extract("What is the difference between SQL and NoSQL?").asks_compare is True

    def test_compare_pros_cons(self):
        assert self.extract("What are the pros and cons of microservices?").asks_compare is True

    def test_no_compare(self):
        assert self.extract("How do I sort a list?").asks_compare is False

    # asks_reasoning
    def test_reasoning_explain(self):
        assert self.extract("Explain how transformers work").asks_reasoning is True

    def test_reasoning_step_by_step(self):
        assert self.extract("Walk me through step-by-step").asks_reasoning is True

    def test_reasoning_why(self):
        assert self.extract("Why does gradient descent converge?").asks_reasoning is True

    def test_no_reasoning(self):
        assert self.extract("List the G7 countries").asks_reasoning is False

    # has_json_like_text
    def test_json_object(self):
        assert self.extract('Send {"name": "Alice", "age": 30}').has_json_like_text is True

    def test_json_array(self):
        assert self.extract("Process [1, 2, 3]").has_json_like_text is True

    def test_no_json(self):
        assert self.extract("What is the capital of France?").has_json_like_text is False

    # num_distinct_requests
    def test_single_request(self):
        assert self.extract("What is Python?").num_distinct_requests >= 1

    def test_multiple_questions(self):
        result = self.extract("What is Python? Why is it popular? How do I install it?")
        assert result.num_distinct_requests >= 2

    def test_compound_request(self):
        result = self.extract("Explain Docker and also show me how to write a Dockerfile")
        assert result.num_distinct_requests >= 2

    # input_token_count
    def test_token_count_nonzero(self):
        assert self.extract("Hello world").input_token_count > 0

    def test_token_count_scales(self):
        short = self.extract("Hi").input_token_count
        long = self.extract("This is a much longer query that should have more tokens than the short one").input_token_count
        assert long > short

    # edge cases
    def test_empty_string(self):
        result = self.extract("")
        assert result.has_code_block is False
        assert result.num_distinct_requests == 1
        assert result.input_token_count == 0

    def test_whitespace_only(self):
        result = self.extract("   \n  ")
        assert result.input_token_count == 0


# ---------------------------------------------------------------------------
# IngestionPipeline tests (mocked LLM)
# ---------------------------------------------------------------------------

class TestIngestionPipeline:
    def setup_method(self):
        # Mock the LLM classifier so tests never hit real APIs
        self.mock_classifier = MagicMock()
        self.mock_classifier.classify.return_value = LLMClassifierScores(
            ambiguity=0.3,
            domain_specificity=0.7,
            multi_step=0.5,
            router_confidence=0.85,
            rationale="Mocked response",
        )
        self.pipeline = IngestionPipeline(classifier=self.mock_classifier)

    def test_run_returns_ingestion_result(self):
        result = self.pipeline.run("Compare BERT vs GPT-4 for NER tasks")
        assert isinstance(result, IngestionResult)

    def test_run_preserves_query_text(self):
        query = "Explain how attention mechanisms work"
        result = self.pipeline.run(query)
        assert result.query_text == query

    def test_run_strips_whitespace(self):
        result = self.pipeline.run("  hello world  ")
        assert result.query_text == "hello world"

    def test_rule_features_populated(self):
        result = self.pipeline.run("Compare BERT vs GPT-4")
        assert result.rule_features.asks_compare is True

    def test_llm_scores_populated(self):
        result = self.pipeline.run("Some query")
        assert result.llm_scores.domain_specificity == 0.7

    def test_classifier_receives_rule_features(self):
        query = "Compare BERT vs GPT-4"
        self.pipeline.run(query)
        call_args = self.mock_classifier.classify.call_args
        assert call_args[0][0] == query  
        assert isinstance(call_args[0][1], RuleFeatures)  

    def test_empty_query_raises(self):
        with pytest.raises(ValueError):
            self.pipeline.run("")

    def test_whitespace_query_raises(self):
        with pytest.raises(ValueError):
            self.pipeline.run("   ")