import io
from pathlib import Path
import openpyxl
import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.reference import (
    HISTORICOS_PATH,
    TARIFAS_PATH,
    import_file,
    load_history,
    load_knowledge_summary,
    load_knowledge_text,
    load_rates,
    rates_by_profile,
    similar_history,
)


def test_load_rates_and_history():
    rates = load_rates()
    assert len(rates) >= 5
    by_profile = rates_by_profile()
    assert "Desarrollador" in by_profile
    assert by_profile["Desarrollador"]["tarifa_hora"] == 30.0

    history = load_history()
    assert len(history) >= 5
    assert any(h["complejidad"] == "media" for h in history)


def test_similar_history():
    matches = similar_history(tech="React FastAPI", complexity="alta")
    assert len(matches) > 0


def test_import_file_csv_valid_and_invalid(tmp_path, monkeypatch):
    test_tarifas_csv = tmp_path / "tarifas.csv"
    test_tarifas_csv.write_text("perfil,tarifa_hora,capacidad_semanal\nTester,20,40\n", encoding="utf-8")
    monkeypatch.setattr("app.reference.TARIFAS_PATH", test_tarifas_csv)
    monkeypatch.setattr("app.reference.DATA_DIR", tmp_path)

    # 1. Invalid columns -> ValueError
    bad_csv = b"perfil,tarifa_hora\nDev,30\n"
    with pytest.raises(ValueError, match="Faltan columnas requeridas"):
        import_file("tarifas", "tarifas.csv", bad_csv)
    # File content remains untouched
    assert "Tester" in test_tarifas_csv.read_text(encoding="utf-8")

    # 2. Invalid number -> ValueError
    bad_num_csv = b"perfil,tarifa_hora,capacidad_semanal\nDev,-10,40\n"
    with pytest.raises(ValueError, match="mayores a 0"):
        import_file("tarifas", "tarifas.csv", bad_num_csv)
    assert "Tester" in test_tarifas_csv.read_text(encoding="utf-8")

    # 3. Valid CSV -> Success
    valid_csv = b"perfil,tarifa_hora,capacidad_semanal\nScrum Master,35,40\nQA Lead,28,40\n"
    rows = import_file("tarifas", "tarifas.csv", valid_csv)
    assert rows == 2
    assert "Scrum Master" in test_tarifas_csv.read_text(encoding="utf-8")


def test_import_file_xlsx_valid(tmp_path, monkeypatch):
    test_hist_csv = tmp_path / "historicos.csv"
    test_hist_csv.write_text("nombre,tecnologias,complejidad,fase,horas_reales\nP1,Python,baja,Dev,50\n", encoding="utf-8")
    monkeypatch.setattr("app.reference.HISTORICOS_PATH", test_hist_csv)
    monkeypatch.setattr("app.reference.DATA_DIR", tmp_path)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["nombre", "tecnologias", "complejidad", "fase", "horas_reales"])
    ws.append(["Proyecto Alpha", "Vue Python", "alta", "Desarrollo", 150])
    ws.append(["Proyecto Beta", "React Go", "media", "Diseno", 80])
    buffer = io.BytesIO()
    wb.save(buffer)
    xlsx_bytes = buffer.getvalue()

    rows = import_file("historicos", "nuevos_historicos.xlsx", xlsx_bytes)
    assert rows == 2
    content = test_hist_csv.read_text(encoding="utf-8")
    assert "Proyecto Alpha" in content
    assert "Proyecto Beta" in content


def test_load_knowledge_text_and_api_endpoint():
    # 1. load_knowledge_text includes CSV contents
    text = load_knowledge_text()
    assert "benchmarks_actividades.csv" in text
    assert "distribucion_fases.csv" in text
    assert "factores_ajuste.csv" in text

    # 2. load_knowledge_summary
    summary = load_knowledge_summary()
    assert summary["benchmarks_count"] >= 20
    assert summary["factors_count"] >= 5
    assert summary["historical_projects_count"] >= 18
    assert len(summary["phases_distribution"]) >= 5
    assert len(summary["benchmarks_actividades"]) >= 20

    # 3. GET /api/reference/knowledge endpoint
    client = TestClient(app)
    resp = client.get("/api/reference/knowledge")
    assert resp.status_code == 200
    data = resp.json()
    assert data["benchmarks_count"] == summary["benchmarks_count"]
    assert data["historical_projects_count"] == summary["historical_projects_count"]
    assert "phases_distribution" in data
    assert "benchmarks_actividades" in data


def test_retrieve_similar_rag_csv_and_sqlite(tmp_path, monkeypatch):
    from app.models import DraftResponse
    from app.reference import retrieve_similar_rag
    from app.store import save_estimation

    test_db = tmp_path / "test_store_rag.db"
    monkeypatch.setattr("app.store.DB_PATH", test_db)

    # 1. Query contra CSV
    matches = retrieve_similar_rag(query_text="Sistema de portal para clientes facturas", tech="React PostgreSQL", top_k=3)
    assert len(matches) > 0
    assert matches[0]["similarity"] > 0.0
    assert matches[0]["source"] == "historico_csv"
    assert "nombre" in matches[0]

    # 2. Agregar estimación aprobada en SQLite
    mock_draft = DraftResponse(
        project_name="Portal Especial B2B Clientes",
        status="ready_for_review",
        requirements=[],
        missing_fields=[],
        questions=[],
        activities=[],
        total_expected_hours=175.0,
        notes=[],
        complexity="alta",
        risks=[],
        recommended_technologies=["React", "PostgreSQL", "Tailwind"],
    )
    save_estimation(mock_draft, reviewer="Revisor Test", comment="Ok", status="approved")

    # 3. Query que debe encontrar la estimación aprobada de SQLite
    matches_with_sqlite = retrieve_similar_rag(query_text="Portal Especial B2B Clientes", tech="React Tailwind", top_k=5)
    assert any(m["source"] == "estimacion_aprobada" for m in matches_with_sqlite)
    approved_match = next(m for m in matches_with_sqlite if m["source"] == "estimacion_aprobada")
    assert approved_match["nombre"] == "Portal Especial B2B Clientes"
    assert approved_match["horas_reales"] == 175.0


