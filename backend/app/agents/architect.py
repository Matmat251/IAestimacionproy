from copy import deepcopy
import json
import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..config import settings
from ..models import DiscardedAlternative, Risk, TechJustification
from ..reference import load_stack_catalog
from .llm import call_llm
from .state import BASE_ACTIVITIES, BASE_RISKS, AgentState

logger = logging.getLogger(__name__)


class ArchActivity(BaseModel):
    id: str = "A1"
    phase: str = "Desarrollo"
    name: str = "Actividad"
    profile: str = "Desarrollador"
    categoria: str = "desarrollo"
    requisitos_ids: list[str] = Field(default_factory=list)
    api_documentada: bool = True
    depends_on: list[str] = Field(default_factory=list)
    optimistic_hours: float = 4.0
    most_likely_hours: float = 10.0
    pessimistic_hours: float = 20.0
    rationale: str = ""


class ArchResponse(BaseModel):
    complexity: Literal["baja", "media", "alta"] = "media"
    infra_profile: Literal["hosting_compartido", "vps", "cloud"] = "vps"
    recommended_technologies: list[str] = Field(default_factory=list)
    tech_justifications: list[TechJustification] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    activities: list[ArchActivity] = Field(default_factory=list)


def detect_infra_profile(p) -> Literal["hosting_compartido", "vps", "cloud"]:
    text = f"{p.constraints} {p.technology} {p.description}".lower()
    if any(k in text for k in ["compartido", "cpanel", "hostinger"]):
        return "hosting_compartido"
    if any(k in text for k in ["aws", "gcp", "azure", "cloud"]):
        return "cloud"
    return "vps"


