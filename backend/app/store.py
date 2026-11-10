from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from .models import DraftResponse

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "app.db"


def _get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS estimations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                status TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                comment TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
    return conn


def save_estimation(draft: DraftResponse, reviewer: str, comment: str, status: str) -> int:
    conn = _get_connection()
    payload = draft.model_dump_json()
    created_at = datetime.now(timezone.utc).isoformat()
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO estimations (project_name, status, reviewer, comment, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (draft.project_name, status, reviewer, comment, payload, created_at),
        )
        return cursor.lastrowid or 0


def list_estimations() -> list[dict[str, Any]]:
    conn = _get_connection()
    cursor = conn.execute(
        "SELECT id, project_name, status, reviewer, comment, created_at FROM estimations ORDER BY id DESC"
    )
    return [dict(row) for row in cursor.fetchall()]


def get_estimation(est_id: int) -> dict[str, Any] | None:
    conn = _get_connection()
    cursor = conn.execute(
        "SELECT id, project_name, status, reviewer, comment, payload_json, created_at FROM estimations WHERE id = ?",
        (est_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    data = dict(row)
    try:
        data["draft"] = json.loads(data["payload_json"])
    except Exception:
        data["draft"] = None
    return data
