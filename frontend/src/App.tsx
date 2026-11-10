import { useEffect, useState } from "react";
import { Activity, DraftResponse, SavedEstimation } from "./types";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function App() {
  const [form, setForm] = useState({
    name: "",
    description: "",
    scope: "",
    technology: "",
    integrations: "",
    constraints: "",
    project_status: "new",
    completed_work: "",
  });
  const [draft, setDraft] = useState<DraftResponse | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [reviewState, setReviewState] = useState("");
  const [isWbsDirty, setIsWbsDirty] = useState(false);

  const [ratesCount, setRatesCount] = useState<number | null>(null);
  const [historyCount, setHistoryCount] = useState<number | null>(null);
  const [savedEstimations, setSavedEstimations] = useState<SavedEstimation[]>([]);
  const [refMessage, setRefMessage] = useState("");

  const update = (key: string, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  async function loadReferenceMeta() {
    try {
      const [resRates, resHist, resEst] = await Promise.all([
        fetch(`${API}/api/reference/tarifas`),
        fetch(`${API}/api/reference/historicos`),
        fetch(`${API}/api/estimations`),
      ]);
      if (resRates.ok) {
        const rates = await resRates.json();
        setRatesCount(Array.isArray(rates) ? rates.length : 0);
      }
      if (resHist.ok) {
        const history = await resHist.json();
        setHistoryCount(Array.isArray(history) ? history.length : 0);
      }
      if (resEst.ok) {
        const ests = await resEst.json();
        setSavedEstimations(Array.isArray(ests) ? ests : []);
      }
    } catch {
      // Backend no disponible en carga inicial; se gestionará al accionar
    }
  }

  useEffect(() => {
    loadReferenceMeta();
  }, []);

  async function generate() {
    setLoading(true);
    setError("");
    setReviewState("");
    try {
      const response = await fetch(`${API}/api/estimate/draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project: form, clarification_answers: answers }),
      });
      if (!response.ok)
        throw new Error(`No se pudo generar el borrador (${response.status}).`);
      setDraft(await response.json());
      setIsWbsDirty(false);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Error de conexión con el backend.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function recalculate() {
    if (!draft) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/estimate/recalculate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      if (!response.ok)
        throw new Error(`Error al recalcular (${response.status}).`);
      const updatedDraft = await response.json();
      setDraft(updatedDraft);
      setIsWbsDirty(false);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Error al recalcular la estimación.",
      );
    } finally {
      setLoading(false);
    }
  }

  function updateActivityHours(
    index: number,
    field: "optimistic_hours" | "most_likely_hours" | "pessimistic_hours",
    value: number,
  ) {
    if (!draft) return;
    const newActivities = [...draft.activities];
    const act = { ...newActivities[index], [field]: Math.max(0, value) };
    act.expected_hours = Number(
      ((act.optimistic_hours + 4 * act.most_likely_hours + act.pessimistic_hours) / 6).toFixed(1)
    );
    newActivities[index] = act;
    const newTotal = Number(
      newActivities.reduce((acc, a) => acc + a.expected_hours, 0).toFixed(1)
    );
    setDraft({
      ...draft,
      activities: newActivities,
      total_expected_hours: newTotal,
    });
    setIsWbsDirty(true);
  }

  async function review(approved: boolean) {
    if (!draft) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/estimate/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approved,
          reviewer: "Estimador del proyecto",
          comment: "",
          draft,
        }),
      });
      if (!response.ok) throw new Error("No se pudo registrar la revisión.");
      setReviewState(
        approved
          ? "Estimación aprobada y guardada en el historial."
          : "Se solicitaron ajustes. Actualiza los datos y vuelve a generar el borrador.",
      );
      await loadReferenceMeta();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error de conexión.");
    } finally {
      setLoading(false);
    }
  }

  async function downloadReport(format: "pdf" | "xlsx") {
    if (!draft) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/estimate/report?format=${format}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approved: true,
          reviewer: "Estimador del proyecto",
          comment: "",
          draft,
        }),
      });
      if (!response.ok)
        throw new Error(`No se pudo generar el informe ${format.toUpperCase()}.`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `estimacion-${draft.project_name}.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Error al descargar el informe.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function uploadReference(kind: "tarifas" | "historicos", file: File) {
    setLoading(true);
    setRefMessage("");
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API}/api/reference/${kind}`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Error al importar archivo (${res.status})`);
      }
      const data = await res.json();
      setRefMessage(`Importación exitosa: ${data.rows} filas cargadas en ${kind}.`);
      await loadReferenceMeta();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al subir el archivo.");
    } finally {
      setLoading(false);
    }
  }

  async function loadSaved(id: number) {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/estimations/${id}`);
      if (!res.ok) throw new Error("No se pudo cargar la estimación.");
      const data = await res.json();
      if (data.draft) {
        setDraft(data.draft);
        setIsWbsDirty(false);
        setForm((f) => ({
          ...f,
          name: data.draft.project_name || f.name,
        }));
        setReviewState(
          `Cargada estimación guardada #${id} (${data.status === "approved" ? "Aprobada" : "En ajustes"}).`,
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al consultar estimación.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">E</div>
          <div>
            <strong>Estimador TI</strong>
            <small>Agente de estimación multiagente</small>
          </div>
        </div>
        <div className="top-meta">
          <span className="live-dot" /> 6 Agentes · v0.2
        </div>
      </header>
      <main>
        <section className="intro">
          <div className="eyebrow">SISTEMA MULTIAGENTE DE ESTIMACIÓN</div>
          <h1>Estimemos un proyecto</h1>
          <p>
            Describe el alcance. La cadena de agentes estructurará requisitos,
            diseñará la WBS, estimará el esfuerzo con PERT y calculará costos,
            personal y riesgos antes de auditar el plan.
          </p>
        </section>

        <div className="steps">
          <span className="step active">
            <i>1</i> Información
          </span>
          <b />
          <span className={`step ${draft ? "active" : ""}`}>
            <i>2</i> Análisis & WBS
          </span>
          <b />
          <span
            className={`step ${draft?.status === "ready_for_review" ? "active" : ""}`}
          >
            <i>3</i> Revisión & Auditoría
          </span>
        </div>

        {/* Panel de datos de referencia */}
        <section className="panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">DATOS DE REFERENCIA</div>
              <h2>Tarifas y Proyectos Históricos</h2>
              <p>
                Tarifas por perfil y base histórica usada por el planificador y el auditor.
              </p>
            </div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <span className="pill green">
                {ratesCount !== null ? `${ratesCount} tarifas` : "Cargando…"}
              </span>
              <span className="pill amber">
                {historyCount !== null ? `${historyCount} históricos` : "Cargando…"}
              </span>
            </div>
          </div>
          <div className="form-grid">
            <div>
              <label>
                Actualizar Tarifas (.csv o .xlsx)
                <input
                  type="file"
                  accept=".csv,.xlsx"
                  disabled={loading}
                  onChange={(e) => {
                    if (e.target.files?.[0]) {
                      uploadReference("tarifas", e.target.files[0]);
                      e.target.value = "";
                    }
                  }}
                />
              </label>
            </div>
            <div>
              <label>
                Actualizar Históricos (.csv o .xlsx)
                <input
                  type="file"
                  accept=".csv,.xlsx"
                  disabled={loading}
                  onChange={(e) => {
                    if (e.target.files?.[0]) {
                      uploadReference("historicos", e.target.files[0]);
                      e.target.value = "";
                    }
                  }}
                />
              </label>
            </div>
          </div>
          {refMessage && <div className="alert note">{refMessage}</div>}
        </section>

        {/* Formulario del proyecto */}
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Información del proyecto</h2>
              <p>
                Completa lo que tengas; el analista solicitará aclaraciones si faltan datos clave.
              </p>
            </div>
            <span className="required">* Obligatorio</span>
          </div>
          <div className="form-grid">
            <label className="wide">
              Nombre del proyecto *
              <input
                value={form.name}
                onChange={(e) => update("name", e.target.value)}
                placeholder="Ej. Portal de atención digital"
              />
            </label>
            <label className="wide">
              Descripción y necesidad *
              <textarea
                rows={4}
                value={form.description}
                onChange={(e) => update("description", e.target.value)}
                placeholder="¿Qué necesita el cliente y qué resultado espera?"
              />
            </label>
            <label>
              Estado del proyecto
              <select
                value={form.project_status}
                onChange={(e) => update("project_status", e.target.value)}
              >
                <option value="new">Proyecto nuevo</option>
                <option value="existing">
                  Funcionalidad de sistema existente
                </option>
              </select>
            </label>
            <label>
              Tecnologías (opcional: el Arquitecto recomendará)
              <textarea
                rows={2}
                value={form.technology}
                onChange={(e) => update("technology", e.target.value)}
                placeholder="Déjalo vacío para recomendación automática o indica tu stack"
              />
            </label>
            <label className="wide">
              Alcance incluido y excluido
              <textarea
                rows={2}
                value={form.scope}
                onChange={(e) => update("scope", e.target.value)}
                placeholder="Funciones, usuarios, entregables y exclusiones"
              />
            </label>
            <label>
              Integraciones
              <textarea
                rows={2}
                value={form.integrations}
                onChange={(e) => update("integrations", e.target.value)}
                placeholder="APIs, sistemas o servicios externos"
              />
            </label>
            <label>
              Restricciones
              <textarea
                rows={2}
                value={form.constraints}
                onChange={(e) => update("constraints", e.target.value)}
                placeholder="Fechas, seguridad, rendimiento u otras"
              />
            </label>
            {form.project_status === "existing" && (
              <label className="wide">
                Trabajo ya ejecutado
                <textarea
                  rows={2}
                  value={form.completed_work}
                  onChange={(e) => update("completed_work", e.target.value)}
                  placeholder="Indica qué trabajo debe excluirse de la estimación pendiente"
                />
              </label>
            )}
          </div>
          <div className="form-footer">
            <span>Los campos pueden completarse progresivamente.</span>
            <button
              className="primary"
              onClick={generate}
              disabled={
                loading || form.name.length < 2 || form.description.length < 20
              }
            >
              {loading ? "Analizando…" : "Analizar y estimar"} <span>→</span>
            </button>
          </div>
          {error && <div className="alert error">{error}</div>}
        </section>

        {draft && (
          <section className="results">
            {draft.notes.map((note, i) => (
              <div className="alert note" key={i}>
                {note}
              </div>
            ))}

            {draft.questions.length > 0 && (
              <div className="panel question-panel">
                <div className="panel-heading">
                  <div>
                    <div className="eyebrow">ACLARACIÓN NECESARIA</div>
                    <h2>Antes de estimar, falta contexto</h2>
                    <p>Responde lo que puedas y vuelve a analizar.</p>
                  </div>
                  <span className="pill amber">
                    {draft.questions.length} pendientes
                  </span>
                </div>
                <div className="form-grid">
                  {draft.questions.map((q, i) => {
                    const field = draft.missing_fields[i] || `pregunta_${i}`;
                    return (
                      <label className="wide" key={field}>
                        {q}
                        <textarea
                          rows={2}
                          value={answers[field] || ""}
                          onChange={(e) =>
                            setAnswers((a) => ({
                              ...a,
                              [field]: e.target.value,
                            }))
                          }
                          placeholder="Escribe una respuesta…"
                        />
                      </label>
                    );
                  })}
                </div>
                <div className="right">
                  <button
                    className="primary"
                    onClick={generate}
                    disabled={loading}
                  >
                    Enviar respuestas y continuar →
                  </button>
                </div>
              </div>
            )}

            <div className="panel">
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">BORRADOR DE ESTIMACIÓN</div>
                  <h2>Resultado para revisión</h2>
                  <p>Revisa requisitos, horas, costos y auditoría antes de aprobar.</p>
                </div>
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  {draft.infra_profile && (
                    <span
                      className="pill"
                      style={{
                        backgroundColor: "#e6f4ff",
                        color: "#0958d9",
                        border: "1px solid #91caff",
                      }}
                    >
                      Infra: {draft.infra_profile.replace("_", " ").toUpperCase()}
                    </span>
                  )}
                  <span className="pill amber">
                    Complejidad: {draft.complexity.toUpperCase()}
                  </span>
                  <span
                    className={`pill ${draft.status === "ready_for_review" ? "green" : "amber"}`}
                  >
                    {draft.status === "ready_for_review"
                      ? "Listo para revisar"
                      : "Pendiente de aclaraciones"}
                  </span>
                </div>
              </div>

              <div
                className="summary"
                style={{
                  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                }}
              >
                <div>
                  <span>Esfuerzo total</span>
                  <strong>
                    {draft.total_expected_hours} <small>horas</small>
                  </strong>
                </div>
                <div>
                  <span>Duración estimada</span>
                  <strong>
                    {draft.plan ? draft.plan.duration_weeks : 0} <small>semanas</small>
                  </strong>
                </div>
                <div>
                  <span>Costo total</span>
                  <strong>
                    ${draft.plan ? draft.plan.total_cost.toLocaleString() : "0"}
                  </strong>
                </div>
                <div>
                  <span>P50 (Esperado)</span>
                  <strong style={{ color: "#167f73" }}>
                    {draft.plan?.p50_hours ?? draft.total_expected_hours} <small>h</small> · ${draft.plan?.p50_cost?.toLocaleString() ?? draft.plan?.total_cost?.toLocaleString() ?? "0"}
                  </strong>
                </div>
                <div>
                  <span>P80 (Precio Cerrado)</span>
                  <strong style={{ color: "#0958d9" }}>
                    {draft.plan?.p80_hours ?? draft.total_expected_hours} <small>h</small> · ${draft.plan?.p80_cost?.toLocaleString() ?? draft.plan?.total_cost?.toLocaleString() ?? "0"}
                  </strong>
                </div>
                <div>
                  <span>Requisitos</span>
                  <strong>{draft.requirements.length}</strong>
                </div>
                <div>
                  <span>Actividades WBS</span>
                  <strong>{draft.activities.length}</strong>
                </div>
              </div>

              {/* Auditor verdict */}
              {draft.audit && (
                <div
                  className={`alert ${draft.audit.approved ? "note" : "error"}`}
                  style={{
                    backgroundColor: draft.audit.approved ? "#e8f7f2" : "#fff2f0",
                    borderColor: draft.audit.approved ? "#9de2cc" : "#f5c2bc",
                  }}
                >
                  <strong>
                    {draft.audit.approved
                      ? `✓ Auditoría aprobada (${draft.audit.iterations} iteración/es)`
                      : `⚠ Auditoría con observaciones (${draft.audit.iterations} iteraciones)`}
                  </strong>
                  {draft.audit.findings.length > 0 ? (
                    <ul style={{ margin: "6px 0 0", paddingLeft: "18px" }}>
                      {draft.audit.findings.map((f, i) => (
                        <li key={i}>{f}</li>
                      ))}
                    </ul>
                  ) : (
                    <p style={{ margin: "4px 0 0" }}>
                      Todas las verificaciones deterministas (O≤M≤P, horas positivas, tarifas registradas, QA y desvío histórico) pasaron satisfactoriamente.
                    </p>
                  )}
                  {draft.audit.warnings && draft.audit.warnings.length > 0 && (
                    <div style={{ marginTop: "8px", paddingTop: "8px", borderTop: "1px dashed #d9d9d9" }}>
                      <strong style={{ color: "#d48806" }}>⚠ Observaciones y Ratios Paramétricos:</strong>
                      <ul style={{ margin: "4px 0 0", paddingLeft: "18px", color: "#874d00" }}>
                        {draft.audit.warnings.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Tecnologías recomendadas & Justificaciones */}
              {((draft.tech_justifications && draft.tech_justifications.length > 0) ||
                (draft.recommended_technologies && draft.recommended_technologies.length > 0)) && (
                <>
                  <h3>Tecnologías recomendadas por el Arquitecto</h3>
                  {draft.tech_justifications && draft.tech_justifications.length > 0 ? (
                    <div style={{ display: "grid", gap: "10px", marginBottom: "16px" }}>
                      {draft.tech_justifications.map((tj, i) => (
                        <div
                          key={i}
                          style={{
                            border: "1px solid #dce5e4",
                            borderRadius: "6px",
                            padding: "10px 14px",
                            backgroundColor: "#fafcfb",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "4px",
                            }}
                          >
                            <strong>
                              {tj.nombre}{" "}
                              <small style={{ color: "#666", fontWeight: "normal" }}>
                                ({tj.categoria || "tecnología"})
                              </small>
                            </strong>
                            <div style={{ display: "flex", gap: "6px" }}>
                              {tj.requisitos_ids.map((rid) => (
                                <span
                                  key={rid}
                                  className="pill green"
                                  style={{ fontSize: "11px", padding: "2px 6px" }}
                                >
                                  {rid}
                                </span>
                              ))}
                            </div>
                          </div>
                          <p style={{ margin: "2px 0 6px", fontSize: "13px", color: "#333" }}>
                            {tj.justificacion}
                          </p>
                          {tj.alternativas_descartadas && tj.alternativas_descartadas.length > 0 && (
                            <div style={{ fontSize: "12px", color: "#666" }}>
                              <span style={{ fontWeight: 600 }}>Alternativas descartadas: </span>
                              {tj.alternativas_descartadas.map((alt, idx) => (
                                <span key={idx}>
                                  <em>{alt.nombre}</em> ({alt.motivo})
                                  {idx < tj.alternativas_descartadas.length - 1 ? ", " : ""}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "8px",
                        marginBottom: "16px",
                      }}
                    >
                      {draft.recommended_technologies?.map((tech, i) => (
                        <span className="pill green" key={i}>
                          {tech}
                        </span>
                      ))}
                    </div>
                  )}
                </>
              )}

              {/* Requisitos */}
              {draft.requirements.length > 0 && (
                <>
                  <h3>Requisitos detectados</h3>
                  <div className="req-list">
                    {draft.requirements.map((r, i) => (
                      <div className="req" key={i}>
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "4px",
                            minWidth: "130px",
                          }}
                        >
                          <span className="req-type">
                            {r.id ? `${r.id} · ` : ""}
                            {r.kind === "functional"
                              ? "FUNCIONAL"
                              : r.kind === "non_functional"
                                ? "NO FUNCIONAL"
                                : "SUPUESTO"}
                          </span>
                          {r.origen && (
                            <span
                              className={`pill ${r.origen === "explicito" ? "green" : r.origen === "implicito" ? "blue" : "amber"}`}
                              style={{ fontSize: "10px", padding: "1px 6px", textAlign: "center" }}
                            >
                              {r.origen.toUpperCase()}
                            </span>
                          )}
                          {r.requiere_confirmacion && !r.confirmado && (
                            <span
                              className="pill amber"
                              style={{
                                fontSize: "10px",
                                padding: "1px 6px",
                                textAlign: "center",
                                backgroundColor: "#fff7e6",
                                color: "#d46b08",
                              }}
                            >
                              REVISAR
                            </span>
                          )}
                        </div>
                        <div>
                          <strong>{r.title}</strong>
                          <p>{r.detail}</p>
                          {r.cita_textual && (
                            <p style={{ margin: "4px 0 0", fontSize: "12px", fontStyle: "italic", color: "#666" }}>
                              «{r.cita_textual}»
                            </p>
                          )}
                        </div>
                        <span className="confidence">
                          {Math.round(r.confidence * 100)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {/* Desglose de actividades */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "24px", marginBottom: "8px", flexWrap: "wrap", gap: "8px" }}>
                <h3 style={{ margin: 0 }}>Desglose WBS y Ruta Crítica</h3>
                <button
                  className={isWbsDirty ? "primary" : "secondary"}
                  onClick={recalculate}
                  disabled={loading}
                  style={{
                    padding: "6px 14px",
                    fontSize: "12px",
                    fontWeight: 600,
                    borderColor: isWbsDirty ? "#167f73" : "#dce5e4",
                    backgroundColor: isWbsDirty ? "#167f73" : "#f8faf9",
                    color: isWbsDirty ? "#fff" : "#167f73",
                    cursor: "pointer",
                  }}
                  title="Recalcula ruta crítica, personal, costos, Monte Carlo P50/P80 y auditoría"
                >
                  🔄 Recalcular Plan y Auditoría {isWbsDirty && "(cambios pendientes)"}
                </button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Etapa / actividad</th>
                      <th>Perfil</th>
                      <th>Dependencias</th>
                      <th>PERT (O / M / P)</th>
                      <th>Horas esperadas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {draft.activities.map((a: Activity, i) => (
                      <tr key={i}>
                        <td><strong>{a.id}</strong></td>
                        <td>
                          <span className="phase">{a.phase}</span>
                          <strong>{a.name}</strong>
                          <small>{a.rationale}</small>
                        </td>
                        <td>{a.profile}</td>
                        <td>{a.depends_on.length > 0 ? a.depends_on.join(", ") : "Inicio"}</td>
                        <td>
                          <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                            <input
                              type="number"
                              min="0"
                              step="0.5"
                              value={a.optimistic_hours}
                              onChange={(e) => updateActivityHours(i, "optimistic_hours", parseFloat(e.target.value) || 0)}
                              style={{ width: "42px", padding: "2px 4px", fontSize: "11px", textAlign: "center", borderRadius: "4px", border: "1px solid #dce5e4" }}
                              title="Horas Optimistas (O)"
                            />
                            <span>/</span>
                            <input
                              type="number"
                              min="0"
                              step="0.5"
                              value={a.most_likely_hours}
                              onChange={(e) => updateActivityHours(i, "most_likely_hours", parseFloat(e.target.value) || 0)}
                              style={{ width: "42px", padding: "2px 4px", fontSize: "11px", textAlign: "center", fontWeight: "bold", borderRadius: "4px", border: "1px solid #dce5e4" }}
                              title="Horas Más Probables (M)"
                            />
                            <span>/</span>
                            <input
                              type="number"
                              min="0"
                              step="0.5"
                              value={a.pessimistic_hours}
                              onChange={(e) => updateActivityHours(i, "pessimistic_hours", parseFloat(e.target.value) || 0)}
                              style={{ width: "42px", padding: "2px 4px", fontSize: "11px", textAlign: "center", borderRadius: "4px", border: "1px solid #dce5e4" }}
                              title="Horas Pesimistas (P)"
                            />
                          </div>
                        </td>
                        <td className="hours">{a.expected_hours} h</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Personal y Costos por perfil */}
              {draft.plan && draft.plan.roles.length > 0 && (
                <>
                  <h3>Personal y Costos por Perfil</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Perfil</th>
                          <th>Horas totales</th>
                          <th>Personas necesarias</th>
                          <th>Tarifa por hora</th>
                          <th>Costo total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {draft.plan.roles.map((r, i) => (
                          <tr key={i}>
                            <td><strong>{r.profile}</strong></td>
                            <td className="hours">{r.hours} h</td>
                            <td>{r.people} pers.</td>
                            <td>${r.rate}/h</td>
                            <td className="hours">${r.cost.toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}

              {/* Riesgos */}
              {draft.risks.length > 0 && (
                <>
                  <h3>Riesgos y Mitigaciones</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Riesgo</th>
                          <th>Impacto</th>
                          <th>Estrategia de mitigación</th>
                        </tr>
                      </thead>
                      <tbody>
                        {draft.risks.map((rk, i) => (
                          <tr key={i}>
                            <td><strong>{rk.description}</strong></td>
                            <td>
                              <span
                                className={`pill ${
                                  rk.impact === "alto"
                                    ? "amber"
                                    : rk.impact === "medio"
                                      ? "amber"
                                      : "green"
                                }`}
                              >
                                {rk.impact.toUpperCase()}
                              </span>
                            </td>
                            <td>{rk.mitigation}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}

              <div className="review-footer">
                <div>
                  <strong>Revisión humana</strong>
                  <span>La estimación requiere aprobación del estimador para persistirse.</span>
                </div>
                <div className="actions">
                  <button
                    className="secondary"
                    onClick={() => review(false)}
                    disabled={loading}
                  >
                    Solicitar ajustes
                  </button>
                  <button
                    className="approve"
                    onClick={() => review(true)}
                    disabled={loading || draft.status !== "ready_for_review"}
                  >
                    Aprobar estimación ✓
                  </button>
                </div>
              </div>

              {reviewState && (
                <div className="review-result">
                  <div className="alert note">{reviewState}</div>
                  {reviewState.startsWith("Estimación aprobada") && (
                    <div style={{ display: "flex", gap: "10px", marginTop: "12px" }}>
                      <button
                        className="primary"
                        onClick={() => downloadReport("pdf")}
                        disabled={loading}
                      >
                        Descargar informe PDF ↓
                      </button>
                      <button
                        className="secondary"
                        onClick={() => downloadReport("xlsx")}
                        disabled={loading}
                        style={{ borderColor: "#167f73", color: "#167f73" }}
                      >
                        Descargar Excel (.xlsx) ↓
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>
        )}

        {/* Sección de Estimaciones Guardadas */}
        {savedEstimations.length > 0 && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <div className="eyebrow">PERSISTENCIA LOCAL (SQLITE)</div>
                <h2>Estimaciones Guardadas</h2>
                <p>Historial de estimaciones registradas. Haz clic en cualquiera para cargarla.</p>
              </div>
              <span className="pill green">{savedEstimations.length} guardadas</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Proyecto</th>
                    <th>Estado</th>
                    <th>Revisor</th>
                    <th>Fecha</th>
                    <th>Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {savedEstimations.map((est) => (
                    <tr key={est.id}>
                      <td><strong>#{est.id}</strong></td>
                      <td><strong>{est.project_name}</strong></td>
                      <td>
                        <span className={`pill ${est.status === "approved" ? "green" : "amber"}`}>
                          {est.status === "approved" ? "Aprobada" : "En ajustes"}
                        </span>
                      </td>
                      <td>{est.reviewer}</td>
                      <td><small>{new Date(est.created_at).toLocaleString()}</small></td>
                      <td>
                        <button
                          className="secondary"
                          style={{ padding: "4px 9px", fontSize: "11px" }}
                          onClick={() => loadSaved(est.id)}
                          disabled={loading}
                        >
                          Cargar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        <footer>
          La estimación de este prototipo es generada por un flujo de 6 agentes (Orquestador, Analista, Arquitecto, Estimador, Planificador, Auditor) y auditada de forma determinista con tarifas y datos históricos.
        </footer>
      </main>
    </div>
  );
}

export default App;
