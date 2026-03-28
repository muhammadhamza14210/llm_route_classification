"""
Generates 10,000 synthetic seed records for the dashboard.
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

import uuid
import random
import logging
from datetime import datetime, timezone, timedelta
import pymssql
from config.settings import settings

#   Small  (gpt-4o-mini): $0.165/1M input, $0.660/1M output
#   Medium (o3-mini):     $1.210/1M input, $4.840/1M output
#   Large  (gpt-4o):      $2.750/1M input, $11.00/1M output
TIER_PROFILES = {
    "small": {
        "weighted_score":    (0.01, 0.14),
        "latency_ms":        (800, 2500),
        "input_tokens":      (500, 2000),
        "output_tokens":     (200, 800),
        "cost_usd":          (0.0002, 0.0009),   # gpt-4o-mini rates
        "cost_if_large":     (0.036, 0.107),     # gpt-4o rates on same tokens
        "quality_score":     (0.75, 0.98),
        "ambiguity":         (0.0, 0.3),
        "domain_specificity":(0.0, 0.3),
        "multi_step":        (0.0, 0.2),
        "router_confidence": (0.75, 0.95),
        "escalation_rate":   0.05,
        "bump_rate":         0.10,
    },
    "medium": {
        "weighted_score":    (0.15, 0.31),
        "latency_ms":        (3000, 9000),
        "input_tokens":      (2000, 6000),
        "output_tokens":     (800, 3000),
        "cost_usd":          (0.006, 0.022),     # o3-mini rates
        "cost_if_large":     (0.036, 0.107),     # gpt-4o rates on same tokens
        "quality_score":     (0.78, 0.95),
        "ambiguity":         (0.1, 0.5),
        "domain_specificity":(0.3, 0.7),
        "multi_step":        (0.2, 0.6),
        "router_confidence": (0.65, 0.85),
        "escalation_rate":   0.12,
        "bump_rate":         0.18,
    },
    "large": {
        "weighted_score":    (0.32, 0.65),
        "latency_ms":        (8000, 35000),
        "input_tokens":      (5000, 15000),
        "output_tokens":     (2000, 6000),
        "cost_usd":          (0.036, 0.107),     # gpt-4o rates
        "cost_if_large":     (0.036, 0.107),     # same — it went to large
        "quality_score":     (0.82, 0.97),
        "ambiguity":         (0.1, 0.4),
        "domain_specificity":(0.6, 0.95),
        "multi_step":        (0.5, 0.95),
        "router_confidence": (0.65, 0.85),
        "escalation_rate":   0.03,
        "bump_rate":         0.05,
    },
}

# 10,000 synthetic + 15 real = ~10,015 total records
# 333 queries/day over 30 days — realistic for a small team
TIER_DISTRIBUTION = (
    ["small"]  * 4000 +
    ["medium"] * 4000 +
    ["large"]  * 2000
)

# Sample queries for synthetic expansion per tier
SYNTHETIC_QUERIES = {
    "small": [
        "What is Python?", "What does HTTP stand for?", "What is a database?",
        "What is JSON?", "What is Git?", "What does IDE stand for?",
        "What is a function in programming?", "What is an API?",
        "What is cloud computing?", "What is machine learning?",
        "What is Docker?", "What is Kubernetes?", "What is DevOps?",
        "What is agile methodology?", "What is a data type?",
    ],
    "medium": [
        "Compare SQL vs NoSQL databases for a web application",
        "How does OAuth 2.0 authentication work?",
        "What are the trade-offs between React and Vue for frontend development?",
        "Explain how Kubernetes manages container orchestration",
        "How does gradient descent work in machine learning?",
        "What is the difference between batch and stream processing?",
        "How does load balancing work in distributed systems?",
        "Explain the CAP theorem and its implications",
        "How does Docker networking work?",
        "What are the pros and cons of serverless architecture?",
        "How does Redis handle persistence?",
        "Explain ACID properties in databases",
        "What is the difference between REST and GraphQL?",
        "How does Kafka handle message ordering?",
        "Explain how HTTPS works",
    ],
    "large": [
        "Design a real-time recommendation system for 10 million users",
        "Implement a distributed transaction system using two-phase commit",
        "Explain and implement a B-tree from scratch in Python",
        "Design a scalable notification system handling 1M messages per second",
        "Implement transformer attention mechanism from scratch with backprop",
        "Design a CQRS event sourcing system for an e-commerce platform",
        "Explain and implement consistent hashing for a distributed cache",
        "Design a multi-region active-active database architecture",
        "Implement a custom memory allocator in Python",
        "Design a real-time bidding system for digital advertising",
    ],
}


def rand_float(lo: float, hi: float, decimals: int = 4) -> float:
    return round(random.uniform(lo, hi), decimals)


def rand_bool(probability: float) -> bool:
    return random.random() < probability


def make_synthetic_record(tier: str, days_ago: int) -> dict:
    """Build one synthetic record for the given tier."""
    p = TIER_PROFILES[tier]

    weighted_score    = rand_float(*p["weighted_score"])
    quality_score     = rand_float(*p["quality_score"])
    was_escalated     = rand_bool(p["escalation_rate"])
    was_bumped        = rand_bool(p["bump_rate"]) and not was_escalated
    flagged           = rand_bool(0.02)
    input_tokens      = random.randint(*p["input_tokens"])
    output_tokens     = random.randint(*p["output_tokens"])
    cost_usd          = rand_float(*p["cost_usd"], 8)
    cost_if_large     = rand_float(*p["cost_if_large"], 8)
    cost_saved        = max(0.0, round(cost_if_large - cost_usd, 8))
    ambiguity         = rand_float(*p["ambiguity"])
    domain            = rand_float(*p["domain_specificity"])
    multi_step        = rand_float(*p["multi_step"])
    confidence        = rand_float(*p["router_confidence"])
    rule_score        = rand_float(weighted_score * 0.4, weighted_score * 0.7)
    llm_score         = rand_float(weighted_score * 0.3, weighted_score * 0.9)
    latency_ms        = rand_float(*p["latency_ms"], 2)

    # Escalation — quality improves after escalation
    escalation_reason = None
    quality_delta     = None
    model_final       = tier
    if was_escalated:
        escalation_reason = f"quality {quality_score:.2f} < 0.65 threshold"
        quality_delta     = rand_float(0.05, 0.25)
        quality_score     = min(quality_score + quality_delta, 0.98)
        model_final       = "medium" if tier == "small" else "large"

    # Timestamp spread over last 30 days with hourly variation
    base_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
    timestamp = base_date.replace(
        hour=random.randint(8, 22),
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        microsecond=0,
    )

    query = random.choice(SYNTHETIC_QUERIES[tier])

    return {
        "query_id":              str(uuid.uuid4()),
        "query_text":            query,
        "timestamp":             timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "has_code_block":        int(rand_bool(0.15)),
        "asks_high_precision":   int(rand_bool(0.10 if tier == "small" else 0.25)),
        "asks_compare":          int(rand_bool(0.05 if tier == "small" else 0.40)),
        "asks_reasoning":        int(rand_bool(0.05 if tier == "small" else 0.50)),
        "has_json_like_text":    int(rand_bool(0.05)),
        "num_distinct_requests": random.randint(1, 1 if tier == "small" else 3),
        "input_token_count":     input_tokens,
        "ambiguity":             ambiguity,
        "domain_specificity":    domain,
        "multi_step":            multi_step,
        "router_confidence":     confidence,
        "classifier_rationale":  f"Synthetic: {tier} tier query",
        "rule_score":            rule_score,
        "llm_score":             llm_score,
        "weighted_score":        weighted_score,
        "model_routed":          tier,
        "model_final":           model_final,
        "was_bumped":            int(was_bumped),
        "bump_reason":           f"confidence {confidence:.2f} < 0.65" if was_bumped else None,
        "latency_ms":            latency_ms,
        "input_tokens":          input_tokens,
        "output_tokens":         output_tokens,
        "cost_usd":              cost_usd,
        "cost_if_always_large":  cost_if_large,
        "cost_saved":            cost_saved,
        "quality_relevance":     rand_float(quality_score - 0.1, min(quality_score + 0.1, 1.0)),
        "quality_completeness":  rand_float(quality_score - 0.15, min(quality_score + 0.05, 1.0)),
        "quality_accuracy":      rand_float(quality_score - 0.05, min(quality_score + 0.1, 1.0)),
        "quality_score":         quality_score,
        "quality_rationale":     f"Synthetic quality evaluation for {tier} tier",
        "was_escalated":         int(was_escalated),
        "escalation_reason":     escalation_reason,
        "quality_delta":         quality_delta,
        "flagged_for_review":    int(flagged),
        "flag_reason":           "Quality below threshold after escalation" if flagged else None,
    }


_INSERT_SQL = """
INSERT INTO query_logs (
    query_id, query_text, timestamp,
    has_code_block, asks_high_precision, asks_compare, asks_reasoning,
    has_json_like_text, num_distinct_requests, input_token_count,
    ambiguity, domain_specificity, multi_step, router_confidence,
    classifier_rationale,
    rule_score, llm_score, weighted_score,
    model_routed, model_final, was_bumped, bump_reason,
    latency_ms, input_tokens, output_tokens,
    cost_usd, cost_if_always_large, cost_saved,
    quality_relevance, quality_completeness, quality_accuracy,
    quality_score, quality_rationale,
    was_escalated, escalation_reason, quality_delta,
    flagged_for_review, flag_reason
) VALUES (
    %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s
)
"""


def run_synthetic_inserts(conn):
    """Insert 10,000 synthetic records spread over 30 days."""
    print("\n🔧 Generating synthetic records...")

    random.shuffle(TIER_DISTRIBUTION)
    cursor = conn.cursor()
    count  = 0

    for i, tier in enumerate(TIER_DISTRIBUTION):
        # Spread records over last 30 days, more recent = more records
        days_ago = random.choices(
            range(30),
            weights=[30 - d for d in range(30)],  # recent days weighted higher
            k=1
        )[0]

        record = make_synthetic_record(tier, days_ago)

        cursor.execute(_INSERT_SQL, (
            record["query_id"], record["query_text"], record["timestamp"],
            record["has_code_block"], record["asks_high_precision"],
            record["asks_compare"], record["asks_reasoning"],
            record["has_json_like_text"], record["num_distinct_requests"],
            record["input_token_count"],
            record["ambiguity"], record["domain_specificity"],
            record["multi_step"], record["router_confidence"],
            record["classifier_rationale"],
            record["rule_score"], record["llm_score"], record["weighted_score"],
            record["model_routed"], record["model_final"],
            record["was_bumped"], record["bump_reason"],
            record["latency_ms"], record["input_tokens"], record["output_tokens"],
            record["cost_usd"], record["cost_if_always_large"], record["cost_saved"],
            record["quality_relevance"], record["quality_completeness"],
            record["quality_accuracy"], record["quality_score"],
            record["quality_rationale"],
            record["was_escalated"], record["escalation_reason"],
            record["quality_delta"],
            record["flagged_for_review"], record["flag_reason"],
        ))

        if (i + 1) % 100 == 0:
            conn.commit()
            print(f"  inserted {i + 1}/{len(TIER_DISTRIBUTION)}...")

        count += 1

    conn.commit()
    cursor.close()
    print(f"  ✅ {count} synthetic records inserted")
    return count


def verify(conn):
    """Print summary of what's in the database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            model_final AS tier,
            COUNT(*) AS total,
            ROUND(AVG(quality_score), 3) AS avg_quality,
            ROUND(AVG(cost_saved), 6) AS avg_cost_saved,
            ROUND(AVG(latency_ms), 0) AS avg_latency_ms,
            SUM(CAST(was_escalated AS INT)) AS escalations,
            SUM(CAST(was_bumped AS INT)) AS bumps
        FROM query_logs
        GROUP BY model_final
        ORDER BY model_final
    """)
    rows = cursor.fetchall()
    cursor.close()

    print("\n📊 Database summary:")
    print(f"  {'Tier':<10} {'Count':>6} {'Quality':>8} {'Saved':>12} {'Latency':>10} {'Escalated':>10} {'Bumped':>8}")
    print(f"  {'─'*70}")
    for row in rows:
        print(f"  {row[0]:<10} {row[1]:>6} {row[2]:>8.3f} {row[3]:>12.6f} {row[4]:>10.0f} {row[5]:>10} {row[6]:>8}")


if __name__ == "__main__":
    print("=" * 60)
    print("LLM Router — Synthetic Data Generator")
    print("=" * 60)

    conn = pymssql.connect(
        server=settings.AZURE_SQL_SERVER,
        user=settings.AZURE_SQL_USERNAME,
        password=settings.AZURE_SQL_PASSWORD,
        database=settings.AZURE_SQL_DATABASE,
    )
    print("✅ Connected to Azure SQL")

    synth_count = run_synthetic_inserts(conn)
    verify(conn)
    conn.close()

    print(f"\n✅ Done — {synth_count} synthetic records inserted")