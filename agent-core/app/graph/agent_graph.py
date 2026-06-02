from __future__ import annotations
import logging
from typing import Literal
from langgraph.graph import END, StateGraph
from app.graph.nodes import (
    analyze_ticket, escalate_human, fetch_external_api,
    query_vector_db, resolve_ticket, self_correct,
)
from app.graph.state import AgentState

logger = logging.getLogger(__name__)


def _route_after_analyze(state: AgentState) -> Literal["escalate_human", "query_vector_db"]:
    if state.get("severity") == "critical":
        logger.info("Routing -> escalate_human (critical severity)")
        return "escalate_human"
    return "query_vector_db"


def _route_after_query_db(state: AgentState) -> Literal["resolve_ticket", "fetch_external_api"]:
    confidence = state.get("confidence") or 0.0
    if confidence > 0.75:
        logger.info("Routing -> resolve_ticket (confidence=%.3f)", confidence)
        return "resolve_ticket"
    logger.info("Routing -> fetch_external_api (confidence=%.3f < 0.75)", confidence)
    return "fetch_external_api"


def _route_after_fetch(state: AgentState) -> Literal["resolve_ticket", "self_correct"]:
    ext = state.get("external_data") or {}
    if ext.get("servicenow_incident"):
        return "resolve_ticket"
    logger.info("Routing -> self_correct (no ServiceNow data found)")
    return "self_correct"


def _route_after_self_correct(state: AgentState) -> Literal["escalate_human", "fetch_external_api"]:
    if (state.get("error_count") or 0) >= 3:
        logger.info("Routing -> escalate_human (max retries reached)")
        return "escalate_human"
    return "fetch_external_api"


def build_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("analyze_ticket", analyze_ticket)
    graph.add_node("query_vector_db", query_vector_db)
    graph.add_node("fetch_external_api", fetch_external_api)
    graph.add_node("self_correct", self_correct)
    graph.add_node("escalate_human", escalate_human)
    graph.add_node("resolve_ticket", resolve_ticket)
    graph.set_entry_point("analyze_ticket")
    graph.add_conditional_edges("analyze_ticket", _route_after_analyze,
        {"escalate_human": "escalate_human", "query_vector_db": "query_vector_db"})
    graph.add_conditional_edges("query_vector_db", _route_after_query_db,
        {"resolve_ticket": "resolve_ticket", "fetch_external_api": "fetch_external_api"})
    graph.add_conditional_edges("fetch_external_api", _route_after_fetch,
        {"resolve_ticket": "resolve_ticket", "self_correct": "self_correct"})
    graph.add_conditional_edges("self_correct", _route_after_self_correct,
        {"escalate_human": "escalate_human", "fetch_external_api": "fetch_external_api"})
    graph.add_edge("escalate_human", END)
    graph.add_edge("resolve_ticket", END)
    return graph.compile()


compiled_graph = build_agent_graph()
