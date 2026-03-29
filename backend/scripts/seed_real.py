"""
Runs 75 real queries through the full pipeline and logs them to Azure SQL.
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

import logging
logging.basicConfig(level=logging.WARNING)  # suppress verbose HTTP logs

from ingestion.pipeline import IngestionPipeline
from routing.pipeline import RoutingPipeline
from response.pipeline import ResponsePipeline
from data.metrics_logger import MetricsLogger

REAL_QUERIES = {
    "small": [
        # General knowledge
        "What does API stand for?",
        "What year was Python created?",
        "What is a REST API?",
        "What does SQL stand for?",
        "What is a variable in programming?",
        "What does HTTP stand for?",
        "What is a database?",
        "What is Git?",
        "What does IDE stand for?",
        "What is cloud computing?",
        "What is machine learning?",
        "What is Docker?",
        "What is an algorithm?",
        "What does CPU stand for?",
        "What is open source software?",
        "What is a framework in programming?",
        "What is JSON?",
        "What does OOP stand for?",
        "What is a compiler?",
        "What is agile methodology?",
        "What is a binary tree?",
        "What does DNS stand for?",
        "What is a container in computing?",
        "What is version control?",
        "What is an IP address?",
    ],
    "medium": [
        # Technical comparisons and explanations
        "Should I use Redis or Postgres for storing session data?",
        "What are the pros and cons of microservices vs monolithic architecture?",
        "Explain how database indexing works and when to use it",
        "What is the difference between supervised and unsupervised learning?",
        "How does JWT authentication work?",
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
        "Explain how HTTPS works end to end",
        "What is the difference between horizontal and vertical scaling?",
        "How does a CDN improve website performance?",
        "Explain how connection pooling works in databases",
        "What is eventual consistency and when should you use it?",
        "How does a message queue improve system reliability?",
    ],
    "large": [
        # Complex multi-step reasoning and implementation
        "Derive the Black-Scholes equation from first principles using Ito's lemma",
        "Explain the mathematical intuition behind attention mechanisms in transformers then implement scaled dot-product attention in Python",
        "I am building a real-time fraud detection system processing 100k transactions per second walk me through the full architecture on Azure",
        "Design a medallion architecture pipeline for an e-commerce platform with exactly what transformations happen at each layer",
        "Explain how to implement a distributed rate limiter using Redis with sliding window algorithm and provide the full implementation",
        "Design a real-time recommendation system for 10 million users including model selection feature engineering and serving infrastructure",
        "Implement a distributed transaction system using two-phase commit protocol with failure handling and recovery",
        "Explain and implement a B-tree data structure from scratch in Python including insert delete and search operations",
        "Design a scalable notification system handling 1 million messages per second across push email and SMS channels",
        "Walk me through designing a multi-region active-active database architecture with conflict resolution",
        "Implement a custom LRU cache with O(1) get and put operations then extend it to support TTL expiration",
        "Design a real-time bidding system for digital advertising that handles 500k bid requests per second",
        "Explain how to build a vector similarity search system from scratch using HNSW algorithm",
        "Implement a distributed consensus algorithm using Raft and explain each phase in detail",
        "Design a data pipeline that ingests 10TB of daily clickstream data processes it and serves it to a dashboard with under 5 minute latency",
        "Build a complete RAG system from scratch including document chunking embedding storage retrieval and generation with evaluation metrics",
        "Explain and implement backpropagation through a transformer layer including multi-head attention and feed-forward network",
        "Design a globally distributed key-value store with tunable consistency guarantees similar to DynamoDB",
        "Implement a columnar storage engine in Python with run-length encoding and dictionary compression",
        "Walk me through building a real-time feature store for machine learning with both online and offline serving paths",
        "Design a fault-tolerant stream processing system using exactly-once semantics across Kafka and a stateful processor",
        "Explain and implement the MVCC concurrency control mechanism used in PostgreSQL",
        "Build a complete observability platform covering metrics traces and logs with anomaly detection",
        "Design a zero-downtime database migration strategy for a table with 500 million rows in production",
        "Implement a circuit breaker pattern with exponential backoff and explain how it prevents cascade failures",
    ],
}


if __name__ == "__main__":
    print("=" * 60)
    print("LLM Router — Real Query Seeder")
    print("=" * 60)
    total = sum(len(q) for q in REAL_QUERIES.values())
    print(f"Running {total} real queries through the full pipeline...")
    print("This will take 15-25 minutes due to API calls.\n")
    print("Large tier queries take 30+ seconds each — be patient.\n")

    ingestion = IngestionPipeline()
    routing   = RoutingPipeline()
    response  = ResponsePipeline()
    logger    = MetricsLogger()

    count   = 0
    failed  = 0

    for tier, queries in REAL_QUERIES.items():
        print(f"\n[{tier.upper()} TIER]")
        for query in queries:
            try:
                print(f"  → {query[:60]}...")
                i = ingestion.run(query)
                r = routing.run(i)
                f = response.run(query, r)
                query_id = logger.log(i, r, f)
                print(f"     tier={r.final_tier.value}  "
                      f"score={r.weighted_score:.4f}  "
                      f"quality={f.quality_score:.2f}  "
                      f"cost=${f.cost_usd:.6f}  "
                      f"saved=${f.cost_saved:.6f}")
                count += 1
            except Exception as e:
                print(f"     ❌ Failed: {e}")
                failed += 1

    logger.close()

    print(f"\n{'=' * 60}")
    print(f"✅ Done — {count}/{total} queries logged successfully")
    if failed:
        print(f"❌ {failed} failed")
    print(f"{'=' * 60}")
