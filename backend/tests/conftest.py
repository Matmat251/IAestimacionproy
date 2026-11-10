import sys
from pathlib import Path
import pytest

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


@pytest.fixture(autouse=True)
def force_demo_mode(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "")
