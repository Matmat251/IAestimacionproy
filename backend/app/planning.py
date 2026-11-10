import math
from typing import Any

from .models import Activity, Plan, RoleCost
from .reference import load_stack_catalog


def critical_path_hours(activities: list[Activity]) -> float:
    if not activities:
        return 0.0

    act_map = {a.id: a for a in activities}

    # Cycle detection via 3-color DFS
    state: dict[str, int] = {}  # 1: visiting, 2: visited

    def has_cycle(node_id: str) -> bool:
        state[node_id] = 1
        for dep in act_map[node_id].depends_on:
            if dep in act_map:
                if state.get(dep) == 1:
                    return True
                if dep not in state and has_cycle(dep):
                    return True
        state[node_id] = 2
        return False

    for node_id in act_map:
        if node_id not in state:
            if has_cycle(node_id):
                raise ValueError("Ciclo detectado en dependencias de actividades")

    memo: dict[str, float] = {}

    def get_ef(node_id: str) -> float:
        if node_id in memo:
            return memo[node_id]
        deps = [d for d in act_map[node_id].depends_on if d in act_map]
        max_pred = max((get_ef(d) for d in deps), default=0.0)
        ef = max_pred + act_map[node_id].expected_hours
        memo[node_id] = ef
        return ef

    return round(max(get_ef(a.id) for a in activities), 1)


def build_plan(activities: list[Activity], rates: dict[str, dict[str, Any]]) -> Plan:
    profile_hours: dict[str, float] = {}
    for a in activities:
        profile_hours[a.profile] = profile_hours.get(a.profile, 0.0) + a.expected_hours

    roles: list[RoleCost] = []
    for profile, total_hours in profile_hours.items():
        hours = round(total_hours, 1)
        rate_info = rates.get(profile, {})
        rate = float(rate_info.get("tarifa_hora", 0.0))
        capacidad = float(rate_info.get("capacidad_semanal", 40.0)) or 40.0
        people = max(1, min(3, math.ceil(hours / (capacidad * 4))))
        cost = round(hours * rate, 2)
        roles.append(RoleCost(profile=profile, hours=hours, people=people, rate=rate, cost=cost))

    duration_weeks = round(critical_path_hours(activities) / 40.0, 1)
    total_cost = round(sum(r.cost for r in roles), 2)
    return Plan(roles=roles, duration_weeks=duration_weeks, total_cost=total_cost)


