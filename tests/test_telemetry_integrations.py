import os

os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("MONITORING_ENABLED", "1")
os.environ.setdefault("REQUEST_LOG_ENABLED", "0")
os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("OTEL_ENABLED", "1")
os.environ.setdefault("OTEL_CONSOLE_EXPORTER_ENABLED", "0")
os.environ.setdefault("SENTRY_ENABLED", "0")
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")

from fastapi import FastAPI
from fastapi.testclient import TestClient

import auth_launch
from telemetry_integrations import init_telemetry, telemetry_status, traced_span

client = TestClient(auth_launch.app)


def test_telemetry_status_endpoint_has_expected_sections():
    response = client.get("/api/telemetry/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    telemetry = payload["telemetry"]
    assert telemetry["initialized"] is True
    assert "otel" in telemetry
    assert "sentry" in telemetry
    assert telemetry["service"]["service.name"] == "claimradar-bg"


def test_test_span_endpoint_returns_span_shape():
    response = client.post("/api/telemetry/test-span")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "span_id" in payload["span"]


def test_init_telemetry_is_safe_for_test_app():
    app = FastAPI()
    status = init_telemetry(app)
    assert "sentry" in status
    assert status["otel"]["enabled"] in {True, False}


def test_manual_traced_span_context_manager_is_safe():
    with traced_span("unit.test", component="tests") as span:
        assert "span_id" in span
    status = telemetry_status()
    assert status["last_manual_span"]["name"] == "unit.test"
