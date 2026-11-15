"""Test fixtures. Each test gets a fresh SQLite DB + in-memory object store."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("ZEST_API_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("ZEST_API_CORS_ORIGINS", "[]")
    # Empty endpoint -> the in-memory object store (no MinIO needed).
    monkeypatch.setenv("ZEST_API_STORAGE_ENDPOINT", "")

    from zest_data_api.config import reset_settings
    from zest_data_api.db import Base, get_engine, reset_engine
    from zest_data_api.storage import reset_store

    reset_settings()
    reset_engine()
    reset_store()
    import zest_data_api.models  # noqa: F401  (register tables)

    Base.metadata.create_all(get_engine())

    from zest_data_api.main import app

    with TestClient(app) as test_client:
        yield test_client

    reset_engine()
    reset_settings()
    reset_store()


@pytest.fixture
def dataset_files():
    """A list of (field, (filename, bytes, content_type)) tuples for TestClient uploads."""
    return [
        ("files", ("SIM-01_log.csv", b"run_id,time_h\nTST,0\nTST,1\n", "text/csv")),
        ("files", ("SIM-01_labels.csv", b"run_id,time_h\nTST,0\n", "text/csv")),
        ("files", ("SIM-01_truth.json", b'{"run_id":"TST","seed":42}', "application/json")),
    ]
