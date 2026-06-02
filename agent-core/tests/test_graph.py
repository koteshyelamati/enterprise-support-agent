from __future__ import annotations

from typing import Any, Dict
from unittest.mock import patch

import pytest

from app.graph.nodes import (
    analyze_ticket, escalate_human, fetch_external_api,
    query_vector_db, resolve_ticket, self_correct,
)


def make_state(**overrides) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "ticket_id": "TEST-001",
        "description": "My laptop screen keeps flickering and will not stay on",
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
    base.update(overrides)
    return base


# ── analyze_ticket ────────────────────────────────────────────────────────────

def test_analyze_ticket_returns_required_fields():
    state = make_state()
    result = analyze_ticket(state)
    assert "severity" in result
    assert result["severity"] in ("critical", "high", "medium", "low")
    assert "category" in result
    assert len(result["history"]) == 1
    assert result["history"][0]["node"] == "analyze_ticket"
    assert "analyze_ticket" in result["tool_calls"]


def test_analyze_ticket_critical_for_outage():
    state = make_state(description="Production server outage -- all services down, revenue impacted")
    result = analyze_ticket(state)
    assert result["severity"] == "critical"


def test_analyze_ticket_account_category_for_password():
    state = make_state(description="I cannot reset my password, the email link expired")
    result = analyze_ticket(state)
    assert result["category"] == "account"


def test_analyze_ticket_network_for_vpn():
    state = make_state(description="VPN is not connecting, I cannot access internal resources")
    result = analyze_ticket(state)
    assert result["category"] == "network"


# ── query_vector_db ───────────────────────────────────────────────────────────

def test_query_vector_db_with_mock_results():
    state = make_state()
    mock_results = [
        {"document": "Password reset: use the portal at portal.internal/reset",
         "distance": 0.15, "metadata": {"category": "account"}, "id": "kb_001"}
    ]
    with patch("app.graph.nodes.search_knowledge_base", return_value=mock_results):
        result = query_vector_db(state)
    assert "confidence" in result
    assert result["confidence"] == pytest.approx(0.85, abs=0.01)
    assert "query_vector_db" in result["tool_calls"]
    assert result["external_data"]["kb_results"] == mock_results


def test_query_vector_db_low_confidence_for_far_match():
    state = make_state()
    mock_results = [{"document": "Some document", "distance": 0.95, "metadata": {}, "id": "kb_005"}]
    with patch("app.graph.nodes.search_knowledge_base", return_value=mock_results):
        result = query_vector_db(state)
    assert result["confidence"] < 0.75


def test_query_vector_db_zero_confidence_on_empty():
    state = make_state()
    with patch("app.graph.nodes.search_knowledge_base", return_value=[]):
        result = query_vector_db(state)
    assert result["confidence"] == 0.0


def test_query_vector_db_handles_exception_gracefully():
    state = make_state()
    with patch("app.graph.nodes.search_knowledge_base", side_effect=ConnectionError("chroma down")):
        result = query_vector_db(state)
    assert result["confidence"] == 0.0
    assert "error" in result["history"][0]["output"]


# ── fetch_external_api ────────────────────────────────────────────────────────

def test_fetch_external_api_found():
    state = make_state()
    mock_incident = {"incident_id": "INC001", "title": "VPN issue", "status": "open", "solution": "Reset credentials"}
    with patch("app.graph.nodes.fetch_servicenow_incident", return_value=mock_incident):
        result = fetch_external_api(state)
    assert result["external_data"]["servicenow_incident"] == mock_incident
    assert result["history"][0]["output"]["found"] is True


def test_fetch_external_api_not_found():
    state = make_state()
    with patch("app.graph.nodes.fetch_servicenow_incident", return_value=None):
        result = fetch_external_api(state)
    assert result["external_data"]["servicenow_incident"] is None
    assert result["history"][0]["output"]["found"] is False


def test_fetch_external_api_preserves_existing_kb_results():
    state = make_state(external_data={"kb_results": [{"document": "kb doc"}]})
    with patch("app.graph.nodes.fetch_servicenow_incident", return_value=None):
        result = fetch_external_api(state)
    assert result["external_data"]["kb_results"] == [{"document": "kb doc"}]


# ── self_correct ──────────────────────────────────────────────────────────────

def test_self_correct_increments_error_count():
    state = make_state(error_count=1, last_error="NameError: undefined")
    with patch("app.graph.nodes.execute_script_safely", return_value=(False, "Still broken")):
        result = self_correct(state)
    assert result["error_count"] == 2
    assert result["last_error"] is not None


def test_self_correct_clears_error_on_success():
    state = make_state(error_count=1, last_error="NameError: undefined")
    with patch("app.graph.nodes.execute_script_safely", return_value=(True, "Diagnostic OK")):
        result = self_correct(state)
    assert result["error_count"] == 2
    assert result["last_error"] is None


