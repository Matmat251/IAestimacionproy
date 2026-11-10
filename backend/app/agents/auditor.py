from typing import Any

from ..models import Activity, Plan
from ..planning import validate_estimation_rules
from .state import AgentState


def auditor_node(state: AgentState) -> dict[str, Any]:
    activities = [Activity.model_validate(a) for a in state["activities"]]
    plan = Plan.model_validate(state["plan"])
    rates = state.get("rates", {})
    history = state.get("similar_history", [])
    iterations = state.get("iterations", 0) + 1
    infra_profile = state.get("infra_profile", "vps")
    tech_justifications = state.get("tech_justifications", [])
    requirements = state.get("requirements", [])

    findings, warnings = validate_estimation_rules(
        activities=activities,
        plan=plan,
        rates=rates,
        similar_hist=history,
        infra_profile=infra_profile,
        tech_justifications=tech_justifications,
        requirements=requirements,
    )
    approved = len(findings) == 0

    return {
        "iterations": iterations,
        "audit": {
            "approved": approved,
            "findings": findings,
            "warnings": warnings,
            "iterations": iterations,
        },
    }


def route_auditor(state: AgentState) -> str:
    audit = state.get("audit", {})
    findings = audit.get("findings", [])
    iterations = state.get("iterations", 0)
    has_fixable = any(
        "viola O <= M <= P" in f
        or "está prohibida para el perfil" in f
        or "prohibid" in f.lower()
        for f in findings
    )
    if has_fixable and iterations < 2:
        return "reestimate"
    return "end"
