from typing import Any

from ..config import settings
from ..reference import rates_by_profile, similar_history
from .state import AgentState


def orquestador_node(state: AgentState) -> dict[str, Any]:
    project = state["request"].project
    rates = rates_by_profile()
    history = similar_history(project.technology, "media")
    notes = []
    if not settings.groq_api_key:
        notes.append("Modo demo: configura GROQ_API_KEY para activar inferencia con LLM.")
    return {
        "rates": rates,
        "similar_history": history,
        "iterations": 0,
        "notes": notes,
    }
