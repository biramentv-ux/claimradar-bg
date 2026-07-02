import os

os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("MONITORING_ENABLED", "1")
os.environ.setdefault("REQUEST_LOG_ENABLED", "0")
os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("MODERATOR_KEY", "test-moderator-key")
os.environ.setdefault("VIEWER_KEY", "test-viewer-key")
os.environ.setdefault("OWASP_HARDENING_ENABLED", "1")
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")

from fastapi.testclient import TestClient

import auth_launch

client = TestClient(auth_launch.app)


def test_owasp_status_endpoint_maps_api_top_10():
    response = client.get("/api/security/owasp/status")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    controls = data["owasp"]["controls"]
    assert "API1_BOLA" in controls
    assert "API4_Resource_Consumption" in controls
    assert "API8_Security_Misconfiguration" in controls


def test_security_headers_are_present_on_html_response():
    response = client.get("/product")
    assert response.status_code == 200
    assert response.headers["x-claimradar-owasp-hardening"] == "enabled"
    assert "content-security-policy" in response.headers
    assert "strict-transport-security" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-dns-prefetch-control"] == "off"


def test_admin_responses_are_not_cached():
    response = client.get("/admin?admin_key=test-admin-key")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"


def test_disallowed_methods_are_blocked():
    response = client.request("TRACE", "/health")
    assert response.status_code == 405
    assert response.json()["error"] == "method_not_allowed_by_security_policy"


def test_suspicious_query_is_blocked_and_redacted():
    response = client.get("/api/security/owasp/status?admin_key=secret&x=%2e%2e%2fetc%2fpasswd")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "suspicious_input_blocked"
    assert "secret" not in data.get("query", "")
    assert "admin_key=***" in data.get("query", "")


def test_api_write_rejects_plain_text_content_type():
    response = client.post("/api/jobs/check", data="plain text", headers={"content-type": "text/plain"})
    assert response.status_code == 415
    assert response.json()["error"] == "unsupported_api_content_type"