def build_tech_justifications(
    p,
    infra_profile: Literal["hosting_compartido", "vps", "cloud"],
    req_ids: list[str],
    restr_ids: list[str],
) -> list[dict[str, Any]]:
    catalogo = load_stack_catalog()
    prohibido = [x.lower() for x in catalogo.get(infra_profile, {}).get("prohibido", [])]
    text = f"{p.name} {p.description} {p.scope} {p.technology} {p.integrations} {p.constraints}".lower()

    items: list[tuple[str, str, str, str, str]] = []

    if infra_profile == "hosting_compartido":
        items.append(("PHP", "backend", "Adecuado para hosting compartido sin soporte de containers daemon", "Node.js", "Requiere soporte específico de runtime en el hosting"))
        items.append(("Laravel", "framework", "Framework robusto y soportado nativamente en PHP compartido", "Symfony", "Mayor complejidad inicial de configuración"))
        items.append(("MySQL", "database", "Base de datos relacional estándar soportada en hosting compartido", "PostgreSQL", "Generalmente no disponible en hosting compartido básico"))
        items.append(("HTML/CSS/JS", "frontend", "Frontend ligero compatible con entrega directa", "SPA pesada", "Sobrecarga innecesaria de bundle"))
    elif infra_profile == "cloud":
        if any(w in text for w in ["movil", "móvil", "mobile", "ios", "android", "app"]):
            items.append(("React Native", "frontend", "Desarrollo móvil multiplataforma eficiente", "Flutter", "Equipo con mayor base en ecosistema JS/TS"))
            items.append(("TypeScript", "lenguaje", "Seguridad de tipos y mantenibilidad", "JavaScript", "Menor control de tipos en producción"))
            items.append(("FastAPI (Python)", "backend", "Alto rendimiento asíncrono y documentación automática", "Django", "Mayor sobrecarga de configuración"))
            items.append(("PostgreSQL", "database", "Base de datos relacional escalable en la nube", "MySQL", "Menor flexibilidad con tipos avanzados"))
        elif any(w in text for w in ["ecommerce", "e-commerce", "tienda", "pago", "carrito", "stripe", "pasarela"]):
            items.append(("Next.js", "frontend", "Renderizado híbrido y optimización SEO para e-commerce", "React SPA", "SEO deficiente para catálogo público"))
            items.append(("TypeScript", "lenguaje", "Tipado estricto en flujos de pago", "JavaScript", "Riesgo de errores en runtime"))
            items.append(("FastAPI (Python)", "backend", "APIs rápidas para transacciones y checkout", "Express.js", "Menor soporte nativo para validación tipada"))
            items.append(("PostgreSQL", "database", "Consistencia ACID para órdenes y transacciones", "MongoDB", "Transaccionalidad compleja"))
            items.append(("Redis", "cache", "Gestión de sesiones y carritos en memoria", "Memcached", "Sin soporte de estructuras de datos ricas"))
        elif any(w in text for w in ["ia", "ai", "agente", "llm", "analitica", "analítica", "datos", "bi", "rag"]):
            items.append(("React", "frontend", "Interfaz reactiva para dashboards interactivos", "Vue", "Ecosistema menor en componentes analíticos"))
            items.append(("FastAPI (Python)", "backend", "Ecosistema Python óptimo para integración con modelos de IA", "Node.js", "Menor soporte nativo de bibliotecas de ML/IA"))
            items.append(("PostgreSQL + pgvector", "database", "Almacenamiento relacional y vectorial integrado en un único motor", "Pinecone", "Costo adicional y fragmentación de datos"))
            items.append(("LangGraph", "framework_ia", "Orquestación de flujos de agentes y estado de IA", "Llamaindex", "Menor control de bucles y ciclos de agentes"))
        else:
            items.append(("React", "frontend", "Frontend modular y ampliamente soportado", "Angular", "Mayor curva de aprendizaje y boilerplate"))
            items.append(("TypeScript", "lenguaje", "Tipado estático para código mantenible", "JavaScript", "Falta de verificación en tiempo de compilación"))
            items.append(("FastAPI (Python)", "backend", "Backend moderno, rápido y con validación automática", "Flask", "Falta de soporte asíncrono nativo moderno"))
            items.append(("PostgreSQL", "database", "Base de datos relacional robusta con soporte ACID completo", "MySQL", "Menor soporte de extensiones avanzadas"))

        if any(w in text for w in ["sap", "erp", "soap", "legacy", "extern"]):
            items.append(("API Gateway / Colas de mensajería", "integracion", "Desacoplamiento seguro de sistemas legacy o ERP", "Integración sincrónica directa", "Riesgo de caídas en cascada y timeouts"))
        if any(w in text for w in ["alta disponibilidad", "cloud", "aws", "gcp", "azure", "docker", "escala"]):
            items.append(("Docker + CI/CD", "devops", "Contenedores portables y despliegue automatizado", "Despliegue manual SSH", "Alto riesgo de error humano y falta de reproducibilidad"))
    else:  # vps
        items.append(("React", "frontend", "Interfaz web dinámica y mantenible", "Angular", "Mayor boilerplate"))
        items.append(("TypeScript", "lenguaje", "Tipado estático para el frontend y contratos", "JavaScript", "Falta de tipado"))
        items.append(("FastAPI (Python)", "backend", "Backend ligero de alto rendimiento sobre VPS", "Django", "Sobrecarga innecesaria para servicios enfocados"))
        items.append(("PostgreSQL", "database", "Persistencia relacional confiable y transaccional", "MySQL", "Menos funciones analíticas avanzadas"))
        items.append(("Docker", "infraestructura", "Contenedorización en VPS para aislamiento y despliegue limpio", "Instalación bare-metal", "Dificultad de actualización y dependencias de SO"))
        items.append(("Nginx", "webserver", "Reverse proxy y terminación SSL eficiente en VPS", "Apache", "Mayor consumo de memoria"))

    # Umbrales para tecnologías complejas (Kubernetes, Kafka, microservicios)
    # Solo permitidas si se superan explícitamente métricas masivas
    has_massive_users = any(int(m) >= 1000 for m in re.findall(r"\b(\d+)\s*(?:usuarios|concurren)", text))
    has_massive_events = any(int(m) >= 500000 for m in re.findall(r"\b(\d+)\s*(?:eventos|transacc)", text))
    allow_complex_scale = has_massive_users or has_massive_events

    res: list[dict[str, Any]] = []
    seen = set()
    default_reqs = req_ids[:2] if req_ids else ["R1"]
    default_restr = restr_ids[:2] if restr_ids else []

    for nombre, cat, just, alt_n, alt_m in items:
        # Check against prohibited
        if any(p_item in nombre.lower() for p_item in prohibido):
            continue
        if not allow_complex_scale and any(k in nombre.lower() for k in ["kubernetes", "kafka", "microservicios"]):
            continue
        if nombre.lower() in seen:
            continue
        seen.add(nombre.lower())
        res.append({
            "nombre": nombre,
            "categoria": cat,
            "justificacion": just,
            "requisitos_ids": default_reqs,
            "restricciones_ids": default_restr,
            "alternativas_descartadas": [{"nombre": alt_n, "motivo": alt_m}],
            "compatible_con_infra": True,
        })
    return res


