import os

os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("MONITORING_ENABLED", "1")
os.environ.setdefault("REQUEST_LOG_ENABLED", "0")
os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("MODERATOR_KEY", "test-moderator-key")
os.environ.setdefault("VIEWER_KEY", "test-viewer-key")
os.environ.setdefault("CUSTOM_DOMAIN", "claimradar.dyrakarmy.eu")
os.environ.setdefault("ROOT_DOMAIN", "dyrakarmy.eu")
os.environ.setdefault("PUBLIC_BASE_URL", "https://claimradar.dyrakarmy.eu")
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")

from fastapi.testclient import TestClient

import auth_launch

client = TestClient(auth_launch.app)


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


def test_custom_domain_endpoints():
    page = client.get("/custom-domain")
    assert page.status_code == 200
    assert "claimradar.dyrakarmy.eu" in page.text

    status = client.get("/custom-domain/status")
    assert status.status_code == 200
    data = status.json()
    assert data["ok"] is True
    assert data["custom_domain"]["custom_domain"] == "claimradar.dyrakarmy.eu"
    assert data["custom_domain"]["recommended_dns_record"]["value"] == "hf.space"

    api_status = client.get("/api/custom-domain/status")
    assert api_status.status_code == 200
    assert api_status.json()["ok"] is True


def test_auth_status_and_whoami_endpoints():
    status = client.get("/auth/status")
    assert status.status_code == 200
    assert status.json()["ok"] is True
    assert "admin" in status.json()["auth"]["roles"]

    anonymous = client.get("/api/auth/whoami")
    assert anonymous.status_code == 200
    assert anonymous.json()["auth"]["role"] == "anonymous"

    viewer = client.get("/api/auth/whoami", headers={"x-api-key": "test-viewer-key"})
    assert viewer.status_code == 200
    assert viewer.json()["auth"]["role"] == "viewer"

    admin = client.get("/api/auth/whoami", headers={"authorization": "Bearer test-admin-key"})
    assert admin.status_code == 200
    assert admin.json()["auth"]["role"] == "admin"


def test_auth_roles_and_check_endpoint():
    roles = client.get("/api/auth/roles")
    assert roles.status_code == 200
    assert roles.json()["roles"]["owner"] > roles.json()["roles"]["admin"]

    denied = client.post("/api/auth/check", json={"token": "test-viewer-key", "minimum_role": "admin"})
    assert denied.status_code == 200
    assert denied.json()["allowed"] is False

    allowed = client.post("/api/auth/check", json={"token": "test-admin-key", "minimum_role": "admin"})
    assert allowed.status_code == 200
    assert allowed.json()["allowed"] is True


def test_monitoring_endpoints():
    status = client.get("/monitoring/status")
    assert status.status_code == 200
    assert status.json()["ok"] is True

    metrics = client.get("/monitoring/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["ok"] is True
    assert "metrics" in metrics.json()


def test_rate_limit_status_and_reset_endpoints():
    status = client.get("/rate-limit/status")
    assert status.status_code == 200
    data = status.json()
    assert data["ok"] is True
    assert "rate_limit" in data
    assert "limits" in data["rate_limit"]

    api_status = client.get("/api/rate-limit/status")
    assert api_status.status_code == 200
    assert api_status.json()["ok"] is True

    denied = client.post("/api/rate-limit/reset", json={"all": True})
    assert denied.status_code == 403

    allowed = client.post("/api/rate-limit/reset", json={"admin_key": "test-admin-key", "all": True})
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True


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


def test_jobs_dashboard_and_stats():
    dashboard = client.get("/jobs")
    assert dashboard.status_code == 200
    assert "Jobs Dashboard" in dashboard.text

    stats = client.get("/api/jobs/stats")
    assert stats.status_code == 200
    assert stats.json()["ok"] is True
    assert "stats" in stats.json()


def test_create_get_cancel_and_retry_job():
    created = client.post("/api/jobs/check", json={"text": "Инфлацията през 2024 година е 10 процента."})
    assert created.status_code == 200
    data = created.json()
    assert data["ok"] is True
    job_id = data["job_id"]

    fetched = client.get(f"/api/jobs/{job_id}")
    assert fetched.status_code == 200
    assert fetched.json()["job"]["id"] == job_id

    denied_cancel = client.post(f"/api/jobs/{job_id}/cancel", json={})
    assert denied_cancel.status_code == 403

    cancel = client.post(f"/api/jobs/{job_id}/cancel", json={"admin_key": "test-admin-key"})
    assert cancel.status_code == 200
    assert cancel.json()["ok"] is True

    retry = client.post(f"/api/jobs/{job_id}/retry", json={"admin_key": "test-admin-key"})
    assert retry.status_code in {200, 400}
    assert retry.json()["ok"] in {True, False}


def test_jobs_cleanup_requires_admin():
    denied = client.post("/api/jobs/cleanup", json={"keep": 100})
    assert denied.status_code == 403

    allowed = client.post("/api/jobs/cleanup", json={"admin_key": "test-admin-key", "keep": 100})
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True