def test_self_correct_first_attempt_uses_buggy_script():
    state = make_state(error_count=0, last_error=None)
    captured = {}

    def fake_execute(code: str):
        captured["code"] = code
        return False, "NameError: name '_undefined_diagnostic_function' is not defined"

    with patch("app.graph.nodes.execute_script_safely", side_effect=fake_execute):
        result = self_correct(state)

    assert "_undefined_diagnostic_function" in captured["code"]
    assert result["error_count"] == 1


# ── escalate_human ────────────────────────────────────────────────────────────

def test_escalate_human_sets_escalated_true():
    state = make_state(severity="critical", ticket_id="INC-CRIT")
    mock_record = {
        "escalation_id": "ESC-INC-CRIT-9999", "assigned_team": "Incident Command",
        "sla_minutes": 60, "reason": "critical",
    }
    with patch("app.graph.nodes.create_escalation_record", return_value=mock_record):
        result = escalate_human(state)
    assert result["escalated"] is True
    assert "ESC-INC-CRIT-9999" in result["resolution"]
    assert "escalate_human" in result["tool_calls"]


def test_escalate_human_mentions_sla():
    state = make_state(severity="high", error_count=3)
    mock_record = {
        "escalation_id": "ESC-TEST-001-1234", "assigned_team": "L2 Support",
        "sla_minutes": 240, "reason": "max retries",
    }
    with patch("app.graph.nodes.create_escalation_record", return_value=mock_record):
        result = escalate_human(state)
    assert "240" in result["resolution"]


# ── resolve_ticket ────────────────────────────────────────────────────────────

def test_resolve_ticket_produces_resolution():
    state = make_state(
        severity="medium", category="account",
        external_data={"kb_results": [{"document": "Use the password reset portal."}]},
    )
    result = resolve_ticket(state)
    assert result["resolution"] is not None
    assert len(result["resolution"]) > 20
    assert "resolve_ticket" in result["tool_calls"]


def test_resolve_ticket_works_without_external_data():
    state = make_state(category="network")
    result = resolve_ticket(state)
    assert result["resolution"] is not None


# ── Full graph integration ────────────────────────────────────────────────────

def test_full_graph_happy_path_resolves():
    from app.graph.agent_graph import compiled_graph
    initial = make_state(
        ticket_id="INT-001",
        description="Cannot reset my password, the link is expired and I am locked out",
    )
    mock_kb = [{"document": "Password reset: Go to the company portal at https://portal.internal/reset.",
                "distance": 0.08, "metadata": {"category": "account"}, "id": "kb_001"}]

    with patch("app.graph.nodes.search_knowledge_base", return_value=mock_kb):
        result = compiled_graph.invoke(initial)

    assert result["resolution"] is not None
    assert result["escalated"] is False
    assert "analyze_ticket" in result["tool_calls"]
    assert "query_vector_db" in result["tool_calls"]
    assert "resolve_ticket" in result["tool_calls"]


def test_full_graph_critical_ticket_escalates():
    from app.graph.agent_graph import compiled_graph
    initial = make_state(
        ticket_id="CRIT-001",
        description="Production database breach detected -- ransomware encrypting files",
    )
    mock_escalation = {
        "escalation_id": "ESC-CRIT-001-0001", "assigned_team": "Incident Command",
        "sla_minutes": 60, "reason": "critical severity",
    }
    with patch("app.graph.nodes.create_escalation_record", return_value=mock_escalation):
        result = compiled_graph.invoke(initial)

    assert result["escalated"] is True
    assert result["severity"] == "critical"
    assert "escalate_human" in result["tool_calls"]
    assert "query_vector_db" not in result["tool_calls"]


def test_full_graph_self_correction_loop():
    from app.graph.agent_graph import compiled_graph
    initial = make_state(
        ticket_id="SELF-001",
        description="Very obscure issue not in any knowledge base at all",
    )
    low_confidence_kb = [{"document": "Unrelated doc", "distance": 0.98, "metadata": {}, "id": "kb_020"}]
    mock_escalation = {
        "escalation_id": "ESC-SELF-001-5555", "assigned_team": "L2 Support",
        "sla_minutes": 240, "reason": "max retries",
    }
    with (
        patch("app.graph.nodes.search_knowledge_base", return_value=low_confidence_kb),
        patch("app.graph.nodes.fetch_servicenow_incident", return_value=None),
        patch("app.graph.nodes.execute_script_safely", return_value=(False, "Script failed")),
        patch("app.graph.nodes.create_escalation_record", return_value=mock_escalation),
    ):
        result = compiled_graph.invoke(initial)

    assert result["escalated"] is True
    assert result["error_count"] >= 3
    self_correct_calls = [c for c in result["tool_calls"] if c.startswith("self_correct")]
    assert len(self_correct_calls) >= 3
