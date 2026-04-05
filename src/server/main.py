"""
Production FastAPI server for Local Deep Researcher.
Replaces `langgraph dev` with proper endpoints, background job execution,
request validation, error handling, and health checks.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Path setup — allow importing ollama_deep_researcher from the src/ directory
# regardless of how the server is launched.
# ---------------------------------------------------------------------------
_src_dir = os.path.join(os.path.dirname(__file__), "..")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory run store (will be replaced with PostgreSQL later)
# ---------------------------------------------------------------------------


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


_runs: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Local Deep Researcher API server")
    # Import the graph at startup to surface config errors early
    from ollama_deep_researcher.graph import graph  # noqa: F401

    logger.info("Research graph loaded successfully")
    yield
    logger.info("Shutting down Local Deep Researcher API server")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Local Deep Researcher API",
    description="Production API for AI-powered deep research",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://research.splitsoft.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Include auth routes
# ---------------------------------------------------------------------------

from server.routes.auth import router as auth_router  # noqa: E402

app.include_router(auth_router)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500, description="Research topic")
    max_loops: int = Field(
        default=3, ge=1, le=10, description="Number of research iterations"
    )
    search_api: Optional[str] = Field(
        default=None, description="Search API override (tavily, duckduckgo, perplexity, searxng)"
    )
    model: Optional[str] = Field(default=None, description="LLM model name override")
    llm_provider: Optional[str] = Field(
        default=None, description="LLM provider override (ollama, lmstudio)"
    )


class ResearchRunSummary(BaseModel):
    run_id: str
    topic: str
    status: RunStatus
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class ResearchRunDetail(ResearchRunSummary):
    result: Optional[str] = None
    sources: Optional[list[str]] = None
    loop_count: Optional[int] = None


class ResearchStartResponse(BaseModel):
    run_id: str
    status: RunStatus
    message: str


# ---------------------------------------------------------------------------
# Background research runner
# ---------------------------------------------------------------------------


async def _run_research(run_id: str, topic: str, config: dict[str, Any]) -> None:
    """Execute the research graph in a background thread and store the result."""
    from ollama_deep_researcher.graph import graph

    _runs[run_id]["status"] = RunStatus.RUNNING

    try:
        # graph.invoke() is synchronous — run in a thread to avoid blocking
        result = await asyncio.to_thread(
            graph.invoke,
            {"research_topic": topic},
            {"configurable": config},
        )

        _runs[run_id].update(
            {
                "status": RunStatus.COMPLETED,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": result.get("running_summary", ""),
                "sources": result.get("sources_gathered", []),
                "loop_count": config.get("max_web_research_loops", 3),
            }
        )
        logger.info("Research run %s completed", run_id)

    except Exception:
        logger.exception("Research run %s failed", run_id)
        _runs[run_id].update(
            {
                "status": RunStatus.FAILED,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": "Research failed — check server logs for details",
            }
        )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "llm_driver": os.getenv("LLM_DRIVER", "ollama"),
    }


# ---------------------------------------------------------------------------
# Research endpoints
# ---------------------------------------------------------------------------


@app.post("/api/research", response_model=ResearchStartResponse, status_code=202)
async def start_research(req: ResearchRequest):
    """Start a new research run. Returns immediately; research runs in the background."""
    run_id = str(uuid.uuid4())

    # Build configurable dict for the graph
    configurable: dict[str, Any] = {
        "max_web_research_loops": req.max_loops,
    }
    if req.search_api:
        configurable["search_api"] = req.search_api
    if req.model:
        configurable["local_llm"] = req.model
    if req.llm_provider:
        configurable["llm_provider"] = req.llm_provider

    _runs[run_id] = {
        "run_id": run_id,
        "topic": req.topic,
        "status": RunStatus.PENDING,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "result": None,
        "sources": None,
        "loop_count": None,
        "error": None,
    }

    # Fire-and-forget background task
    asyncio.create_task(_run_research(run_id, req.topic, configurable))

    return ResearchStartResponse(
        run_id=run_id,
        status=RunStatus.PENDING,
        message="Research started — poll GET /api/research/{run_id} for status",
    )


@app.get("/api/research/{run_id}", response_model=ResearchRunDetail)
async def get_research_status(run_id: str):
    """Get the current status and details of a research run."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")
    return ResearchRunDetail(**run)


@app.get("/api/research/{run_id}/result")
async def get_research_result(run_id: str):
    """Get only the final result of a completed research run."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    if run["status"] == RunStatus.PENDING or run["status"] == RunStatus.RUNNING:
        return JSONResponse(
            status_code=202,
            content={
                "run_id": run_id,
                "status": run["status"],
                "message": "Research is still in progress",
            },
        )

    if run["status"] == RunStatus.FAILED:
        raise HTTPException(status_code=500, detail=run.get("error", "Research failed"))

    return {
        "run_id": run_id,
        "status": run["status"],
        "topic": run["topic"],
        "result": run["result"],
        "sources": run["sources"],
    }


@app.get("/api/research", response_model=list[ResearchRunSummary])
async def list_research_runs():
    """List all research runs."""
    return [
        ResearchRunSummary(
            run_id=r["run_id"],
            topic=r["topic"],
            status=r["status"],
            created_at=r["created_at"],
            completed_at=r["completed_at"],
            error=r["error"],
        )
        for r in sorted(_runs.values(), key=lambda r: r["created_at"], reverse=True)
    ]


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "path": str(request.url.path)},
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error("Internal server error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )
