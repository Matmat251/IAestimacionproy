from typing import Any

from ..models import Activity
from ..planning import build_plan
from .state import AgentState


def planificador_node(state: AgentState) -> dict[str, Any]:
    activities = [Activity.model_validate(a) for a in state["activities"]]
    rates = state.get("rates", {})
    plan = build_plan(activities, rates)
    return {"plan": plan.model_dump()}
