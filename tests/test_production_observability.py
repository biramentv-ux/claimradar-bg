import os

os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("MONITORING_ENABLED", "1")
os.environ.setdefault("REQUEST_LOG_ENABLED", "0")
os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("OPENAI_INPUT_COST_PER_1M", "1.0")
os.environ.setdefault("OPENAI_OUTPUT_COST_PER_1M", "2.0")
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")

from fastapi.testclient import TestClient

import auth_launch
from production_observability import ai_cost_summary, prometheus_text, record_ai_usage

client = TestClient(auth_launch.app)


def test_observability_summary_endpoint_has_core_sections():
    response = client.get("/api/observability/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    obs = data["observability"]
    for key in ["uptime", "latency", "errors", "requests", "providers", "cost", "slo", "links"]:
        assert key in obs
    assert "search" in obs["providers"]
    assert "ai" in obs["providers"]


def test_observability_dashboard_renders():
    response = client.get("/observability")
    assert response.status_code == 200
    assert "Production Observability" in response.text
    assert "Search provider health" in response.text
    assert "AI provider health" in response.text


def test_prometheus_metrics_endpoint_uses_text_format():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    text = response.text
    assert "# HELP claimradar_up" in text
    assert "# TYPE claimradar_requests_total counter" in text
    assert "claimradar_latency_p95_ms" in text


def test_provider_and_cost_endpoints():
    providers = client.get("/api/observability/providers")
    assert providers.status_code == 200
    assert providers.json()["ok"] is True
    assert "search" in providers.json()["providers"]

    costs = client.get("/api/observability/costs")
    assert costs.status_code == 200
    assert costs.json()["ok"] is True
    assert "total_tokens" in costs.json()["cost"]


def test_ai_usage_requires_admin_and_records_cost():
    denied = client.post("/api/observability/ai-usage", json={"provider": "openai", "model": "test", "input_tokens": 100, "output_tokens": 50})
    assert denied.status_code == 403

    allowed = client.post(
        "/api/observability/ai-usage",
        json={"admin_key": "test-admin-key", "provider": "openai", "model": "test", "input_tokens": 100, "output_tokens": 50},
    )
    assert allowed.status_code == 200
    data = allowed.json()
    assert data["ok"] is True
    assert data["usage"]["total_tokens"] == 150
    assert data["usage"]["cost_usd"] >= 0


def test_prometheus_text_builder_contains_provider_metrics():
    usage = record_ai_usage("openai", "unit-test", 10, 20, cost_usd=0.001)
    assert usage["total_tokens"] == 30
    summary = {"uptime": {"seconds": 10}, "requests": {"total": 2}, "errors": {"total": 0, "error_rate": 0}, "latency": {"avg_ms": 1, "p95_ms": 1}, "cost": ai_cost_summary(), "jobs": {"total": 0, "status_counts": {}}, "providers": {"search": {"duckduckgo": {"configured": True}}, "ai": {"openai": {"configured": True}}}}
    text = prometheus_text(summary)
    assert "claimradar_ai_tokens_total" in text
    assert 'claimradar_search_provider_configured{provider="duckduckgo"} 1.0' in text
