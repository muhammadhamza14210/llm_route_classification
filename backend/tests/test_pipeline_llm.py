from ingestion.pipeline import IngestionPipeline
from routing.pipeline import RoutingPipeline

ingestion = IngestionPipeline()
routing = RoutingPipeline()

queries = [
    # --- Should route SMALL ---
    "What is Python?",
    "What year was Docker released?",
    "What does API stand for?",

    # --- Should route MEDIUM ---
    "Should I use Redis or Postgres for storing session data?",
    "What are the pros and cons of microservices vs monolithic architecture?",
    "Explain how indexing works in PostgreSQL",
    "Why is my React component re-rendering too many times?",

    # --- Should route LARGE ---
    "Derive the Black-Scholes equation from first principles using Ito's lemma and explain every assumption made",
    "I am building a real-time fraud detection system processing 100k transactions per second. Walk me through the architecture, model selection, feature engineering, and deployment strategy on Azure",
    "Explain the mathematical intuition behind attention mechanisms in transformers, then implement a scaled dot-product attention from scratch in Python",
    "Given this schema {'orders': {'user_id': int, 'product_id': int, 'amount': float, 'timestamp': str}} design a medallion architecture pipeline with exactly what transformations happen at each layer",

    # --- Tricky — ambiguous, confidence bump should fire ---
    "help me with my code",
    "it's not working",
    "fix this",
    "make it better",
]

print(f"\n{'─'*75}")
print(f"{'QUERY':<45} {'SCORE':>6}  {'TIER':<8} {'FINAL':<8} {'BUMP'}")
print(f"{'─'*75}")

for query in queries:
    # Stage 1 — rule extraction + LLM classification
    ingestion_result = ingestion.run(query)

    # Stage 2 — feature merger + weighted scorer + router
    routing_result = routing.run(ingestion_result)

    bump = (f"↑ {routing_result.tier.value}→{routing_result.final_tier.value}"
            if routing_result.was_bumped else "—")

    print(f"{query:<45} {routing_result.weighted_score:>6.4f}  "
          f"{routing_result.tier.value:<8} {routing_result.final_tier.value:<8} {bump}")

    print(f"  llm → ambiguity={ingestion_result.llm_scores.ambiguity:.2f}  "
          f"domain={ingestion_result.llm_scores.domain_specificity:.2f}  "
          f"multi_step={ingestion_result.llm_scores.multi_step:.2f}  "
          f"confidence={ingestion_result.llm_scores.router_confidence:.2f}")
    print(f"  rationale: {ingestion_result.llm_scores.rationale}")
    print()

print(f"{'─'*75}\n")