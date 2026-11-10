from typing import Annotated, Any, Literal, TypedDict
import operator

from ..models import DraftRequest


REQUIRED = {
    "scope": "Alcance incluido y excluido",
    "integrations": "Integraciones con otros sistemas",
    "constraints": "Restricciones, fechas o requisitos no funcionales",
}

BASE_ACTIVITIES = [
    {
        "id": "A1",
        "phase": "Análisis",
        "name": "Refinamiento de requerimientos",
        "profile": "Analista funcional",
        "categoria": "analisis",
        "requisitos_ids": ["R1"],
        "api_documentada": True,
        "depends_on": [],
        "optimistic_hours": 4.0,
        "most_likely_hours": 8.0,
        "pessimistic_hours": 16.0,
        "rationale": "Base demostrativa; ajustar según alcance y complejidad.",
    },
    {
        "id": "A2",
        "phase": "Diseño",
        "name": "Diseño técnico y arquitectura",
        "profile": "Arquitecto / Tech Lead",
        "categoria": "diseno",
        "requisitos_ids": ["R1"],
        "api_documentada": True,
        "depends_on": ["A1"],
        "optimistic_hours": 4.0,
        "most_likely_hours": 8.0,
        "pessimistic_hours": 16.0,
        "rationale": "Base demostrativa; validar integraciones y restricciones.",
    },
    {
        "id": "A3",
        "phase": "Desarrollo",
        "name": "Implementación de la solución",
        "profile": "Desarrollador",
        "categoria": "desarrollo",
        "requisitos_ids": ["R1"],
        "api_documentada": True,
        "depends_on": ["A2"],
        "optimistic_hours": 16.0,
        "most_likely_hours": 40.0,
        "pessimistic_hours": 80.0,
        "rationale": "Estimación demostrativa; requiere desglose por funcionalidades.",
    },
    {
        "id": "A4",
        "phase": "QA",
        "name": "Pruebas y corrección de defectos",
        "profile": "QA",
        "categoria": "qa",
        "requisitos_ids": ["R1"],
        "api_documentada": True,
        "depends_on": ["A3"],
        "optimistic_hours": 6.0,
        "most_likely_hours": 12.0,
        "pessimistic_hours": 24.0,
        "rationale": "Base demostrativa; confirmar estrategia y cobertura de pruebas.",
    },
    {
        "id": "A5",
        "phase": "Despliegue",
        "name": "Despliegue y transferencia",
        "profile": "DevOps",
        "categoria": "despliegue",
        "requisitos_ids": ["R1"],
        "api_documentada": True,
        "depends_on": ["A4"],
        "optimistic_hours": 2.0,
        "most_likely_hours": 6.0,
        "pessimistic_hours": 12.0,
        "rationale": "Base demostrativa; validar ambientes y plan de liberación.",
    },
]

BASE_RISKS = [
    {
        "description": "Ambigüedad en los requerimientos o integraciones externas poco documentadas",
        "impact": "medio",
        "mitigation": "Sesión técnica de refinamiento y diseño conjunto antes del desarrollo.",
    },
    {
        "description": "Retrasos por dependencias de servicios externos en ambientes de prueba",
        "impact": "alto",
        "mitigation": "Implementar mocks y contratos de prueba desacoplados.",
    },
]


class AgentState(TypedDict, total=False):
    request: DraftRequest
    rates: dict[str, dict[str, Any]]
    similar_history: list[dict[str, Any]]
    requirements: list[dict[str, Any]]
    sufficient: bool
    missing: list[str]
    questions: list[str]
    complexity: Literal["baja", "media", "alta"]
    risks: list[dict[str, Any]]
    activities: list[dict[str, Any]]
    recommended_technologies: list[str]
    infra_profile: Literal["hosting_compartido", "vps", "cloud"]
    tech_justifications: list[dict[str, Any]]
    plan: dict[str, Any]
    audit: dict[str, Any]
    iterations: int
    notes: Annotated[list[str], operator.add]
