from __future__ import annotations
import operator
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict

class AgentState(TypedDict):
    ticket_id: str
    description: str
    category: Optional[str]
    history: Annotated[List[Dict[str, Any]], operator.add]
    tool_calls: Annotated[List[str], operator.add]
    resolution: Optional[str]
    escalated: bool
    error_count: int
    severity: Optional[str]
    confidence: Optional[float]
    external_data: Optional[Dict[str, Any]]
    last_error: Optional[str]
