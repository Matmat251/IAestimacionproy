from collections import Counter
import csv
import io
import json
import math
from pathlib import Path
import re
from typing import Any, Literal
import unicodedata
import openpyxl

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TARIFAS_PATH = DATA_DIR / "tarifas.csv"
HISTORICOS_PATH = DATA_DIR / "historicos.csv"
CATALOGO_STACKS_PATH = DATA_DIR / "catalogo_stacks.json"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"


def load_knowledge_text() -> str:
    """Devuelve los CSV de conocimiento como texto compacto para el prompt del LLM."""
    parts = []
    for name in ("benchmarks_actividades.csv", "distribucion_fases.csv", "factores_ajuste.csv"):
        path = KNOWLEDGE_DIR / name
        if path.exists():
            parts.append(f"### {name}\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts)


def load_knowledge_summary() -> dict[str, Any]:
    """Devuelve un resumen consolidado de la base de conocimiento para la API y UI."""
    benchmarks_path = KNOWLEDGE_DIR / "benchmarks_actividades.csv"
    benchmarks_rows: list[dict[str, Any]] = []
    if benchmarks_path.exists():
        with open(benchmarks_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            benchmarks_rows = [
                {
                    "tipo_actividad": (row.get("tipo_actividad") or "").strip(),
                    "unidad": (row.get("unidad") or "").strip(),
                    "perfil": (row.get("perfil") or "").strip(),
                    "horas_min": float(row.get("horas_min") or 0.0),
                    "horas_tipicas": float(row.get("horas_tipicas") or 0.0),
                    "horas_max": float(row.get("horas_max") or 0.0),
                    "nota": (row.get("nota") or "").strip(),
                }
                for row in reader
                if (row.get("tipo_actividad") or "").strip()
            ]

    distribucion_path = KNOWLEDGE_DIR / "distribucion_fases.csv"
    phases_rows: list[dict[str, Any]] = []
    if distribucion_path.exists():
        with open(distribucion_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            phases_rows = [
                {
                    "fase": (row.get("fase") or "").strip(),
                    "pct_min": float(row.get("pct_min") or 0.0),
                    "pct_tipico": float(row.get("pct_tipico") or 0.0),
                    "pct_max": float(row.get("pct_max") or 0.0),
                    "nota": (row.get("nota") or "").strip(),
                }
                for row in reader
                if (row.get("fase") or "").strip()
            ]

    factores_path = KNOWLEDGE_DIR / "factores_ajuste.csv"
    factors_count = 0
    if factores_path.exists():
        with open(factores_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            factors_count = sum(1 for row in reader if (row.get("factor") or "").strip())

    history = load_history()

    return {
        "benchmarks_count": len(benchmarks_rows),
        "phases_distribution": phases_rows,
        "distribucion_fases": phases_rows,
        "factors_count": factors_count,
        "historical_projects_count": len(history),
        "benchmarks_actividades": benchmarks_rows,
    }

DEFAULT_STACK_CATALOG = {
    "hosting_compartido": {
        "permitido": ["PHP", "Laravel", "MySQL", "MariaDB", "Composer", "GitHub Actions", "Sharp_via_PHP_GD", "HTML/CSS/JS"],
        "prohibido": ["Docker", "Kubernetes", "Nginx_propio", "Nginx", "Kafka", "Redis", "microservicios"],
        "nota": "Verificar si el plan incluye Node.js antes de proponerlo",
    },
    "vps": {
        "permitido": ["Node.js", "PHP", "FastAPI (Python)", "FastAPI", "Python", "React", "Next.js", "TypeScript", "Docker", "Nginx", "PostgreSQL", "MySQL", "Redis"],
        "prohibido": ["Kubernetes", "Kafka", "microservicios"],
    },
    "cloud": {
        "permitido": ["servicios_gestionados", "React", "React Native", "Next.js", "TypeScript", "FastAPI (Python)", "FastAPI", "Node.js", "PostgreSQL", "PostgreSQL + pgvector", "Redis", "Docker", "Docker + CI/CD", "Kubernetes", "Kafka", "API Gateway / Colas de mensajería", "LangGraph"],
        "prohibido": [],
    },
    "umbral_complejidad": {
        "kubernetes_kafka_microservicios": {
            "usuarios_concurrentes_explicitos": 1000,
            "eventos_por_dia_explicitos": 500000,
            "equipos_paralelos": 3,
        }
    },
}


def load_stack_catalog() -> dict:
    if not CATALOGO_STACKS_PATH.exists():
        return DEFAULT_STACK_CATALOG
    try:
        with open(CATALOGO_STACKS_PATH, mode="r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_STACK_CATALOG


def load_rates() -> list[dict]:
    if not TARIFAS_PATH.exists():
        return []
    with open(TARIFAS_PATH, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [
            {
                "perfil": (row.get("perfil") or "").strip(),
                "tarifa_hora": float(row.get("tarifa_hora") or 0.0),
                "capacidad_semanal": float(row.get("capacidad_semanal") or 40.0),
            }
            for row in reader
            if (row.get("perfil") or "").strip()
        ]


def rates_by_profile() -> dict[str, dict]:
    return {r["perfil"]: r for r in load_rates()}


def load_history() -> list[dict]:
    if not HISTORICOS_PATH.exists():
        return []
    with open(HISTORICOS_PATH, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [
            {
                "nombre": (row.get("nombre") or "").strip(),
                "tecnologias": (row.get("tecnologias") or "").strip(),
                "complejidad": (row.get("complejidad") or "").strip().lower(),
                "fase": (row.get("fase") or "").strip(),
                "horas_reales": float(row.get("horas_reales") or 0.0),
            }
            for row in reader
            if (row.get("nombre") or "").strip()
        ]


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return norm.lower()


def _extract_ngrams(text: str) -> list[str]:
    norm = _normalize_text(text)
    words = re.findall(r"\b[a-z0-9_]{2,}\b", norm)
    features: list[str] = list(words)
    for w in words:
        if len(w) >= 4:
            for i in range(len(w) - 3):
                features.append(w[i : i + 4])
    return features


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    dot_product = sum(vec_a[k] * vec_b.get(k, 0.0) for k in vec_a if k in vec_b)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def retrieve_similar_rag(
    query_text: str,
    tech: str = "",
    complexity: str = "media",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    # 1. Pool desde CSV
    candidates: list[dict[str, Any]] = [
        {
            "nombre": row.get("nombre", ""),
            "tecnologias": row.get("tecnologias", ""),
            "complejidad": row.get("complejidad", "media"),
            "fase": row.get("fase", "General"),
            "horas_reales": float(row.get("horas_reales", 0.0)),
            "source": "historico_csv",
        }
        for row in load_history()
    ]

    # 2. Pool desde SQLite (estimaciones aprobadas)
    try:
        from .store import list_estimations
        saved = list_estimations()
        for s in saved:
            if s.get("status") == "approved":
                payload_str = s.get("payload_json") or ""
                payload: dict[str, Any] = {}
                if payload_str:
                    try:
                        payload = json.loads(payload_str)
                    except Exception:
                        payload = {}
                techs = ""
                if payload.get("recommended_technologies"):
                    techs = " ".join(payload["recommended_technologies"])
                elif payload.get("project", {}).get("technology"):
                    techs = payload["project"]["technology"]

                candidates.append({
                    "nombre": s.get("project_name") or payload.get("project_name") or "Estimación Aprobada",
                    "tecnologias": techs,
                    "complejidad": payload.get("complexity", "media"),
                    "fase": "General",
                    "horas_reales": float(payload.get("total_expected_hours", 0.0)),
                    "source": "estimacion_aprobada",
                })
    except Exception:
        pass

    if not candidates:
        return []

    # 3. TF-IDF + Cosine Similarity
    full_query = f"{query_text} {tech} {complexity}".strip()
    query_features = _extract_ngrams(full_query)
    doc_features = [
        _extract_ngrams(f"{c['nombre']} {c['tecnologias']} {c['complejidad']} {c['fase']}")
        for c in candidates
    ]

    all_docs = [query_features] + doc_features
    total_docs = len(all_docs)

    df: Counter[str] = Counter()
    for doc in all_docs:
        for t in set(doc):
            df[t] += 1

    idf: dict[str, float] = {
        token: math.log((total_docs + 1) / (count + 1)) + 1.0
        for token, count in df.items()
    }

    q_counts = Counter(query_features)
    query_vec = {t: count * idf.get(t, 1.0) for t, count in q_counts.items()}

    query_tech_words = set(re.findall(r"\w+", (tech or "").lower()))
    comp_target = (complexity or "").strip().lower()

    scored_candidates: list[dict[str, Any]] = []
    for cand, c_feats in zip(candidates, doc_features):
        c_counts = Counter(c_feats)
        cand_vec = {t: count * idf.get(t, 1.0) for t, count in c_counts.items()}
        base_cosine = _cosine_similarity(query_vec, cand_vec)

        cand_tech_words = set(re.findall(r"\w+", (cand["tecnologias"] or "").lower()))
        tech_bonus = 0.0
        if query_tech_words and (query_tech_words & cand_tech_words):
            overlap_count = len(query_tech_words & cand_tech_words)
            tech_bonus = min(0.20, 0.08 * overlap_count)

        comp_bonus = 0.05 if cand["complejidad"].lower() == comp_target else 0.0
        final_score = min(1.0, max(0.0, base_cosine + tech_bonus + comp_bonus))

        item = dict(cand)
        item["similarity"] = round(final_score, 2)
        scored_candidates.append(item)

    scored_candidates.sort(key=lambda x: (x["similarity"], x["horas_reales"]), reverse=True)
    return scored_candidates[:top_k]


def similar_history(tech: str, complexity: str, query_text: str = "") -> list[dict]:
    if query_text:
        return retrieve_similar_rag(query_text=query_text, tech=tech, complexity=complexity)
    history = load_history()
    if not history:
        return []
    tech_words = set(re.findall(r"\w+", (tech or "").lower()))
    comp_norm = (complexity or "").strip().lower()
    matches = [
        item
        for item in history
        if (tech_words and (tech_words & set(re.findall(r"\w+", item["tecnologias"].lower()))))
        or (comp_norm and item["complejidad"] == comp_norm)
    ]
    res = matches if matches else history
    # shortcut: compatibilidad retroactiva de atributos source y similarity
    for item in res:
        if "source" not in item:
            item["source"] = "historico_csv"
        if "similarity" not in item:
            item["similarity"] = 0.5
    return res


def import_file(kind: Literal["tarifas", "historicos"], filename: str, content: bytes) -> int:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in ("csv", "xlsx"):
        raise ValueError(f"Extensión no permitida: .{ext}. Solo se admiten archivos .csv o .xlsx")

    raw_rows: list[dict[str, str]] = []
    if ext == "csv":
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("El archivo CSV está vacío o no contiene encabezados")
        raw_rows = [{k: (v or "").strip() for k, v in row.items() if k is not None} for row in reader]
    else:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        sheet = wb.active
        data_rows = list(sheet.iter_rows(values_only=True))
        if not data_rows:
            raise ValueError("El archivo Excel está vacío")
        header = [str(col).strip() if col is not None else "" for col in data_rows[0]]
        for row in data_rows[1:]:
            if all(cell is None or str(cell).strip() == "" for cell in row):
                continue
            row_dict = {}
            for idx, col_name in enumerate(header):
                if col_name and idx < len(row):
                    val = row[idx]
                    row_dict[col_name] = str(val).strip() if val is not None else ""
            raw_rows.append(row_dict)

    if not raw_rows:
        raise ValueError("El archivo no contiene filas de datos")

    if kind == "tarifas":
        required = {"perfil", "tarifa_hora", "capacidad_semanal"}
        header_keys = set(raw_rows[0].keys())
        missing = required - header_keys
        if missing:
            raise ValueError(f"Faltan columnas requeridas en tarifas: {', '.join(sorted(missing))}")

        validated: list[dict] = []
        for idx, row in enumerate(raw_rows, start=1):
            perfil = row.get("perfil", "").strip()
            if not perfil:
                raise ValueError(f"Fila {idx}: el campo 'perfil' no puede estar vacío")
            try:
                tarifa = float(row.get("tarifa_hora", ""))
                capacidad = float(row.get("capacidad_semanal", ""))
            except (ValueError, TypeError):
                raise ValueError(f"Fila {idx}: 'tarifa_hora' y 'capacidad_semanal' deben ser números")
            if tarifa <= 0 or capacidad <= 0:
                raise ValueError(f"Fila {idx}: 'tarifa_hora' y 'capacidad_semanal' deben ser mayores a 0")
            validated.append({"perfil": perfil, "tarifa_hora": tarifa, "capacidad_semanal": capacidad})
        fieldnames = ["perfil", "tarifa_hora", "capacidad_semanal"]
        target_path = TARIFAS_PATH
    elif kind == "historicos":
        required = {"nombre", "tecnologias", "complejidad", "fase", "horas_reales"}
        header_keys = set(raw_rows[0].keys())
        missing = required - header_keys
        if missing:
            raise ValueError(f"Faltan columnas requeridas en historicos: {', '.join(sorted(missing))}")

        validated = []
        for idx, row in enumerate(raw_rows, start=1):
            nombre = row.get("nombre", "").strip()
            tecnologias = row.get("tecnologias", "").strip()
            complejidad = row.get("complejidad", "").strip().lower()
            fase = row.get("fase", "").strip()
            if not (nombre and tecnologias and complejidad and fase):
                raise ValueError(f"Fila {idx}: faltan campos de texto obligatorios")
            try:
                horas = float(row.get("horas_reales", ""))
            except (ValueError, TypeError):
                raise ValueError(f"Fila {idx}: 'horas_reales' debe ser un número")
            if horas <= 0:
                raise ValueError(f"Fila {idx}: 'horas_reales' debe ser mayor a 0")
            validated.append({
                "nombre": nombre,
                "tecnologias": tecnologias,
                "complejidad": complejidad,
                "fase": fase,
                "horas_reales": horas,
            })
        fieldnames = ["nombre", "tecnologias", "complejidad", "fase", "horas_reales"]
        target_path = HISTORICOS_PATH
    else:
        raise ValueError(f"Tipo no válido: {kind}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(validated)

    return len(validated)
