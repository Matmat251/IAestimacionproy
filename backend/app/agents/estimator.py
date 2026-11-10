from copy import deepcopy
from typing import Any

from ..reference import load_stack_catalog
from .state import AgentState


def estimador_node(state: AgentState) -> dict[str, Any]:
    activities = deepcopy(state["activities"])
    complexity = state.get("complexity", "media")
    audit = state.get("audit")
    tech_justifications = deepcopy(state.get("tech_justifications", []))
    recommended_technologies = list(state.get("recommended_technologies", []))
    infra_profile = state.get("infra_profile", "vps")

    if audit and audit.get("findings"):
        findings = audit.get("findings", [])
        for a in activities:
            if not (a["optimistic_hours"] <= a["most_likely_hours"] <= a["pessimistic_hours"]):
                a["most_likely_hours"] = max(a["optimistic_hours"], a["most_likely_hours"])
                a["pessimistic_hours"] = max(a["most_likely_hours"], a["pessimistic_hours"])

        if any("prohibid" in f.lower() for f in findings):
            catalogo = load_stack_catalog()
            prohibido = [x.lower() for x in catalogo.get(infra_profile, {}).get("prohibido", [])]
            tech_justifications = [
                tj for tj in tech_justifications
                if not any(p_tech in tj.get("nombre", "").lower() for p_tech in prohibido)
            ]
            recommended_technologies = [
                tech for tech in recommended_technologies
                if not any(p_tech in tech.lower() for p_tech in prohibido)
            ]
    else:
        # Escala por complejidad: baja: 0.8, media: 1.0, alta: 1.4
        scale = 0.8 if complexity == "baja" else (1.4 if complexity == "alta" else 1.0)
        for a in activities:
            a["optimistic_hours"] = round(a["optimistic_hours"] * scale, 1)
            a["most_likely_hours"] = round(a["most_likely_hours"] * scale, 1)
            a["pessimistic_hours"] = round(a["pessimistic_hours"] * scale, 1)
            if not (a["optimistic_hours"] <= a["most_likely_hours"] <= a["pessimistic_hours"]):
                a["most_likely_hours"] = max(a["optimistic_hours"], a["most_likely_hours"])
                a["pessimistic_hours"] = max(a["most_likely_hours"], a["pessimistic_hours"])

    res: dict[str, Any] = {"activities": activities}
    if tech_justifications:
        res["tech_justifications"] = tech_justifications
    if recommended_technologies:
        res["recommended_technologies"] = recommended_technologies
    return res
