import csv
import io
import json
from pathlib import Path
import re
from typing import Literal
import openpyxl

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TARIFAS_PATH = DATA_DIR / "tarifas.csv"
HISTORICOS_PATH = DATA_DIR / "historicos.csv"
CATALOGO_STACKS_PATH = DATA_DIR / "catalogo_stacks.json"

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


def similar_history(tech: str, complexity: str) -> list[dict]:
    # shortcut: coincidencia por palabras de tecnología + complejidad; upgrade a embeddings/RAG cuando haya volumen
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
    return matches if matches else history


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
