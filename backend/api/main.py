"""
FastAPI backend for LLM Router dashboard.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import pymssql

from config.settings import settings

app = FastAPI(title="LLM Router API", version="1.0.0")

# Allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Lazy pipeline init
# ---------------------------------------------------------------------------
_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        from main import run_query
        _pipeline = run_query
    return _pipeline

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
# Models
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
def run_query(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    try:
        run = get_pipeline()
        result = run(req.query.strip())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/overview")
def analytics_overview():
    try:
        rows = qdb("""
            SELECT
                COUNT(*)            AS total_queries,
                SUM(cost_saved)     AS total_saved,
                AVG(quality_score)  AS avg_quality,
                AVG(latency_ms)     AS avg_latency
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
                SUM(total_queries)      AS queries,
                AVG(avg_quality_score)  AS avg_quality
            FROM quality_analysis
            GROUP BY query_date
            ORDER BY query_date DESC
        """)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))