import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from app.core.config import get_settings


def test_runtime_status_reads_actual_schema_without_mutation(client: TestClient, database_engine: Engine) -> None:
    path = Path(database_engine.url.database)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    response = client.get('/api/v1/runtime')
    assert response.status_code == 200
    assert response.json()['app_version'] == get_settings().app_version
    assert response.json()['database_schema'] == '0005_add_deadlines_recurrence_reminders'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
