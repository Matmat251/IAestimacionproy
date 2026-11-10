from copy import deepcopy
import pytest
from fastapi.testclient import TestClient

from app.agent import agent_graph, create_draft
from app.main import app
from app.models import DraftRequest, ProjectInput, ReviewRequest


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_app.db"
    monkeypatch.setattr("app.store.DB_PATH", test_db)
    return TestClient(app)


def test_graph_needs_clarification():
    req = DraftRequest(
        project=ProjectInput(
            name="Proyecto Incompleto",
            description="Necesitamos un sistema de pedidos para sucursales pero no sabemos aún qué incluir.",
            scope="",
            technology="",
            integrations="",
            constraints="",
        )
    )
    draft = create_draft(req)
    assert draft.status == "needs_clarification"
    assert len(draft.missing_fields) > 0
    assert len(draft.questions) > 0


def test_graph_ready_for_review():
    req = DraftRequest(
        project=ProjectInput(
            name="Portal de Clientes",
            description="Portal web para que clientes consulten facturas y estados de cuenta en tiempo real.",
            scope="Módulo de autenticación, consulta de saldo, descarga de facturas en PDF.",
            technology="",
            integrations="ERP SAP mediante REST API",
            constraints="Tiempo de respuesta < 1.5s, despliegue en AWS",
        )
    )
    draft = create_draft(req)
    assert draft.status == "ready_for_review"
    assert len(draft.recommended_technologies) > 0
    assert len(draft.activities) == 5
    assert draft.total_expected_hours > 0
    assert draft.plan is not None
    assert draft.plan.total_cost > 0
    assert draft.plan.duration_weeks > 0
    assert len(draft.risks) >= 2
    assert draft.audit is not None
    assert draft.audit.iterations >= 1


def test_auditor_reestimate_loop_cap(monkeypatch):
    # Forzamos un estimador que siempre viola O <= M <= P
    def bad_estimador(state):
        acts = deepcopy(state["activities"])
        for a in acts:
            # O=20 > M=10 > P=5 (viola O <= M <= P)
            a["optimistic_hours"] = 20.0
            a["most_likely_hours"] = 10.0
            a["pessimistic_hours"] = 5.0
        return {"activities": acts}

    monkeypatch.setattr("app.agent.estimador_node", bad_estimador)
    # Reconstruir grafo para usar el estimador monkeypatcheado
    from langgraph.graph import END, START, StateGraph
    from app.agent import AgentState, analista_node, arquitecto_node, auditor_node, orquestador_node, planificador_node, route_analista, route_auditor

    gb = StateGraph(AgentState)
    gb.add_node("orquestador", orquestador_node)
    gb.add_node("analista", analista_node)
    gb.add_node("arquitecto", arquitecto_node)
    gb.add_node("estimador", bad_estimador)
    gb.add_node("planificador", planificador_node)
    gb.add_node("auditor", auditor_node)

    gb.add_edge(START, "orquestador")
    gb.add_edge("orquestador", "analista")
    gb.add_conditional_edges("analista", route_analista, {"needs_clarification": END, "proceed": "arquitecto"})
    gb.add_edge("arquitecto", "estimador")
    gb.add_edge("estimador", "planificador")
    gb.add_edge("planificador", "auditor")
    gb.add_conditional_edges("auditor", route_auditor, {"reestimate": "estimador", "end": END})
    test_graph = gb.compile()

    req = DraftRequest(
        project=ProjectInput(
            name="Test Loop Cap",
            description="Sistema de pruebas para verificar el límite de iteraciones del auditor.",
            scope="Todo",
            technology="Python",
            integrations="Ninguna",
            constraints="Ninguna",
        )
    )
    res = test_graph.invoke({"request": req})
    # Se debe detener exactamente en 2 iteraciones
    assert res["audit"]["iterations"] == 2
    assert res["audit"]["approved"] is False
    assert any("viola O <= M <= P" in f for f in res["audit"]["findings"])


def test_api_endpoints_full_lifecycle(client):
    # 1. Health
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"
    assert r_health.json()["provider"] == "groq"

    # 2. Draft
    draft_payload = {
        "project": {
            "name": "App Móvil de Entregas",
            "description": "Aplicación móvil para repartidores con geolocalización y confirmación de entrega.",
            "scope": "Registro de entrega, mapa de ruta, firma digital.",
            "technology": "Flutter, FastAPI, PostgreSQL",
            "integrations": "Google Maps API",
            "constraints": "Offline first en zonas sin cobertura",
        }
    }
    r_draft = client.post("/api/estimate/draft", json=draft_payload)
    assert r_draft.status_code == 200
    draft_data = r_draft.json()
    assert draft_data["status"] == "ready_for_review"
    assert draft_data["plan"] is not None

    # 3. Review & SQLite Save
    review_payload = {
        "approved": True,
        "reviewer": "Tech Lead Juan",
        "comment": "Aprobado sin objeciones",
        "draft": draft_data,
    }
    r_review = client.post("/api/estimate/review", json=review_payload)
    assert r_review.status_code == 200
    review_resp = r_review.json()
    assert review_resp["status"] == "approved"
    est_id = review_resp["id"]
    assert est_id > 0

    # 4. List and Get Estimations
    r_list = client.get("/api/estimations")
    assert r_list.status_code == 200
    assert any(item["id"] == est_id for item in r_list.json())

    r_single = client.get(f"/api/estimations/{est_id}")
    assert r_single.status_code == 200
    assert r_single.json()["project_name"] == "App Móvil de Entregas"

    # 5. Reference Data
    r_ref = client.get("/api/reference/tarifas")
    assert r_ref.status_code == 200
    assert len(r_ref.json()) > 0

    # 6. Reports: PDF and XLSX
    r_pdf = client.post("/api/estimate/report?format=pdf", json=review_payload)
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    assert len(r_pdf.content) > 1000

    r_xlsx = client.post("/api/estimate/report?format=xlsx", json=review_payload)
    assert r_xlsx.status_code == 200
    assert "spreadsheetml" in r_xlsx.headers["content-type"]
    assert len(r_xlsx.content) > 1000
