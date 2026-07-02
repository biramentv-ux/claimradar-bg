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
from telemetry_integrations import init_telemetry, scrub_sensitive, sentry_before_send, telemetry_status, traced_span

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


def test_sentry_status_endpoint_has_expected_sections():
    response = client.get("/api/sentry/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    sentry = payload["sentry"]
    assert "enabled" in sentry
    assert "scrubber_enabled" in sentry
    assert sentry["send_default_pii"] in {True, False}


def test_sentry_test_event_requires_admin_and_returns_shape():
    denied = client.post("/api/sentry/test-event", json={"message": "hello"})
    assert denied.status_code == 403
    allowed = client.post("/api/sentry/test-event", json={"admin_key": "test-admin-key", "message": "hello"})
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["ok"] is True
    assert "event_id" in payload
    assert "sentry" in payload


def test_sentry_test_error_requires_admin_and_returns_shape():
    denied = client.post("/api/sentry/test-error", json={"message": "boom"})
    assert denied.status_code == 403
    allowed = client.post("/api/sentry/test-error", json={"admin_key": "test-admin-key", "message": "controlled test"})
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["ok"] is True
    assert payload["captured"] is True
    assert "event_id" in payload


def test_sentry_scrubber_filters_sensitive_values():
    data = {"admin_key": "redacted", "nested": {"Authorization": "redacted", "safe": "ok"}, "items": [{"api_key": "redacted"}]}
    scrubbed = scrub_sensitive(data)
    assert scrubbed["admin_key"] == "[Filtered]"
    assert scrubbed["nested"]["Authorization"] == "[Filtered]"
    assert scrubbed["nested"]["safe"] == "ok"
    assert scrubbed["items"][0]["api_key"] == "[Filtered]"


def test_sentry_before_send_scrubs_and_tags_event():
    event = {"extra": {"token": "redacted", "safe": "ok"}, "request": {"headers": {"cookie": "redacted"}}}
    result = sentry_before_send(event, {})
    assert result["extra"]["token"] == "[Filtered]"
    assert result["extra"]["safe"] == "ok"
    assert result["request"]["headers"]["cookie"] == "[Filtered]"
    assert result["tags"]["service.name"] == "claimradar-bg"


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
