# LLM Router

A query routing system built on Azure AI Foundry that sends simple queries to cheap models and complex ones to powerful models automatically, based on what the query actually needs.

The core idea: most queries hitting an LLM in production don't need `gpt-4o`. Routing them intelligently saves significant cost with minimal quality trade-off.

---

## What it does

Every incoming query goes through two stages before a model is called:

**Stage 1  Rule extraction** scans the query with regex patterns and pulls out 7 signals: does it have a code block, is it asking for a comparison, does it need step-by-step reasoning, how many distinct things is it asking for, etc. This runs in under 1ms and costs nothing.

**Stage 2  LLM classification** sends the query plus those rule signals to a small cheap model (`gpt-4o-mini`) to score three things rules can't reliably detect: how ambiguous the query is, how specialised the domain is, and whether answering it requires multi-step reasoning.

Those signals get combined into a single weighted score (55% rules, 45% LLM), which determines the tier:

| Score | Tier | Model |
|-------|------|-------|
| < 0.15 | Small | gpt-4o-mini |
| 0.15 – 0.32 | Medium | o3-mini |
| > 0.32 | Large | gpt-4o |

If the classifier isn't confident in its own scores (below 0.60), the query gets bumped up one tier automatically rather than risk under-routing it.

After the model responds, a quality evaluator scores the response on relevance, completeness, and accuracy. If the score falls below 0.65, the system retries on the next tier up and logs both attempts.

Everything  every score, every routing decision, every cost, every quality evaluation  gets written to Azure SQL. Five analytical views sit on top of that table and feed a real-time dashboard.

---

## Stack

**Backend**
- Python 3.10
- FastAPI  REST API consumed by the frontend
- Azure AI Foundry  model deployments (gpt-4o-mini, o3-mini, gpt-4o)
- Azure OpenAI SDK
- Azure SQL Database  query log storage
- pymssql  SQL driver
- Pydantic  data validation throughout the pipeline

**Frontend**
- Next.js 15 (App Router)
- TypeScript
- Recharts  quality trend + volume charts
- react-markdown  renders model responses

---

## Project structure

```
backend/
├── ingestion/
│   ├── rule_extractor.py      7 regex-based complexity signals
│   ├── llm_classifier.py      Azure OpenAI classifier, scores ambiguity/domain/multi-step
│   ├── models.py              RuleFeatures, LLMClassifierScores, IngestionResult
│   └── pipeline.py            Orchestrates both stages
│
├── routing/
│   ├── feature_merger.py      Normalises all features to 0–1
│   ├── weighted_scorer.py     55/45 rule/LLM weighted score
│   ├── router.py              Threshold logic + confidence bump
│   ├── models.py              ModelTier, RoutingDecision, NormalisedFeatures
│   └── pipeline.py            FeatureMerger → WeightedScorer → Router
│
├── response/
│   ├── response_generator.py  Calls the routed Azure model, tracks cost + latency
│   ├── quality_evaluator.py   LLM eval for Small/Medium, rule-based for Large
│   ├── escalation_engine.py   Retries on next tier if quality < 0.65
│   ├── models.py              ModelResponse, QualityScores, FinalResponse
│   └── pipeline.py            Generator → Evaluator → Escalation
│
├── data/
│   ├── metrics_logger.py      Writes one record per query to Azure SQL
│   ├── models.py              QueryLogRecord  typed schema
│   ├── schema.sql             Table definition (run once in Azure SQL)
│   └── sql/                   5 analytical views for the dashboard
│       ├── stg_queries.sql
│       ├── routing_summary.sql
│       ├── cost_analysis.sql
│       ├── quality_analysis.sql
│       ├── escalation_analysis.sql
│       └── model_comparison.sql
│
├── api/
│   └── main.py                FastAPI  5 endpoints consumed by Next.js
│
├── scripts/
│   ├── seed_data.py           Generates 10k synthetic records for the dashboard
│   └── seed_real.py           Runs 75 real queries through the full pipeline
│
├── tests/
│   ├── test_ingestion.py      31 tests  rule extractor + classifier interface
│   ├── test_routing.py        27 tests  merger, scorer, router, pipeline
│   └── test_response.py       19 tests  generator, evaluator, escalation
│
├── config/settings.py         All env vars loaded once here
├── requirements.txt
└── .env.example

frontend/
├── app/
│   ├── page.tsx               Tab switching  Dashboard / Live Query
│   ├── layout.tsx
│   └── globals.css            Dark theme base styles
└── components/
    ├── AnalyticsPanel.tsx     KPI cards, tier breakdown, charts, cost table
    └── QueryPanel.tsx         Query input, routing decision, quality bars, answer
```

