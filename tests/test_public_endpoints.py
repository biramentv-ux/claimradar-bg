import os

os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("MONITORING_ENABLED", "1")
os.environ.setdefault("REQUEST_LOG_ENABLED", "0")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")

from fastapi.testclient import TestClient

import persistent_launch

client = TestClient(persistent_launch.app)


def test_database_status_endpoint():
    response = client.get("/db/status")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["storage"] in {"postgres", "jsonl_fallback"}


def test_database_schema_endpoint():
    response = client.get("/api/db/schema")
    assert response.status_code == 200
    assert "claimradar_checks" in response.text
    assert "claimradar_jobs" in response.text


def test_monitoring_endpoints():
    status = client.get("/monitoring/status")
    assert status.status_code == 200
    assert status.json()["ok"] is True

    metrics = client.get("/monitoring/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["ok"] is True
    assert "metrics" in metrics.json()


def test_admin_monitoring_logs_endpoint_requires_key():
    denied = client.get("/monitoring/logs")
    assert denied.status_code == 403

    allowed = client.get("/monitoring/logs?admin_key=test-admin-key")
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True


def test_public_legal_pages():
    for path in ["/about", "/methodology", "/privacy", "/terms", "/sources", "/contact"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "ClaimRadar BG" in response.text


def test_legal_methodology_markdown_endpoint():
    response = client.get("/legal-methodology.md")
    assert response.status_code == 200
    assert "ClaimRadar BG" in response.text


def test_manual_monitoring_event_requires_admin():
    denied = client.post("/api/monitoring/event", json={"kind": "test", "message": "denied"})
    assert denied.status_code == 403

    allowed = client.post(
        "/api/monitoring/event",
        json={"admin_key": "test-admin-key", "kind": "test", "level": "info", "message": "ok"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True
