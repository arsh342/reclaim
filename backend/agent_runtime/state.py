"""Agent runtime state definitions."""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class AgentStage(str, Enum):
    RECEIVED = "RECEIVED"
    CONTEXT_LOADING = "CONTEXT_LOADING"
    DIAGNOSING = "DIAGNOSING"
    GENERATING_CANDIDATES = "GENERATING_CANDIDATES"
    EVALUATING_COUNTERFACTUALS = "EVALUATING_COUNTERFACTUALS"
    PLANNING = "PLANNING"
    SAFETY_CHECK = "SAFETY_CHECK"
    EXECUTING = "EXECUTING"
    WAITING_FOR_OUTCOME = "WAITING_FOR_OUTCOME"
    COMPLETED = "COMPLETED"
    REPLANNING = "REPLANNING"


@dataclass
class RunState:
    run_id: str
    order_id: str
    current_stage: AgentStage = AgentStage.RECEIVED
    status: str = "running"
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    diagnosis: Optional[Dict[str, Any]] = None
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    counterfactuals: List[Dict[str, Any]] = field(default_factory=list)
    plan: Optional[Dict[str, Any]] = None
    safety_result: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    final_action: Optional[str] = None
    final_reason: Optional[str] = None
    error: Optional[str] = None
    replan_count: int = 0


# Event types for agent_events table
AGENT_EVENT_TYPES = {
    "run_started": "agent.run.started",
    "stage_started": "agent.stage.started",
    "stage_completed": "agent.stage.completed",
    "tool_called": "agent.tool.called",
    "tool_completed": "agent.tool.completed",
    "policy_rejected": "agent.policy.rejected",
    "plan_created": "agent.plan.created",
    "action_executed": "agent.action.executed",
    "replan_started": "agent.replan.started",
    "order_recovered": "order.recovered",
    "run_completed": "agent.run.completed",
}