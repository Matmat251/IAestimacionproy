from io import BytesIO
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .agent import create_draft
from .config import settings
from .models import DraftRequest, DraftResponse, ReviewRequest
from .reference import import_file, load_history, load_rates
from .store import get_estimation, list_estimations, save_estimation

app = FastAPI(title="Prototipo estimador de proyectos TI", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm_configured": bool(settings.groq_api_key),
        "provider": "groq",
        "model": settings.groq_model,
        "groq_configured": bool(settings.groq_api_key),
    }


@app.post("/api/estimate/draft", response_model=DraftResponse)
def draft_estimate(request: DraftRequest):
    return create_draft(request)


@app.post("/api/estimate/review")
def review_estimate(request: ReviewRequest):
    status = "approved" if request.approved else "changes_requested"
    est_id = save_estimation(
        draft=request.draft,
        reviewer=request.reviewer,
        comment=request.comment,
        status=status,
    )
    return {
        "id": est_id,
        "status": status,
        "reviewer": request.reviewer,
        "comment": request.comment,
        "draft": request.draft,
    }


@app.get("/api/estimations")
def get_estimations():
    return list_estimations()


@app.get("/api/estimations/{est_id}")
def get_single_estimation(est_id: int):
    est = get_estimation(est_id)
    if not est:
        raise HTTPException(status_code=404, detail="Estimación no encontrada")
    return est


@app.get("/api/reference/{kind}")
def get_reference_data(kind: Literal["tarifas", "historicos"]):
    if kind == "tarifas":
        return load_rates()
    elif kind == "historicos":
        return load_history()
    raise HTTPException(status_code=400, detail="Tipo inválido. Use 'tarifas' o 'historicos'.")


