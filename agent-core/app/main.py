from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.graph.agent_graph import compiled_graph
from app.graph.state import AgentState
from app.tools.vector_search import seed_knowledge_base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Seeding ChromaDB knowledge base on startup ...")
    try:
        await asyncio.to_thread(seed_knowledge_base)
        logger.info("ChromaDB ready.")
    except Exception as exc:
        logger.warning("ChromaDB seeding failed at startup (will retry on first request): %s", exc)
    yield
    logger.info("Shutting down enterprise-support-agent.")


app = FastAPI(
    title="Enterprise Support Agent",
    description=(
        "LangGraph-powered IT support ticket resolution engine. "
        "Classifies tickets, searches a ChromaDB knowledge base, queries "
        "ServiceNow, self-corrects on script errors, and escalates when needed."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class TicketRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1, max_length=64, description="Unique ticket identifier")
    description: str = Field(..., min_length=10, max_length=4096, description="Full ticket description")


class ResolutionTrace(BaseModel):
    ticket_id: str
    description: str
    severity: Optional[str] = None
    category: Optional[str] = None
    resolution: Optional[str] = None
    escalated: bool = False
    error_count: int = 0
    tool_calls: List[str] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    version: str
    mock_mode: bool


@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        mock_mode=_use_mock(),
    )


def _use_mock() -> bool:
    return settings.mock_llm or not (settings.openai_api_key or settings.anthropic_api_key)


@app.post(
    "/agent/resolve",
    response_model=ResolutionTrace,
    status_code=status.HTTP_200_OK,
    tags=["agent"],
    summary="Resolve a support ticket via the LangGraph agent",
)
async def resolve_ticket(request: TicketRequest) -> ResolutionTrace:
    """
    Submit a support ticket for agentic resolution.

    The LangGraph workflow will:
    1. analyze_ticket -- classify severity and category
    2. query_vector_db -- search ChromaDB knowledge base
    3. fetch_external_api -- check ServiceNow for related incidents
    4. self_correct -- retry with self-correction on script failures (max 3x)
    5. escalate_human -- escalate critical or unresolvable tickets
    6. resolve_ticket -- compose the final resolution response
    """
    logger.info("Received ticket: %s", request.ticket_id)

    initial_state: AgentState = {
        "ticket_id": request.ticket_id,
        "description": request.description,
        "category": None,
        "history": [],
        "tool_calls": [],
        "resolution": None,
        "escalated": False,
        "error_count": 0,
        "severity": None,
        "confidence": None,
        "external_data": None,
        "last_error": None,
    }

    try:
        final_state: AgentState = await asyncio.to_thread(compiled_graph.invoke, initial_state)
    except Exception as exc:
        logger.exception("Graph execution failed for ticket %s: %s", request.ticket_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent processing failed: {exc}",
        )

    return ResolutionTrace(
        ticket_id=final_state["ticket_id"],
        description=final_state["description"],
        severity=final_state.get("severity"),
        category=final_state.get("category"),
        resolution=final_state.get("resolution"),
        escalated=final_state.get("escalated", False),
        error_count=final_state.get("error_count", 0),
        tool_calls=final_state.get("tool_calls", []),
        history=final_state.get("history", []),
    )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)
