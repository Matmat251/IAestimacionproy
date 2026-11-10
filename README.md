# Prototipo de Sistema Multiagente para Estimación de Proyectos TI

Sistema multiagente modular para registrar proyectos de software, estructurar requisitos con trazabilidad, diseñar la WBS encadenada por dependencias, recomendar stacks austeros basados en catálogo de infraestructura, estimar esfuerzo con PERT y calcular personal, costos y riesgos, respaldado por auditoría determinista y datos de referencia.

## Flujo de 6 Agentes (LangGraph)

1. **Orquestador (Python determinista)**: Carga tarifas por perfil e históricos comparables de la empresa para inicializar el estado del grafo.
2. **Analista (LLM + Trazabilidad)**: Extrae requerimientos estructurados con IDs (`R1`, `R2`, ...), clasificación de origen (`explicito`, `implicito`, `supuesto`), cita textual y detección de cifras cuantitativas con bloqueo de supuestos no confirmados.
3. **Arquitecto (LLM + Catálogo Controlado)**: Evalúa el perfil de infraestructura (`hosting_compartido`, `vps`, `cloud`), selecciona el stack más austero según `catalogo_stacks.json`, genera justificaciones técnicas con alternativas descartadas y diseña la WBS con dependencias.
4. **Estimador (LLM + PERT)**: Asigna horas PERT (Optimista, Más probable, Pesimista) ajustadas por complejidad e históricos, corrigiendo desviaciones reportadas por el auditor.
5. **Planificador (Python determinista)**: Agrupa horas por perfil, calcula el personal óptimo y costo total según tarifas reales, y determina la ruta crítica (CPM) del proyecto.
6. **Auditor (Python determinista)**: Valida consistencia (O ≤ M ≤ P, horas > 0, tarifas registradas, fase QA, compatibilidad de infraestructura, ratios de PM 8–18% y QA 12–30%, e integraciones externas < 24h). Permite hasta 2 reajustes automáticos con el estimador.

## Arquitectura por Capas

```
backend/app/
├── agents/                       # Capa de Agentes Especializados (Modular)
│   ├── state.py                  # Contrato de datos y AgentState común
│   ├── llm.py                    # Cliente LLM con salida estructurada JSON
│   ├── orchestrator.py           # Agente Orquestador (Carga RAG de tarifas e históricos)
│   ├── analyst.py                # Agente Analista (Requerimientos y preguntas de aclaración)
│   ├── architect.py              # Agente Arquitecto (WBS, tecnologías y riesgos)
│   ├── estimator.py              # Agente Estimador (Puntos PERT y escala de complejidad)
│   ├── planner.py                # Agente Planificador (Ruta crítica y staffing)
│   ├── auditor.py                # Agente Auditor (Validación de reglas y re-estimación)
│   └── graph.py                  # Ensamblado del StateGraph en LangGraph
├── planning.py                   # Algoritmos deterministas (CPM, PERT, Staffing)
├── reference.py                  # Servicios de datos de referencia (CSV/Excel)
├── store.py                      # Persistencia en SQLite
├── main.py                       # API REST FastAPI y generación de PDF/XLSX
└── agent.py                      # Fachada de compatibilidad (100% retrocompatible)
```

## Stack Tecnológico

- **Frontend**: React 18, TypeScript, Vite, Tailwind-like styling, Lucide React.
- **Backend**: Python 3.12, FastAPI, Pydantic v2, LangGraph, ReportLab, openpyxl, SQLite3.
- **Inferencia LLM**: Groq API (`openai/gpt-oss-120b` o `qwen/qwen3.8-27b`) con modo de respaldo determinista local en caso de ausencia de API Key o fallos de red.
- **Persistencia**: SQLite local (`backend/data/app.db`).
- **Datos de referencia**: Archivos CSV/XLSX (`backend/data/tarifas.csv`, `backend/data/historicos.csv`) y catálogo de infraestructura (`backend/data/catalogo_stacks.json`).

## Arranque del Proyecto

### Requisitos previos
- Python 3.12+
- Node.js 18+

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Configura tu GROQ_API_KEY en .env (o déjala vacía para operar en modo determinista local)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API interactiva y documentación OpenAPI: `http://127.0.0.1:8000/docs`

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

La interfaz web estará disponible en `http://localhost:5173`.

## Pruebas Automatizadas

Ejecutar la suite completa de pruebas del backend (18 tests):

```powershell
cd backend
python -m pytest -v
```

Construir el frontend para producción:

```powershell
cd frontend
npm run build
```

## Informes y Exportación

- **PDF**: Informe detallado con resumen gerencial, perfil de infraestructura, desglose WBS, personal y costos, riesgos y observaciones de auditoría.
- **Excel (.xlsx)**: Cuatro hojas estructuradas (`Resumen`, `WBS`, `Personal y Costos`, `Riesgos y Auditoria`).
