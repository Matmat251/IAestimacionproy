from langgraph.graph import END, START, StateGraph

from ..models import Activity, Audit, DraftRequest, DraftResponse, Plan, RagEvidence, Requirement, Risk, TechJustification
from .analyst import analista_node, route_analista
from .architect import arquitecto_node
from .auditor import auditor_node, route_auditor
from .estimator import estimador_node
from .orchestrator import orquestador_node
from .planner import planificador_node
from .state import AgentState

# Construcción modular del grafo LangGraph
graph_builder = StateGraph(AgentState)

# Registro de Nodos / Agentes
graph_builder.add_node("orquestador", orquestador_node)
graph_builder.add_node("analista", analista_node)
graph_builder.add_node("arquitecto", arquitecto_node)
graph_builder.add_node("estimador", estimador_node)
graph_builder.add_node("planificador", planificador_node)
graph_builder.add_node("auditor", auditor_node)

# Flujo de ejecución
graph_builder.add_edge(START, "orquestador")
graph_builder.add_edge("orquestador", "analista")
graph_builder.add_conditional_edges(
    "analista",
    route_analista,
    {"needs_clarification": END, "proceed": "arquitecto"},
)
graph_builder.add_edge("arquitecto", "estimador")
graph_builder.add_edge("estimador", "planificador")
graph_builder.add_edge("planificador", "auditor")
graph_builder.add_conditional_edges(
    "auditor",
    route_auditor,
    {"reestimate": "estimador", "end": END},
)

agent_graph = graph_builder.compile()


def create_draft(request: DraftRequest) -> DraftResponse:
    state = agent_graph.invoke({"request": request})
    missing = state.get("missing", [])
    questions = state.get("questions", [])
    is_clarification = bool(missing or questions or not state.get("sufficient", True))

    requirements = [Requirement.model_validate(r) for r in state.get("requirements", [])]
    activities = [Activity.model_validate(a) for a in state.get("activities", [])]
    risks = [Risk.model_validate(rk) for rk in state.get("risks", [])]

    plan_data = state.get("plan")
    plan = Plan.model_validate(plan_data) if plan_data else None

    audit_data = state.get("audit")
    audit = Audit.model_validate(audit_data) if audit_data else None

    infra_profile = state.get("infra_profile", "vps")
    tech_justifications = [
        TechJustification.model_validate(t)
        for t in state.get("tech_justifications", [])
    ]
    rag_evidence = [
        RagEvidence.model_validate(h)
        for h in state.get("similar_history", [])
        if isinstance(h, dict) and "nombre" in h
    ]

    return DraftResponse(
        project_name=request.project.name,
        status="needs_clarification" if is_clarification else "ready_for_review",
        requirements=requirements,
        missing_fields=missing,
        questions=questions,
        activities=activities,
        total_expected_hours=round(sum(a.expected_hours for a in activities), 1),
        notes=state.get("notes", []),
        complexity=state.get("complexity", "media"),
        risks=risks,
        recommended_technologies=state.get("recommended_technologies", []),
        infra_profile=infra_profile,
        tech_justifications=tech_justifications,
        plan=plan,
        audit=audit,
        rag_evidence=rag_evidence,
    )
