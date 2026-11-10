# Base de conocimiento para estimación

| Archivo | Qué es | Quién lo usa |
|---|---|---|
| `benchmarks_actividades.csv` | Rangos de horas (mín/típico/máx) por tipo de actividad. **Referencia de industria, no datos propios.** | Arquitecto (prompt): ancla O/M/P |
| `distribucion_fases.csv` | % de esfuerzo esperado por fase (alineado a fases ISBSG: Plan, Specify, Design, Build, Test, Implement). | Auditor (ratios) y Arquitecto |
| `factores_ajuste.csv` | Multiplicadores por condiciones del proyecto. | Arquitecto (prompt) |
| `plantilla_historico_actividades.csv` | Formato para cargar **proyectos reales** con horas estimadas vs reales por actividad. | Futuro RAG / calibración |

## Prioridad de fuentes
1. Históricos reales de la empresa (plantilla) — la fuente que más mejora la precisión.
2. Benchmarks de este directorio — punto de partida mientras no haya datos propios.
3. Conocimiento general del LLM — solo para descomponer el alcance, nunca para fijar horas.

Ajusta los valores a la realidad de tu equipo; son reglas prácticas, no un estándar.
