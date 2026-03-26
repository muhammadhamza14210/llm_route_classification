# test_manual.py
from ingestion.rule_extract import RuleExtractor

extractor = RuleExtractor()

queries = [
    # Ambiguous — could be simple or complex
    "help me with my code",

    # Looks simple but is actually domain-specific
    "what's the difference between L1 and L2 regularization",

    # Multi-request but no question marks
    "summarize this, find the key themes, then suggest improvements",

    # Precision language buried in a casual query
    "can you give me the exact steps to deploy a docker container",

    # Code block mid-sentence
    "why does this fail ```SELECT * FROM users WHERE id = 1```",

    # Very long query — tests token count scaling
    "I am building a recommendation system for an e-commerce platform and I need to understand the trade-offs between collaborative filtering and content-based filtering approaches, specifically in terms of cold start problems, scalability, and real-time serving latency",

    # JSON but also asking for reasoning
    "explain what is wrong with this payload {'user': null, 'token': '', 'role': 'admin'} and how should I fix it",

    # Looks complex but is actually simple
    "what year was Python created",

    # Multiple question marks
    "what is overfitting? how do I detect it? what are the solutions?",

    # Compare hidden in natural language
    "should I use Redis or Postgres for storing session data",
]

for q in queries:
    f = extractor.extract(q)
    print(f"\nQuery: {q}")
    print(f"  code_block={f.has_code_block}  precision={f.asks_high_precision}")
    print(f"  compare={f.asks_compare}  reasoning={f.asks_reasoning}")
    print(f"  json={f.has_json_like_text}  requests={f.num_distinct_requests}")
    print(f"  tokens={f.input_token_count}")