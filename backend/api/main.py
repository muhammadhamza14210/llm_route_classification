"""
FastAPI backend for LLM Router dashboard.
"""

import sys
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import pymssql

from config.settings import settings

app = FastAPI(title="LLM Router API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Lazy pipeline init 
# ---------------------------------------------------------------------------
_ingestion = None
_routing   = None
_response  = None
_metrics   = None


def get_pipeline():
    global _ingestion, _routing, _response, _metrics
    if _ingestion is None:
        from ingestion.pipeline import IngestionPipeline
        from routing.pipeline import RoutingPipeline
        from response.pipeline import ResponsePipeline
        from data.metrics_logger import MetricsLogger
        _ingestion = IngestionPipeline()
        _routing   = RoutingPipeline()
        _response  = ResponsePipeline()
        _metrics   = MetricsLogger()
    return _ingestion, _routing, _response, _metrics


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------
def qdb(sql: str) -> list[dict]:
    conn = pymssql.connect(
        server=settings.AZURE_SQL_SERVER,
        user=settings.AZURE_SQL_USERNAME,
        password=settings.AZURE_SQL_PASSWORD,
        database=settings.AZURE_SQL_DATABASE,
    )
    df = pd.read_sql(sql, conn)
    conn.close()
    return df.to_dict("records")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query")
def run_query_endpoint(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    try:
        ingestion, routing, response, metrics = get_pipeline()
        query = req.query.strip()

        ingestion_result = ingestion.run(query)
        routing_result   = routing.run(ingestion_result)
        response_result  = response.run(query, routing_result)
        query_id         = metrics.log(ingestion_result, routing_result, response_result)

        return {
            "query_id":             query_id,
            "query":                query,

            # Rule features
            "rule_features":        ingestion_result.rule_features.model_dump(),

            # LLM scores
            "llm_scores":           ingestion_result.llm_scores.model_dump(),

            # Routing
            "weighted_score":       routing_result.weighted_score,
            "rule_score":           routing_result.rule_score,
            "llm_score":            routing_result.llm_score,
            "tier":                 routing_result.tier.value,
            "final_tier":           routing_result.final_tier.value,
            "was_bumped":           routing_result.was_bumped,
            "bump_reason":          routing_result.bump_reason,

            # Response
            "content":              response_result.content,
            "model_final":          response_result.model_final.value,
            "latency_ms":           response_result.latency_ms,
            "input_tokens":         response_result.input_tokens,
            "output_tokens":        response_result.output_tokens,

            # Cost
            "cost_usd":             response_result.cost_usd,
            "cost_if_large":        response_result.cost_if_always_large,
            "cost_saved":           response_result.cost_saved,

            # Quality
            "quality_score":        response_result.quality_score,
            "quality_relevance":    response_result.quality_scores.relevance,
            "quality_completeness": response_result.quality_scores.completeness,
            "quality_accuracy":     response_result.quality_scores.accuracy,
            "quality_rationale":    response_result.quality_scores.rationale,

            # Escalation
            "was_escalated":        response_result.was_escalated,
            "escalation":           response_result.escalation.model_dump() if response_result.escalation else None,
            "flagged_for_review":   response_result.flagged_for_review,
            "flag_reason":          response_result.flag_reason,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/overview")
def analytics_overview():
    try:
        rows = qdb("""
            SELECT
                COUNT(*)         AS total_queries,
                SUM(cost_saved)  AS total_saved,
                AVG(quality_score) AS avg_quality,
                AVG(latency_ms)  AS avg_latency
            FROM query_logs
        """)
        return rows[0] if rows else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/routing")
def analytics_routing():
    try:
        return qdb("SELECT * FROM routing_summary")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/cost")
def analytics_cost():
    try:
        return qdb("SELECT * FROM model_comparison")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/quality")
def analytics_quality():
    try:
        return qdb("""
            SELECT TOP 14
                query_date,
                SUM(total_queries)     AS queries,
                AVG(avg_quality_score) AS avg_quality
            FROM quality_analysis
            GROUP BY query_date
            ORDER BY query_date DESC
        """)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))