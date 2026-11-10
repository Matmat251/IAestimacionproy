import pytest
from app.models import Activity, Plan, RoleCost
from app.planning import audit_estimation, build_plan, critical_path_hours


def test_pert_calculation():
    act = Activity(
        id="A1",
        phase="Desarrollo",
        name="Backend core",
        profile="Desarrollador",
        optimistic_hours=2.0,
        most_likely_hours=4.0,
        pessimistic_hours=12.0,
        rationale="Prueba PERT",
    )
    # (2 + 4*4 + 12) / 6 = 30 / 6 = 5.0
    assert act.expected_hours == 5.0


def test_critical_path_parallel_branches():
    # A1 (10h) -> A2 (20h) -> A4 (10h) => 40h
    #          -> A3 (5h)  -> A4 (10h) => 25h
    # Ruta crítica debe ser 40h
    a1 = Activity(id="A1", phase="Análisis", name="A1", profile="Analista funcional", optimistic_hours=10, most_likely_hours=10, pessimistic_hours=10, rationale="")
    a2 = Activity(id="A2", phase="Diseño", name="A2", profile="Arquitecto / Tech Lead", depends_on=["A1"], optimistic_hours=20, most_likely_hours=20, pessimistic_hours=20, rationale="")
    a3 = Activity(id="A3", phase="Diseño", name="A3", profile="Arquitecto / Tech Lead", depends_on=["A1"], optimistic_hours=5, most_likely_hours=5, pessimistic_hours=5, rationale="")
    a4 = Activity(id="A4", phase="QA", name="A4", profile="QA", depends_on=["A2", "A3"], optimistic_hours=10, most_likely_hours=10, pessimistic_hours=10, rationale="")

    total_cp = critical_path_hours([a1, a2, a3, a4])
    assert total_cp == 40.0


def test_critical_path_detects_cycle():
    a1 = Activity(id="A1", phase="Análisis", name="A1", profile="Analista funcional", depends_on=["A2"], optimistic_hours=4, most_likely_hours=4, pessimistic_hours=4, rationale="")
    a2 = Activity(id="A2", phase="Diseño", name="A2", profile="Arquitecto / Tech Lead", depends_on=["A1"], optimistic_hours=4, most_likely_hours=4, pessimistic_hours=4, rationale="")

    with pytest.raises(ValueError, match="Ciclo detectado"):
        critical_path_hours([a1, a2])


def test_build_plan_roles_and_costs():
    activities = [
        Activity(id="A1", phase="Análisis", name="A1", profile="Analista funcional", optimistic_hours=40, most_likely_hours=40, pessimistic_hours=40, rationale=""),
        Activity(id="A2", phase="QA", name="A2", profile="QA", depends_on=["A1"], optimistic_hours=40, most_likely_hours=40, pessimistic_hours=40, rationale=""),
    ]
    rates = {
        "Analista funcional": {"tarifa_hora": 25.0, "capacidad_semanal": 40.0},
        "QA": {"tarifa_hora": 20.0, "capacidad_semanal": 40.0},
    }
    plan = build_plan(activities, rates)
    assert len(plan.roles) == 2
    analista_role = next(r for r in plan.roles if r.profile == "Analista funcional")
    assert analista_role.hours == 40.0
    assert analista_role.cost == 1000.0  # 40 * 25
    assert analista_role.people == 1
    assert plan.total_cost == 1800.0  # 1000 + 800
    assert plan.duration_weeks == 2.0  # (40 + 40) / 40


def test_audit_estimation_rules():
    rates = {"Desarrollador": {"tarifa_hora": 30.0, "capacidad_semanal": 40.0}}
    # 1. Viola O <= M <= P
    a_violacion = Activity(id="A1", phase="Dev", name="Mal PERT", profile="Desarrollador", optimistic_hours=10, most_likely_hours=5, pessimistic_hours=20, rationale="")
    # 2. Perfil sin tarifa
    a_no_rate = Activity(id="A2", phase="Dev", name="Sin tarifa", profile="Disenador UI", optimistic_hours=4, most_likely_hours=4, pessimistic_hours=4, rationale="")
    # 3. Ausencia de QA
    activities = [a_violacion, a_no_rate]
    plan = Plan(roles=[], duration_weeks=1.0, total_cost=0.0)

    findings = audit_estimation(activities, plan, rates, similar_hist=[{"horas_reales": 100.0}])

    # Chequeos de hallazgos
    assert any("viola O <= M <= P" in f for f in findings)
    assert any("no existe en tarifas" in f for f in findings)
    assert any("Ausencia de actividad de fase 'QA'" in f for f in findings)
    # Total de horas de activities es 6.7 + 4 = 10.7h vs 100h histórico (>50% desvío)
    assert any("se desvía más del 50%" in f for f in findings)