def recommend_technologies(p) -> list[str]:
    infra_profile = detect_infra_profile(p)
    tj = build_tech_justifications(p, infra_profile, ["R1"], [])
    return [t["nombre"] for t in tj]


def normalize_profile(raw_profile: str, valid_profiles: list[str]) -> str:
    raw_lower = raw_profile.lower()
    for vp in valid_profiles:
        if vp.lower() == raw_lower or vp.lower() in raw_lower or raw_lower in vp.lower():
            return vp
    if any(k in raw_lower for k in ["dev", "desarr", "backend", "frontend", "mobile", "fullstack", "engineer", "ingeniero"]):
        return "Desarrollador"
    if any(k in raw_lower for k in ["qa", "test", "prueb", "calidad"]):
        return "QA"
    if any(k in raw_lower for k in ["arq", "arch", "lead", "lider", "líder", "solution"]):
        return "Arquitecto / Tech Lead"
    if any(k in raw_lower for k in ["analis", "analys", "funcional", "product", "negocio"]):
        return "Analista funcional"
    if any(k in raw_lower for k in ["devops", "cloud", "infra", "sre", "sysadmin"]):
        return "DevOps"
    if any(k in raw_lower for k in ["jefe", "pm", "project", "gerente", "scrum"]):
        return "Jefe de proyecto"
    return valid_profiles[0] if valid_profiles else "Desarrollador"


