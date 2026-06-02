from __future__ import annotations
import json
import logging
from typing import Any, Dict

from app.config import settings
from app.graph.state import AgentState
from app.tools.code_executor import execute_script_safely, generate_corrected_script, generate_diagnostic_script
from app.tools.external_api import create_escalation_record, fetch_servicenow_incident
from app.tools.vector_search import search_knowledge_base

logger = logging.getLogger(__name__)


def _use_mock() -> bool:
    return settings.mock_llm or not (settings.openai_api_key or settings.anthropic_api_key)


def _mock_analyze(description: str) -> Dict[str, Any]:
    desc = description.lower()
    if any(kw in desc for kw in {"outage", "breach", "critical", "production down", "ransomware", "hack", "attack"}):
        severity = "critical"
    elif any(kw in desc for kw in {"not working", "cannot", "failed", "broken", "error", "urgent", "crash"}):
        severity = "high"
    else:
        severity = "medium"
    category_map = [
        (["password", "login", "account", "lockout", "mfa", "2fa"], "account"),
        (["vpn", "wifi", "internet", "network", "connection", "rdp"], "network"),
        (["printer", "laptop", "hardware", "disk", "drive", "usb", "bsod", "memory"], "hardware"),
        (["outlook", "teams", "email", "software", "install", "license", "calendar"], "software"),
        (["access", "permission", "security", "malware", "antivirus", "breach"], "security"),
        (["server", "database", "infrastructure", "timeout"], "infrastructure"),
    ]
    category = "general_it"
    for keywords, cat in category_map:
        if any(kw in desc for kw in keywords):
            category = cat
            break
    return {"severity": severity, "category": category, "intent": f"User needs support for: {description[:80]}"}


def _llm_analyze(description: str, ticket_id: str) -> Dict[str, Any]:
    if _use_mock():
        return _mock_analyze(description)
    try:
        if settings.openai_api_key:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            prompt = (
                "You are an IT support analyst. Analyze this support ticket.\n"
                f"Ticket ID: {ticket_id}\nDescription: {description}\n\n"
                'Return ONLY JSON: {"severity":"<critical|high|medium|low>",'
                '"category":"<infrastructure|security|software|hardware|account|network>",'
                '"intent":"<one sentence>"}'
            )
            resp = client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}],
                temperature=0.1, response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        if settings.anthropic_api_key:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            prompt = (
                "You are an IT support analyst. Analyze this support ticket.\n"
                f"Ticket ID: {ticket_id}\nDescription: {description}\n\n"
                'Return ONLY JSON: {"severity":"<critical|high|medium|low>",'
                '"category":"<infrastructure|security|software|hardware|account|network>",'
                '"intent":"<one sentence>"}'
            )
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            return json.loads(text[text.find("{"):text.rfind("}") + 1])
    except Exception as exc:
        logger.warning("LLM analyze failed, using mock: %s", exc)
    return _mock_analyze(description)


def _llm_compose_resolution(description: str, kb_results: list, external_data, category: str) -> str:
    ctx = []
    if kb_results:
        ctx.append("Knowledge Base:")
        for r in kb_results[:2]:
            ctx.append(f"  - {r['document'][:250]}")
    if external_data:
        if external_data.get("title"):
            ctx.append(f"Related Incident: {external_data['title']}")
        if external_data.get("solution"):
            ctx.append(f"Known Solution: {external_data['solution']}")
        if external_data.get("workaround"):
            ctx.append(f"Workaround: {external_data['workaround']}")
    context = "\n".join(ctx) or "No additional context available."
    if _use_mock():
        if kb_results:
            top = kb_results[0]["document"][:300]
            return (
                f"We have identified a resolution for your {category} issue. "
                f"{top} "
                "Please follow these steps and contact IT helpdesk at ext. 4357 if the issue persists."
            )
        return (
            f"Your {category} support request has been processed. "
            "Our AI agent has analysed your ticket and queued it for resolution. "
            "Please allow up to 4 business hours for changes to take effect. "
            "Contact IT helpdesk at ext. 4357 if you need immediate assistance."
        )
    prompt = (
        f"Write a professional IT support resolution (2-4 sentences).\n"
        f"Issue: {description}\nCategory: {category}\n\n{context}"
    )
    try:
        if settings.openai_api_key:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.3)
            return resp.choices[0].message.content
        if settings.anthropic_api_key:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=512,
                messages=[{"role": "user", "content": prompt}])
            return resp.content[0].text
    except Exception as exc:
        logger.warning("LLM resolution failed: %s", exc)
    return (
        f"Your {category} issue has been processed. "
        "Please follow the standard resolution steps. "
        "Contact IT helpdesk at ext. 4357 if the problem persists."
    )


# ── Graph Nodes ───────────────────────────────────────────────────────────────

def analyze_ticket(state: AgentState) -> Dict[str, Any]:
    """Classify ticket severity and intent using LLM (or mock)."""
    analysis = _llm_analyze(state["description"], state["ticket_id"])
    logger.info("analyze_ticket: id=%s severity=%s category=%s",
                state["ticket_id"], analysis.get("severity"), analysis.get("category"))
    return {
        "severity": analysis.get("severity", "medium"),
        "category": analysis.get("category", "general_it"),
        "history": [{"node": "analyze_ticket",
                     "input": {"ticket_id": state["ticket_id"], "description": state["description"][:100]},
                     "output": analysis}],
        "tool_calls": ["analyze_ticket"],
    }


