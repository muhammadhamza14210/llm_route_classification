# Full end-to-end test — real Azure calls through all three layers

import logging
logging.basicConfig(level=logging.INFO)

from ingestion.pipeline import IngestionPipeline
from routing.pipeline import RoutingPipeline
from response.pipeline import ResponsePipeline

ingestion = IngestionPipeline()
routing   = RoutingPipeline()
response  = ResponsePipeline()

queries = [
    "What does API stand for?",
    "Should I use Redis or Postgres for storing session data?",
    "Derive the Black-Scholes equation from first principles using Ito's lemma",
]

print(f"\n{'═'*75}")
print("FULL PIPELINE TEST — Ingestion → Routing → Response")
print(f"{'═'*75}")

for query in queries:
    print(f"\n{'─'*75}")
    print(f"QUERY: {query}")
    print(f"{'─'*75}")

    # Layer 1 — Ingestion
    ingestion_result = ingestion.run(query)
    print(f"\n[INGESTION]")
    print(f"  rules    → compare={ingestion_result.rule_features.asks_compare} "
          f"reasoning={ingestion_result.rule_features.asks_reasoning} "
          f"tokens={ingestion_result.rule_features.input_token_count}")
    print(f"  llm      → ambiguity={ingestion_result.llm_scores.ambiguity:.2f} "
          f"domain={ingestion_result.llm_scores.domain_specificity:.2f} "
          f"multi_step={ingestion_result.llm_scores.multi_step:.2f} "
          f"confidence={ingestion_result.llm_scores.router_confidence:.2f}")
    print(f"  rationale: {ingestion_result.llm_scores.rationale}")

    # Layer 2 — Routing
    routing_result = routing.run(ingestion_result)
    bump = (f"↑ {routing_result.tier.value}→{routing_result.final_tier.value}"
            if routing_result.was_bumped else "none")
    print(f"\n[ROUTING]")
    print(f"  score={routing_result.weighted_score:.4f}  "
          f"tier={routing_result.tier.value}  "
          f"final={routing_result.final_tier.value}  "
          f"bump={bump}")

    # Layer 3 — Response
    response_result = response.run(query, routing_result)
    print(f"\n[RESPONSE]")
    print(f"  model      = {response_result.model_final.value}")
    print(f"  latency    = {response_result.latency_ms:.0f}ms")
    print(f"  tokens     = {response_result.input_tokens} in / "
          f"{response_result.output_tokens} out")
    print(f"  cost       = ${response_result.cost_usd:.6f}")
    print(f"  cost_large = ${response_result.cost_if_always_large:.6f}")
    print(f"  saved      = ${response_result.cost_saved:.6f}")
    print(f"\n[QUALITY]")
    print(f"  relevance    = {response_result.quality_scores.relevance:.2f}")
    print(f"  completeness = {response_result.quality_scores.completeness:.2f}")
    print(f"  accuracy     = {response_result.quality_scores.accuracy:.2f}")
    print(f"  score        = {response_result.quality_score:.2f}")
    print(f"  escalated    = {response_result.was_escalated}")
    if response_result.was_escalated:
        print(f"  escalation   → "
              f"{response_result.escalation.original_tier.value} → "
              f"{response_result.escalation.escalated_tier.value} | "
              f"quality delta = +{response_result.escalation.quality_delta:.2f}")
    if response_result.flagged_for_review:
        print(f"  ⚠️  FLAGGED: {response_result.flag_reason}")
    print(f"\n[ANSWER]")
    print(f"  {response_result.content[:300]}")
    if len(response_result.content) > 300:
        print(f"  ... [{len(response_result.content)} chars total]")

print(f"\n{'═'*75}")
print("SUMMARY")
print(f"{'═'*75}")