def validate_estimation_rules(
    activities: list[Activity],
    plan: Plan,
    rates: dict[str, dict[str, Any]],
    similar_hist: list[dict[str, Any]],
    infra_profile: str = "vps",
    tech_justifications: list[Any] | None = None,
    requirements: list[Any] | None = None,
) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    warnings: list[str] = []

    # 1. Check O <= M <= P
    for a in activities:
        if not (a.optimistic_hours <= a.most_likely_hours <= a.pessimistic_hours):
            findings.append(
                f"Actividad '{a.name}' viola O <= M <= P ({a.optimistic_hours} <= {a.most_likely_hours} <= {a.pessimistic_hours})"
            )

    # 2. Check expected_hours <= 0
    for a in activities:
        if a.expected_hours <= 0:
            findings.append(f"Actividad '{a.name}' tiene horas esperadas <= 0")

    # 3. Check profiles registered in rates
    for a in activities:
        if a.profile not in rates:
            msg = f"Perfil '{a.profile}' no existe en tarifas de referencia"
            if msg not in findings:
                findings.append(msg)

    # 4. Absence of QA activity
    has_qa = any("QA" in a.phase.upper() or "PRUEBAS" in a.name.upper() or a.profile.upper() == "QA" for a in activities)
    if not has_qa:
        findings.append("Ausencia de actividad de fase 'QA'")

    # 5. Deviation from historical average
    total_expected = sum(a.expected_hours for a in activities)
    if similar_hist:
        total_hist_hours = sum(float(h.get("horas_reales", 0.0)) for h in similar_hist)
        avg_hist = total_hist_hours / len(similar_hist)
        if avg_hist > 0 and (abs(total_expected - avg_hist) / avg_hist) > 0.5:
            findings.append(
                f"El esfuerzo total ({round(total_expected, 1)} h) se desvía más del 50% respecto a la media histórica ({round(avg_hist, 1)} h)"
            )

    # 6. Catálogo de stacks y justificaciones tecnológicas
    catalogo = load_stack_catalog()
    prohibido = [x.lower() for x in catalogo.get(infra_profile, {}).get("prohibido", [])]
    if tech_justifications:
        for tj in tech_justifications:
            name = tj.nombre if hasattr(tj, "nombre") else tj.get("nombre", "")
            # Chequeo de tecnología prohibida para el perfil
            if any(p_tech in name.lower() for p_tech in prohibido):
                findings.append(f"Tecnología '{name}' está prohibida para el perfil de infraestructura '{infra_profile}'")

            # Trazabilidad con requisitos o restricciones
            r_ids = tj.requisitos_ids if hasattr(tj, "requisitos_ids") else tj.get("requisitos_ids", [])
            rst_ids = tj.restricciones_ids if hasattr(tj, "restricciones_ids") else tj.get("restricciones_ids", [])
            if not r_ids and not rst_ids:
                findings.append(f"Tecnología '{name}' carece de trazabilidad: falta asociar requisitos_ids o restricciones_ids")

            # Alternativas descartadas
            alts = tj.alternativas_descartadas if hasattr(tj, "alternativas_descartadas") else tj.get("alternativas_descartadas", [])
            if not alts:
                findings.append(f"Tecnología '{name}' no incluye alternativas descartadas con su motivo")

    # 7. Trazabilidad de origen y confirmación de supuestos cuantitativos
    if requirements:
        for r in requirements:
            r_id = getattr(r, "id", None) or (r.get("id") if isinstance(r, dict) else "R?")
            r_origen = getattr(r, "origen", None) or (r.get("origen") if isinstance(r, dict) else "explicito")
            r_cifra = getattr(r, "contiene_cifra", None) if hasattr(r, "contiene_cifra") else (r.get("contiene_cifra") if isinstance(r, dict) else False)
            r_conf = getattr(r, "confirmado", None) if hasattr(r, "confirmado") else (r.get("confirmado") if isinstance(r, dict) else True)
            r_cita = getattr(r, "cita_textual", None) if hasattr(r, "cita_textual") else (r.get("cita_textual") if isinstance(r, dict) else None)

            if r_origen == "supuesto" and r_cifra and not r_conf:
                findings.append(f"Requisito '{r_id}' es un supuesto con cifras numéricas y requiere confirmación del cliente antes de estimar")

            if r_origen == "explicito" and tech_justifications and not r_cita:
                findings.append(f"Requisito '{r_id}' marcado como explícito pero carece de cita_textual verificable")

    # 8. Alertas paramétricas (warnings no bloqueantes)
    if total_expected > 0:
        # Ratio Gestión de Proyecto / PM: 8% a 18%
        pm_hours = sum(
            a.expected_hours
            for a in activities
            if any(k in a.profile.lower() or k in a.phase.lower() for k in ["jefe de proyecto", "gestion_proyecto", "project", "pm", "gestión"])
        )
        pm_ratio = (pm_hours / total_expected) * 100.0
        if pm_hours > 0 and (pm_ratio < 8.0 or pm_ratio > 18.0):
            warnings.append(f"Ratio de Gestión de Proyecto ({round(pm_ratio, 1)}%) fuera del rango paramétrico recomendado (8% - 18%)")

        # Ratio QA: 12% a 30%
        qa_hours = sum(
            a.expected_hours
            for a in activities
            if any(k in a.profile.lower() or k in a.phase.lower() or k in a.name.lower() for k in ["qa", "prueb", "test"])
        )
        qa_ratio = (qa_hours / total_expected) * 100.0
        if qa_hours > 0 and (qa_ratio < 12.0 or qa_ratio > 30.0):
            warnings.append(f"Ratio de QA ({round(qa_ratio, 1)}%) fuera del rango paramétrico recomendado (12% - 30%)")

    # 9. Integración externa < 24h cuando api_documentada es False
    for a in activities:
        api_doc = getattr(a, "api_documentada", True)
        if not api_doc and a.expected_hours < 24.0:
            warnings.append(f"Actividad de integración externa '{a.name}' tiene {a.expected_hours}h esperadas (< 24h) con API no documentada")

    return findings, warnings


def audit_estimation(
    activities: list[Activity],
    plan: Plan,
    rates: dict[str, dict[str, Any]],
    similar_hist: list[dict[str, Any]],
    infra_profile: str = "vps",
    tech_justifications: list[Any] | None = None,
    requirements: list[Any] | None = None,
) -> list[str]:
    findings, _ = validate_estimation_rules(
        activities=activities,
        plan=plan,
        rates=rates,
        similar_hist=similar_hist,
        infra_profile=infra_profile,
        tech_justifications=tech_justifications,
        requirements=requirements,
    )
    return findings
