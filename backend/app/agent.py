"""Fachada de compatibilidad para el subsistema de agentes.

El flujo se encuentra modularizado en el paquete `app.agents` por capas:
- `app.agents.orchestrator`: Carga de tarifas y proyectos similares.
- `app.agents.analyst`: Extracción de requerimientos y preguntas de aclaración.
- `app.agents.architect`: Desglose de WBS, tecnologías y riesgos.
- `app.agents.estimator`: Aplicación de complejidad y ajuste PERT.
- `app.agents.planner`: Ruta Crítica (CPM) y asignación de staffing/costos.
- `app.agents.auditor`: Reglas de auditoría y ciclo de re-estimación.
- `app.agents.graph`: Ensamblado de StateGraph y compilación.
"""

from .agents.analyst import analista_node, route_analista
from .agents.architect import arquitecto_node, recommend_technologies
from .agents.auditor import auditor_node, route_auditor
from .agents.estimator import estimador_node
from .agents.graph import agent_graph, create_draft
from .agents.orchestrator import orquestador_node
from .agents.planner import planificador_node
from .agents.state import BASE_ACTIVITIES, BASE_RISKS, REQUIRED, AgentState

__all__ = [
    "agent_graph",
    "create_draft",
    "AgentState",
    "orquestador_node",
    "analista_node",
    "arquitecto_node",
    "estimador_node",
    "planificador_node",
    "auditor_node",
    "route_analista",
    "route_auditor",
    "REQUIRED",
    "BASE_ACTIVITIES",
    "BASE_RISKS",
    "recommend_technologies",
]