def query_vector_db(state: AgentState) -> Dict[str, Any]:
    """Search ChromaDB for similar issues and known solutions."""
    try:
        results = search_knowledge_base(state["description"], n_results=3)
        confidence = max(0.0, round(1.0 - results[0]["distance"], 4)) if results else 0.0
        logger.info("query_vector_db: %d results, confidence=%.3f", len(results), confidence)
        return {
            "confidence": confidence,
            "external_data": {"kb_results": results},
            "history": [{"node": "query_vector_db",
                         "input": {"query": state["description"][:100]},
                         "output": {"num_results": len(results), "confidence": confidence,
                                    "top_match": results[0]["document"][:100] if results else None}}],
            "tool_calls": ["query_vector_db"],
        }
    except Exception as exc:
        logger.error("query_vector_db error: %s", exc)
        return {
            "confidence": 0.0, "external_data": {"kb_results": []},
            "history": [{"node": "query_vector_db", "input": {"query": state["description"][:100]},
                         "output": {"error": str(exc)}}],
            "tool_calls": ["query_vector_db"],
        }


def fetch_external_api(state: AgentState) -> Dict[str, Any]:
    """Fetch related incident data from mock ServiceNow API."""
    incident = fetch_servicenow_incident(state["ticket_id"])
    logger.info("fetch_external_api: ticket=%s found=%s", state["ticket_id"], incident is not None)
    existing = dict(state.get("external_data") or {})
    existing["servicenow_incident"] = incident
    return {
        "external_data": existing,
        "history": [{"node": "fetch_external_api",
                     "input": {"ticket_id": state["ticket_id"]},
                     "output": {"found": incident is not None,
                                "incident_id": (incident or {}).get("incident_id")}}],
        "tool_calls": ["fetch_external_api"],
    }


def self_correct(state: AgentState) -> Dict[str, Any]:
    """Self-correction loop: generate diagnostic script, catch failures, fix and retry (max 3x)."""
    attempt = state["error_count"] + 1
    last_error = state.get("last_error")
    if last_error:
        base_script = generate_diagnostic_script(state["description"])
        script = generate_corrected_script(base_script, last_error)
        logger.info("self_correct: attempt %d -- using corrected script", attempt)
    else:
        base_script = generate_diagnostic_script(state["description"])
        script = base_script + "\nresult = _undefined_diagnostic_function()\n"
        logger.info("self_correct: attempt %d -- running script with simulated bug", attempt)
    success, output = execute_script_safely(script)
    logger.info("self_correct: attempt=%d success=%s", attempt, success)
    new_last_error = None if success else output
    note = (f"Attempt {attempt} succeeded. Output: {output[:150]}" if success
            else f"Attempt {attempt} failed: {output[:150]}")
    return {
        "error_count": attempt, "last_error": new_last_error,
        "history": [{"node": "self_correct",
                     "input": {"attempt": attempt, "had_prior_error": last_error is not None},
                     "output": {"success": success, "note": note}}],
        "tool_calls": [f"self_correct_attempt_{attempt}"],
    }


def escalate_human(state: AgentState) -> Dict[str, Any]:
    """Escalate ticket to human L2/L3 support."""
    reason = (
        "ticket classified as critical severity" if state.get("severity") == "critical"
        else f"automated resolution failed after {state['error_count']} attempt(s)"
    )
    escalation = create_escalation_record(
        ticket_id=state["ticket_id"], description=state["description"],
        severity=state.get("severity", "unknown"), reason=reason,
    )
    logger.info("escalate_human: ticket=%s escalation=%s team=%s",
                state["ticket_id"], escalation.get("escalation_id"), escalation.get("assigned_team"))
    resolution = (
        f"Your ticket {state['ticket_id']} has been escalated to our "
        f"{escalation['assigned_team']} team (ref: {escalation['escalation_id']}). "
        f"Expected SLA: {escalation['sla_minutes']} minutes. "
        "You will receive an email confirmation once an engineer is assigned."
    )
    return {
        "escalated": True, "resolution": resolution,
        "history": [{"node": "escalate_human",
                     "input": {"reason": reason, "severity": state.get("severity")},
                     "output": escalation}],
        "tool_calls": ["escalate_human"],
    }


def resolve_ticket(state: AgentState) -> Dict[str, Any]:
    """Compose the final resolution response."""
    ext = state.get("external_data") or {}
    kb_results = ext.get("kb_results", [])
    servicenow_data = ext.get("servicenow_incident")
    resolution = _llm_compose_resolution(
        description=state["description"], kb_results=kb_results,
        external_data=servicenow_data, category=state.get("category", "general_it"),
    )
    logger.info("resolve_ticket: ticket=%s resolution_len=%d", state["ticket_id"], len(resolution))
    return {
        "resolution": resolution,
        "history": [{"node": "resolve_ticket",
                     "input": {"kb_results_count": len(kb_results),
                               "has_servicenow_data": servicenow_data is not None},
                     "output": {"resolution_chars": len(resolution)}}],
        "tool_calls": ["resolve_ticket"],
    }
