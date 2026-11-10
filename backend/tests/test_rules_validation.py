import pytest

from app.agent import create_draft
from app.models import Activity, DiscardedAlternative, DraftRequest, Plan, ProjectInput, Requirement, TechJustification
from app.planning import validate_estimation_rules
from app.reference import load_stack_catalog


def test_stack_catalog_loads_correctly():
    catalog = load_stack_catalog()
    assert "hosting_compartido" in catalog
    assert "vps" in catalog
    assert "cloud" in catalog
    assert "umbral_complejidad" in catalog
    assert "Docker" in catalog["hosting_compartido"]["prohibido"]
    assert "Kubernetes" in catalog["vps"]["prohibido"]
    assert "servicios_gestionados" in catalog["cloud"]["permitido"]


def test_hosting_compartido_detects_prohibited_tech():
    req = DraftRequest(
        project=ProjectInput(
            name="Blog Personal",
            description="Sitio web corporativo y blog desplegado en hosting cPanel compartido.",
            scope="Gestión de artículos y formulario de contacto",
            technology="PHP, MySQL",
            integrations="Ninguna",
            constraints="Alojado en cpanel compartido de bajo costo",
        )
    )
    draft = create_draft(req)
    assert draft.infra_profile == "hosting_compartido"
    # Docker, Kubernetes, Nginx, Redis, Kafka prohibited in hosting_compartido
    for tj in draft.tech_justifications:
        assert tj.nombre not in ["Docker", "Kubernetes", "Kafka", "Redis", "microservicios"]
    assert len(draft.tech_justifications) > 0
    assert draft.tech_justifications[0].alternativas_descartadas[0].motivo != ""


def test_unconfirmed_numeric_assumption_detected_in_auditor():
    activities = [
        Activity(
            id="A1",
            phase="QA",
            name="Pruebas de carga",
            profile="QA",
            optimistic_hours=10,
            most_likely_hours=10,
            pessimistic_hours=10,
            rationale="",
        )
    ]
    plan = Plan(roles=[], duration_weeks=1.0, total_cost=0.0)
    rates = {"QA": {"tarifa_hora": 20.0, "capacidad_semanal": 40.0}}

    req_supuesto_con_cifra = Requirement(
        id="R1",
        title="Escalabilidad",
        detail="Debe soportar 10000 usuarios concurrentes",
        kind="assumption",
        origen="supuesto",
        contiene_cifra=True,
        requiere_confirmacion=True,
        confirmado=False,
    )

    findings, warnings = validate_estimation_rules(
        activities=activities,
        plan=plan,
        rates=rates,
        similar_hist=[],
        infra_profile="vps",
        requirements=[req_supuesto_con_cifra],
    )

    assert any("supuesto con cifras numéricas y requiere confirmación" in f for f in findings)


def test_prohibited_tech_finding():
    activities = [
        Activity(
            id="A1",
            phase="QA",
            name="QA",
            profile="QA",
            optimistic_hours=10,
            most_likely_hours=10,
            pessimistic_hours=10,
            rationale="",
        )
    ]
    plan = Plan(roles=[], duration_weeks=1.0, total_cost=0.0)
    rates = {"QA": {"tarifa_hora": 20.0, "capacidad_semanal": 40.0}}

    tj_prohibido = TechJustification(
        nombre="Kubernetes",
        categoria="orquestacion",
        justificacion="Contenedores en VPS",
        requisitos_ids=["R1"],
        alternativas_descartadas=[DiscardedAlternative(nombre="Docker Compose", motivo="Menos escalable")],
    )

    findings, warnings = validate_estimation_rules(
        activities=activities,
        plan=plan,
        rates=rates,
        similar_hist=[],
        infra_profile="vps",
        tech_justifications=[tj_prohibido],
    )

    assert any("está prohibida para el perfil de infraestructura 'vps'" in f for f in findings)


def test_parametric_warnings_pm_and_undocumented_api():
    # Actividad de integración con api_documentada=False y < 24h
    act_integ = Activity(
        id="A1",
        phase="Desarrollo",
        name="Integración pasarela de pagos externa",
        profile="Desarrollador",
        categoria="integracion",
        api_documentada=False,
        optimistic_hours=8,
        most_likely_hours=10,
        pessimistic_hours=12,
        rationale="",
    )
    act_qa = Activity(
        id="A2",
        phase="QA",
        name="Pruebas generales",
        profile="QA",
        optimistic_hours=10,
        most_likely_hours=10,
        pessimistic_hours=10,
        rationale="",
    )
    # Total = 10 + 10 = 20h. No hay PM (0%) -> Advertencia paramétrica PM
    activities = [act_integ, act_qa]
    plan = Plan(roles=[], duration_weeks=1.0, total_cost=0.0)
    rates = {
        "Desarrollador": {"tarifa_hora": 30.0, "capacidad_semanal": 40.0},
        "QA": {"tarifa_hora": 20.0, "capacidad_semanal": 40.0},
    }

    findings, warnings = validate_estimation_rules(
        activities=activities,
        plan=plan,
        rates=rates,
        similar_hist=[],
        infra_profile="vps",
    )

    assert any("con API no documentada" in w for w in warnings)