def arquitecto_node(state: AgentState) -> dict[str, Any]:
    p = state["request"].project
    notes: list[str] = []
    valid_profiles = list(state.get("rates", {}).keys()) or [
        "Analista funcional",
        "Arquitecto / Tech Lead",
        "Desarrollador",
        "QA",
        "DevOps",
        "Jefe de proyecto",
    ]

    infra_profile = detect_infra_profile(p)
    catalogo = load_stack_catalog()
    prohibido_list = catalogo.get(infra_profile, {}).get("prohibido", [])

    complexity: Literal["baja", "media", "alta"] = "media"
    combined_text = f"{p.name} {p.description} {p.scope} {p.technology}".lower()
    if any(w in combined_text for w in ["alta", "complejo", "distribuido"]):
        complexity = "alta"
    elif any(w in combined_text for w in ["baja", "simple", "landing", "estático"]):
        complexity = "baja"

    raw_reqs = state.get("requirements", [])
    req_ids = [r["id"] for r in raw_reqs if r.get("id")] or ["R1"]
    restr_ids = [r["id"] for r in raw_reqs if r.get("kind") == "non_functional" and r.get("id")]

    # Exclusión de supuestos cuantitativos no confirmados
    unconfirmed_numeric = [
        r for r in raw_reqs
        if r.get("requiere_confirmacion") and not r.get("confirmado")
    ]
    if unconfirmed_numeric:
        u_ids = [r.get("id", "R?") for r in unconfirmed_numeric]
        notes.append(
            f"Se excluyeron del dimensionamiento {len(unconfirmed_numeric)} supuesto(s) cuantitativo(s) sin confirmar ({', '.join(u_ids)})."
        )

    activities = deepcopy(BASE_ACTIVITIES)
    risks = deepcopy(BASE_RISKS)
    tech_justifications = build_tech_justifications(p, infra_profile, req_ids, restr_ids)
    recommended_technologies = [t["nombre"] for t in tech_justifications]

    if p.completed_work.strip():
        notes.append(
            "Se consideró el trabajo ya ejecutado; se redujo el alcance de desarrollo y diseño para evitar duplicidades."
        )
        for act in activities:
            if act["phase"] == "Desarrollo":
                act["rationale"] += f" (Alcance ajustado por trabajo ya ejecutado: {p.completed_work.strip()[:60]})."
                act["optimistic_hours"] = max(4.0, round(act["optimistic_hours"] * 0.7, 1))
                act["most_likely_hours"] = max(8.0, round(act["most_likely_hours"] * 0.7, 1))
                act["pessimistic_hours"] = max(16.0, round(act["pessimistic_hours"] * 0.7, 1))

    if settings.groq_api_key:
        profiles_list_str = ", ".join(valid_profiles)
        prompt = (
            f"Diseña la WBS (actividades encadenadas por dependencias), recomienda el stack tecnológico "
            f"ideal según el perfil de infraestructura y requerimientos, e identifica riesgos:\n"
            f"Nombre: {p.name}\nDescripción: {p.description}\nAlcance: {p.scope}\n"
            f"Tecnología indicada: {p.technology}\nIntegraciones: {p.integrations}\n"
            f"Restricciones: {p.constraints}\nTrabajo ya realizado: {p.completed_work}\n"
            f"Perfil de infraestructura: {infra_profile}\n"
            f"Requerimientos detectados: {json.dumps(raw_reqs[:8], ensure_ascii=False)}\n\n"
            f"7 REGLAS ESTRICTAS DE ARQUITECTURA:\n"
            f"1. Stack más austero: Escoge la solución tecnológica más simple y económica que resuelva el alcance.\n"
            f"2. Respetar catálogo de infraestructura: Para '{infra_profile}' están estrictamente prohibidas: {json.dumps(prohibido_list)}.\n"
            f"3. Trazabilidad: Cada tecnología en 'tech_justifications' debe justificar su elección con 'requisitos_ids' o 'restricciones_ids'.\n"
            f"4. Prohibición de tecnologías sobredimensionadas ('por si acaso'): NUNCA propongas Kubernetes, Kafka ni microservicios sin cifras explícitas masivas (>1000 usuarios concurrentes o >500k eventos/día).\n"
            f"5. Alternativas descartadas: Cada tecnología recomendada debe incluir al menos una alternativa descartada con su motivo en 'alternativas_descartadas'.\n"
            f"6. Metadatos de Actividades: Cada actividad debe especificar 'categoria', 'requisitos_ids' y 'api_documentada'.\n"
            f"7. Exclusión de supuestos cuantitativos: Ignora supuestos numéricos no confirmados por el cliente.\n\n"
            f"Regla de perfiles: Para el campo 'profile' de cada actividad, asigna uno de los siguientes roles exactos: {profiles_list_str}."
        )
        try:
            res = call_llm(prompt, ArchResponse)
            complexity = res.complexity

            # Validar y procesar tech_justifications
            if res.tech_justifications:
                cleaned_tj = []
                for tj in res.tech_justifications:
                    tj_dict = tj.model_dump()
                    # Verificar contra tecnologías prohibidas
                    if any(p_item.lower() in tj_dict["nombre"].lower() for p_item in prohibido_list):
                        continue
                    if not tj_dict.get("requisitos_ids"):
                        tj_dict["requisitos_ids"] = req_ids[:1]
                    if not tj_dict.get("alternativas_descartadas"):
                        tj_dict["alternativas_descartadas"] = [{"nombre": "Alternativa genérica", "motivo": "Mayor complejidad o menor ajuste al perfil"}]
                    cleaned_tj.append(tj_dict)
                if cleaned_tj:
                    tech_justifications = cleaned_tj
                    recommended_technologies = [t["nombre"] for t in tech_justifications]

            if res.risks:
                risks = [r.model_dump() for r in res.risks]

            if res.activities:
                activities = [
                    {
                        "id": a.id,
                        "phase": a.phase,
                        "name": a.name,
                        "profile": normalize_profile(a.profile, valid_profiles),
                        "categoria": a.categoria or "desarrollo",
                        "requisitos_ids": a.requisitos_ids or req_ids[:1],
                        "api_documentada": a.api_documentada,
                        "depends_on": a.depends_on,
                        "optimistic_hours": max(1.0, float(a.optimistic_hours or 4.0)),
                        "most_likely_hours": max(max(1.0, float(a.optimistic_hours or 4.0)), float(a.most_likely_hours or 10.0)),
                        "pessimistic_hours": max(max(1.0, float(a.most_likely_hours or 10.0)), float(a.pessimistic_hours or 20.0)),
                        "rationale": a.rationale or f"Actividad de {a.phase}",
                    }
                    for a in res.activities
                ]
        except Exception:
            logger.exception("Error llamando al Arquitecto con LLM")
            notes.append("Arquitecto LLM no disponible; se usó WBS y recomendación tecnológica demostrativa.")

    return {
        "complexity": complexity,
        "infra_profile": infra_profile,
        "tech_justifications": tech_justifications,
        "recommended_technologies": recommended_technologies,
        "risks": risks,
        "activities": activities,
        "notes": notes,
    }
