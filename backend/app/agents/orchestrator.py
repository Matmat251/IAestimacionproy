from typing import Any

from ..config import settings
from ..reference import rates_by_profile, retrieve_similar_rag
from .state import AgentState


def orquestador_node(state: AgentState) -> dict[str, Any]:
    project = state["request"].project
    rates = rates_by_profile()
    query_text = (
        f"{project.name} {project.description} {project.scope} "
        f"{project.technology} {project.integrations} {project.constraints}"
    ).strip()
    history = retrieve_similar_rag(
        query_text=query_text,
        tech=project.technology,
        complexity="media",
        top_k=5,
    )
    notes = []
    if not settings.groq_api_key:
        notes.append("Modo demo: configura GROQ_API_KEY para activar inferencia con LLM.")
    return {
        "rates": rates,
        "similar_history": history,
        "iterations": 0,
        "notes": notes,
    }
