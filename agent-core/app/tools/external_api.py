from __future__ import annotations
import logging
import random
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_MOCK_SERVICENOW_DB: Dict[str, Dict[str, Any]] = {
    "INC001": {"incident_id": "INC001", "title": "VPN not connecting for remote workers", "status": "open", "priority": "2", "assigned_team": "Network Operations", "solution": "VPN gateway was restarted. Reset credentials and reconnect using Cisco AnyConnect.", "workaround": "Use web VPN at webvpn.company.com as fallback."},
    "INC002": {"incident_id": "INC002", "title": "Mass account lockout after AD sync", "status": "resolved", "priority": "1", "assigned_team": "Identity & Access Management", "solution": "AD sync conflict resolved. Run Unlock-ADAccount cmdlet for affected users.", "workaround": "Use secondary account while primary is unlocked."},
    "INC003": {"incident_id": "INC003", "title": "Email gateway outage", "status": "in_progress", "priority": "1", "assigned_team": "Messaging Infrastructure", "solution": "Email routing tables being updated. ETA 2 hours.", "workaround": "Use webmail at mail.company.com."},
    "INC004": {"incident_id": "INC004", "title": "File server inaccessible from Floor 3", "status": "resolved", "priority": "2", "assigned_team": "Storage Team", "solution": "Network switch replaced. All services restored.", "workaround": None},
    "INC005": {"incident_id": "INC005", "title": "Slow database queries in CRM application", "status": "open", "priority": "3", "assigned_team": "Database Administration", "solution": "Index rebuild scheduled for next maintenance window.", "workaround": "Use crm-reports.internal as read-only alternative."},
}


def fetch_servicenow_incident(ticket_id: str) -> Optional[Dict[str, Any]]:
    """Simulate fetching incident data from ServiceNow REST API."""
    time.sleep(0.05)
    if ticket_id in _MOCK_SERVICENOW_DB:
        logger.info("ServiceNow: exact match for %s", ticket_id)
        return dict(_MOCK_SERVICENOW_DB[ticket_id])
    if random.random() > 0.4:
        key = random.choice(list(_MOCK_SERVICENOW_DB.keys()))
        incident = dict(_MOCK_SERVICENOW_DB[key])
        incident["incident_id"] = ticket_id
        incident["note"] = "Related incident pattern applied"
        logger.info("ServiceNow: related incident %s applied to %s", key, ticket_id)
        return incident
    logger.info("ServiceNow: no incident found for %s", ticket_id)
    return None


def create_escalation_record(ticket_id: str, description: str, severity: str, reason: str) -> Dict[str, Any]:
    """Create an escalation record in ServiceNow."""
    time.sleep(0.05)
    escalation_id = f"ESC-{ticket_id}-{random.randint(1000, 9999)}"
    assigned_team = "Incident Command" if severity == "critical" else "L2 Support"
    sla_minutes = 60 if severity == "critical" else 240
    return {
        "escalation_id": escalation_id, "ticket_id": ticket_id,
        "status": "escalated", "severity": severity,
        "assigned_team": assigned_team, "sla_minutes": sla_minutes, "reason": reason,
        "message": f"Ticket {ticket_id} escalated to {assigned_team}. SLA: {sla_minutes} minutes. Reason: {reason}.",
    }
