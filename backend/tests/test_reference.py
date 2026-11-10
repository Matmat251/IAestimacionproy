import io
from pathlib import Path
import openpyxl
import pytest

from app.reference import (
    HISTORICOS_PATH,
    TARIFAS_PATH,
    import_file,
    load_history,
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
