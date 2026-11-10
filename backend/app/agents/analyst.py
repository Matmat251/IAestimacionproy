import json
import logging
import re
from typing import Any

from pydantic import BaseModel

from ..config import settings
from ..models import Requirement
from .llm import call_llm
from .state import REQUIRED, AgentState

logger = logging.getLogger(__name__)


class AnalystResponse(BaseModel):
    requirements: list[Requirement] = []
    sufficient: bool = True
    additional_questions: list[str] = []


def analista_node(state: AgentState) -> dict[str, Any]:
    p = state["request"].project
    answers = state["request"].clarification_answers
    notes: list[str] = []

    missing = [
        key
        for key, label in REQUIRED.items()
        if not getattr(p, key, "").strip() and not answers.get(key, "").strip()
    ]
    questions = [f"{REQUIRED[key]}: ¿qué información debemos considerar?" for key in missing]

    reqs: list[dict[str, Any]] = []
    sufficient = len(missing) == 0

    if settings.groq_api_key:
        prompt = (
            f"Analiza la información del proyecto y extrae requerimientos técnicos y funcionales.\n"
            f"Proyecto: {p.name}\nDescripción: {p.description}\nAlcance: {p.scope}\n"
            f"Tecnología: {p.technology}\nIntegraciones: {p.integrations}\n"
            f"Restricciones: {p.constraints}\nRespuestas de aclaración previas: {json.dumps(answers, ensure_ascii=False)}\n\n"
            f"Reglas para Requerimientos:\n"
            f"1. Asigna un ID secuencial a cada requerimiento (R1, R2, R3, ...).\n"
            f"2. Clasifica 'origen' como 'explicito' (incluye cita textual en 'cita_textual'), 'implicito', o 'supuesto'.\n"
            f"3. Si el detalle contiene cifras o métricas cuantitativas, establece 'contiene_cifra': true.\n"
            f"4. Si 'origen' es 'supuesto' (o kind 'assumption') y 'contiene_cifra' es true, establece 'requiere_confirmacion': true y 'confirmado': false.\n"
            f"5. Si la descripción y el alcance tienen suficiente contexto para una estimación inicial, establece 'sufficient': true.\n"
            f"6. Si faltan datos críticos imprescindibles sin los cuales no es posible estimar, establece 'sufficient': false y agrega preguntas concisas en 'additional_questions'.\n"
            f"7. Si ya se han recibido respuestas de aclaración previas, establece 'sufficient': true."
        )
        try:
            res = call_llm(prompt, AnalystResponse)
            reqs = [r.model_dump() for r in res.requirements]
            if not res.sufficient and res.additional_questions and not answers:
                for q in res.additional_questions:
                    if q not in questions:
                        questions.append(q)
                sufficient = False
            else:
                sufficient = len(missing) == 0
        except Exception:
            logger.exception("Error llamando al Analista con LLM")
            notes.append("Analista LLM no disponible; se procedió con extracción determinista.")

    if not reqs:
        idx = 1
        for label, val in [
            ("Descripción", p.description),
            ("Alcance", p.scope),
            ("Tecnología", p.technology),
            ("Integraciones", p.integrations),
            ("Restricciones", p.constraints),
        ]:
            if val.strip():
                detail = val.strip()
                has_digit = bool(re.search(r"\d+", detail))
                reqs.append({
                    "id": f"R{idx}",
                    "title": label,
                    "detail": detail,
                    "kind": "functional" if label != "Restricciones" else "non_functional",
                    "origen": "explicito",
                    "cita_textual": detail[:120],
                    "contiene_cifra": has_digit,
                    "requiere_confirmacion": False,
                    "confirmado": True,
                    "confidence": 0.85,
                })
                idx += 1

    # Normalización y validación de trazabilidad y requerimientos cuantitativos
    for idx, r in enumerate(reqs, start=1):
        if not r.get("id"):
            r["id"] = f"R{idx}"
        detail = r.get("detail", "")
        has_digit = bool(re.search(r"\d+", detail))
        r["contiene_cifra"] = has_digit
        origen = r.get("origen", "explicito")
        kind = r.get("kind", "functional")
        if origen == "supuesto" or kind == "assumption":
            if has_digit:
                is_confirmed = any(
                    r["id"].lower() in k.lower()
                    or r.get("title", "").lower() in v.lower()
                    or r["id"].lower() in v.lower()
                    for k, v in answers.items()
                )
                r["requiere_confirmacion"] = True
                r["confirmado"] = is_confirmed
            else:
                r["requiere_confirmacion"] = False
                r["confirmado"] = True
        elif origen == "explicito" and not r.get("cita_textual"):
            r["cita_textual"] = detail[:120]

    return {
        "requirements": reqs,
        "missing": missing,
        "questions": questions,
        "sufficient": sufficient and len(missing) == 0,
        "notes": notes,
    }


def route_analista(state: AgentState) -> str:
    if state.get("missing") or not state.get("sufficient", True) or state.get("questions"):
        return "needs_clarification"
    return "proceed"