---

## Setup

### Prerequisites
- Python 3.10+
- Node.js 20+
- Azure AI Foundry project with three model deployments
- Azure SQL Database

### Azure setup

Deploy three models in Azure AI Foundry Studio:

| Deployment name | Model |
|-----------------|-------|
| `gpt-4o-mini` | gpt-4o-mini |
| `o3-large` | o3-mini |
| `gpt-4o-medium` | gpt-4o |

Run `data/schema.sql` in Azure SQL Query Editor to create the `query_logs` table, then run the five SQL files in `data/sql/` in order (starting with `stg_queries.sql`).

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-12-01-preview

AZURE_DEPLOYMENT_SMALL=gpt-4o-mini
AZURE_DEPLOYMENT_MEDIUM=o3-large
AZURE_DEPLOYMENT_LARGE=gpt-4o-medium

ROUTER_SMALL_MAX=0.15
ROUTER_MEDIUM_MAX=0.32
ROUTER_CONFIDENCE_BUMP_THRESHOLD=0.65

AZURE_SQL_SERVER=your-server.database.windows.net
AZURE_SQL_DATABASE=your-database-name
AZURE_SQL_USERNAME=your-username
AZURE_SQL_PASSWORD=your-password
```

Seed the database with synthetic data:

```bash
export PYTHONPATH=.
python scripts/seed_data.py
```

Optionally run real queries through the pipeline (takes 15–20 mins):

```bash
python scripts/seed_real.py
```

Start the API:

```bash
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

---

## Running tests

```bash
cd backend
export PYTHONPATH=.
pytest tests/ -v
```

77 tests, all offline  no Azure credentials needed. The LLM classifier and Azure model calls are mocked throughout.

---

## Dashboard

The dashboard loads with the Analytics tab by default, showing data from the seeded query logs.

**Dashboard tab** shows:
- Total cost saved vs always routing to the large model
- Query volume and quality scores broken down by tier
- Quality trend over the last 14 days
- Full cost breakdown table with latency and quality per dollar metrics

**Live Query tab** lets you run any query through the full pipeline in real time and see exactly how the routing decision was made  which rule features fired, what the LLM scored, why it landed on a particular tier, and how the response was evaluated.

---

## Key design decisions

**Why 60/40 rule/LLM weighting?** Rules are deterministic and free  they should carry more weight. The LLM classifier adds signal for things rules genuinely can't detect (ambiguity, domain depth) but it's fallible, so it gets less weight.

**Why use a small model to classify complex queries?** Classification is easier than answering. A small model doesn't need to know how to derive Black-Scholes  it just needs to recognise that the query involves specialised finance and multi-step reasoning. That's a much simpler task.

**Why skip LLM evaluation for Large tier responses?** The cost of evaluating a 2000-token Large response with another LLM call starts to eat into the savings. Large responses pass a length and structure check instead  if the model produced a substantial, structured answer, it's almost certainly acceptable.

**Why separate rule features from LLM scores in the prompt?** The classifier prompt explicitly shows it the rule features so it doesn't re-score what rules already caught. This keeps the LLM scores additive rather than redundant.

---

## Cost results (10k query sample)

Based on synthetic data calibrated to real Azure pricing:

| Tier | Queries | Share | Total Cost | Cost Saved |
|------|---------|-------|------------|------------|
| Small (gpt-4o-mini) | ~4,000 | 40% | ~$2 | ~$220 |
| Medium (o3-mini) | ~4,000 | 40% | ~$56 | ~$170 |
| Large (gpt-4o) | ~2,000 | 20% | ~$180 | $0 |

Routing 80% of queries away from the large model saves roughly **$390 per 10,000 queries** while maintaining average quality scores above 0.85.