@app.post("/api/reference/{kind}")
async def upload_reference_data(kind: Literal["tarifas", "historicos"], file: UploadFile = File(...)):
    filename = file.filename or ""
    if not (filename.lower().endswith(".csv") or filename.lower().endswith(".xlsx")):
        raise HTTPException(status_code=400, detail="Solo se admiten archivos con extensión .csv o .xlsx")

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El archivo excede el tamaño máximo permitido de 2 MB")

    try:
        count = import_file(kind, filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    items = load_rates() if kind == "tarifas" else load_history()
    return {"kind": kind, "rows": count, "items": items}


def _build_pdf(draft: DraftResponse, reviewer: str) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    small_style = ParagraphStyle(
        "SmallCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
    )

    story = [
        Paragraph("Informe de Estimación de Esfuerzo TI", styles["Title"]),
        Spacer(1, 4 * mm),
        Paragraph(f"<b>Proyecto:</b> {draft.project_name}", styles["Heading2"]),
        Paragraph(f"<b>Revisor:</b> {reviewer} · <b>Estado:</b> Aprobado", styles["BodyText"]),
        Spacer(1, 4 * mm),
    ]

    # Summary table
    weeks = draft.plan.duration_weeks if draft.plan else 0.0
    cost = draft.plan.total_cost if draft.plan else 0.0
    summary_data = [
        ["Complejidad", "Esfuerzo Total", "Duración Estimada", "Costo Total"],
        [draft.complexity.capitalize(), f"{draft.total_expected_hours:g} h", f"{weeks:g} semanas", f"${cost:,.2f}"],
    ]
    t_summary = Table(summary_data, colWidths=[45 * mm] * 4)
    t_summary.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#167f73")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dce5e4")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f3f8f7")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    story.extend([t_summary, Spacer(1, 5 * mm)])

    if draft.recommended_technologies:
        story.append(
            Paragraph(
                f"<b>Tecnologías recomendadas:</b> {', '.join(draft.recommended_technologies)}",
                styles["BodyText"],
            )
        )
        story.append(Spacer(1, 4 * mm))

    # WBS Table
    story.append(Paragraph("Desglose de Actividades (WBS)", styles["Heading2"]))
    story.append(Spacer(1, 2 * mm))
    wbs_rows = [["ID", "Fase", "Actividad", "Perfil", "O / M / P", "Horas"]]
    for act in draft.activities:
        wbs_rows.append([
            act.id,
            Paragraph(act.phase, small_style),
            Paragraph(f"<b>{act.name}</b><br/><font color='#666'>{act.rationale}</font>", small_style),
            Paragraph(act.profile, small_style),
            f"{act.optimistic_hours:g}/{act.most_likely_hours:g}/{act.pessimistic_hours:g}",
            f"{act.expected_hours:g} h",
        ])
    t_wbs = Table(wbs_rows, repeatRows=1, colWidths=[12 * mm, 22 * mm, 70 * mm, 38 * mm, 22 * mm, 16 * mm])
    t_wbs.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#167f73")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce5e4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8faf9")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.extend([t_wbs, Spacer(1, 5 * mm)])

    # Roles and Cost Table
    if draft.plan and draft.plan.roles:
        story.append(Paragraph("Personal y Costos por Perfil", styles["Heading2"]))
        story.append(Spacer(1, 2 * mm))
        role_rows = [["Perfil", "Horas", "Personas", "Tarifa/h", "Costo"]]
        for r in draft.plan.roles:
            role_rows.append([r.profile, f"{r.hours:g} h", str(r.people), f"${r.rate:g}", f"${r.cost:,.2f}"])
        t_roles = Table(role_rows, repeatRows=1, colWidths=[65 * mm, 25 * mm, 25 * mm, 25 * mm, 40 * mm])
        t_roles.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#167f73")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce5e4")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8faf9")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.extend([t_roles, Spacer(1, 5 * mm)])

    # Risks Table
    if draft.risks:
        story.append(Paragraph("Riesgos Identificados", styles["Heading2"]))
        story.append(Spacer(1, 2 * mm))
        risk_rows = [["Riesgo", "Impacto", "Mitigación"]]
        for rk in draft.risks:
            risk_rows.append([
                Paragraph(rk.description, small_style),
                rk.impact.capitalize(),
                Paragraph(rk.mitigation, small_style),
            ])
        t_risks = Table(risk_rows, repeatRows=1, colWidths=[75 * mm, 25 * mm, 80 * mm])
        t_risks.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#167f73")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce5e4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8faf9")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.extend([t_risks, Spacer(1, 5 * mm)])

    # Audit & Notes
    story.append(Paragraph("Auditoría y Supuestos", styles["Heading2"]))
    if draft.audit:
        status_text = "Aprobada sin hallazgos" if draft.audit.approved else "Aprobada con observaciones"
        story.append(
            Paragraph(
                f"<b>Auditor determinista:</b> {status_text} ({draft.audit.iterations} iteraciones)",
                styles["BodyText"],
            )
        )
        for finding in draft.audit.findings:
            story.append(Paragraph(f"• [Observación] {finding}", styles["BodyText"]))

    for note in draft.notes:
        story.append(Paragraph(f"• {note}", styles["BodyText"]))

    doc.build(story)
    buffer.seek(0)
    return buffer


def _build_xlsx(draft: DraftResponse, reviewer: str) -> BytesIO:
    wb = openpyxl.Workbook()
    header_fill = PatternFill(start_color="167F73", end_color="167F73", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    # Sheet 1: Resumen
    ws_resumen = wb.active
    ws_resumen.title = "Resumen"
    resumen_data = [
        ["Proyecto", draft.project_name],
        ["Revisor", reviewer],
        ["Estado", "Aprobado"],
        ["Complejidad", draft.complexity.capitalize()],
        ["Tecnologías recomendadas", ", ".join(draft.recommended_technologies)],
        ["Esfuerzo total (horas)", draft.total_expected_hours],
        ["Duración estimada (semanas)", draft.plan.duration_weeks if draft.plan else 0.0],
        ["Costo total estimado", draft.plan.total_cost if draft.plan else 0.0],
        ["Auditoría aprobada", "Sí" if draft.audit and draft.audit.approved else "No"],
        ["Iteraciones del auditor", draft.audit.iterations if draft.audit else 0],
    ]
    for row_idx, (label, val) in enumerate(resumen_data, start=1):
        c1 = ws_resumen.cell(row=row_idx, column=1, value=label)
        c2 = ws_resumen.cell(row=row_idx, column=2, value=val)
        c1.font = Font(bold=True)
    ws_resumen.column_dimensions["A"].width = 28
    ws_resumen.column_dimensions["B"].width = 40

    # Sheet 2: WBS
    ws_wbs = wb.create_sheet(title="WBS")
    wbs_headers = ["ID", "Fase", "Nombre", "Perfil", "Dependencias", "Optimista", "Más probable", "Pesimista", "Horas esperadas", "Rationale"]
    ws_wbs.append(wbs_headers)
    for col_num in range(1, len(wbs_headers) + 1):
        cell = ws_wbs.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
    for a in draft.activities:
        ws_wbs.append([
            a.id,
            a.phase,
            a.name,
            a.profile,
            ", ".join(a.depends_on),
            a.optimistic_hours,
            a.most_likely_hours,
            a.pessimistic_hours,
            a.expected_hours,
            a.rationale,
        ])
    for col_letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]:
        ws_wbs.column_dimensions[col_letter].width = 20
    ws_wbs.column_dimensions["C"].width = 30
    ws_wbs.column_dimensions["J"].width = 45

    # Sheet 3: Personal y Costos
    ws_roles = wb.create_sheet(title="Personal y Costos")
    roles_headers = ["Perfil", "Horas", "Personas", "Tarifa por hora", "Costo"]
    ws_roles.append(roles_headers)
    for col_num in range(1, len(roles_headers) + 1):
        cell = ws_roles.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
    if draft.plan:
        for r in draft.plan.roles:
            ws_roles.append([r.profile, r.hours, r.people, r.rate, r.cost])
    for col_letter in ["A", "B", "C", "D", "E"]:
        ws_roles.column_dimensions[col_letter].width = 22

    # Sheet 4: Riesgos y Auditoria
    ws_risks = wb.create_sheet(title="Riesgos y Auditoria")
    risk_headers = ["Descripción del Riesgo", "Impacto", "Mitigación"]
    ws_risks.append(risk_headers)
    for col_num in range(1, len(risk_headers) + 1):
        cell = ws_risks.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
    for rk in draft.risks:
        ws_risks.append([rk.description, rk.impact.capitalize(), rk.mitigation])

    next_row = len(draft.risks) + 3
    ws_risks.cell(row=next_row, column=1, value="Hallazgos de Auditoría").font = Font(bold=True, size=12)
    next_row += 1
    if draft.audit and draft.audit.findings:
        for f in draft.audit.findings:
            ws_risks.cell(row=next_row, column=1, value=f)
            next_row += 1
    else:
        ws_risks.cell(row=next_row, column=1, value="Sin hallazgos reportados por el auditor.")

    ws_risks.column_dimensions["A"].width = 45
    ws_risks.column_dimensions["B"].width = 15
    ws_risks.column_dimensions["C"].width = 45

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


@app.post("/api/estimate/report")
def generate_report(request: ReviewRequest, format: Literal["pdf", "xlsx"] = Query("pdf")):
    if not request.approved or request.draft.status != "ready_for_review":
        raise HTTPException(
            status_code=400,
            detail="Solo se puede generar el informe de una estimación lista y aprobada.",
        )

    import re
    import unicodedata

    ascii_name = unicodedata.normalize("NFKD", request.draft.project_name).encode("ascii", "ignore").decode("ascii")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", ascii_name).strip("_") or "estimacion"

    if format == "xlsx":
        buffer = _build_xlsx(request.draft, request.reviewer)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={safe_name}.xlsx"},
        )

    buffer = _build_pdf(request.draft, request.reviewer)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.pdf"},
    )
