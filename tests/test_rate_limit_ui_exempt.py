from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from security_jobs import SecurityAndRateLimitMiddleware, rate_limiter, rate_limit_status


def make_client():
    app = FastAPI()
    app.add_middleware(SecurityAndRateLimitMiddleware)

    @app.get("/")
    def home():
        return JSONResponse({"ok": True, "page": "home"})

    @app.get("/api_info")
    def api_info():
        return JSONResponse({"ok": True, "api_info": {}})

    @app.post("/api/test-rate-limit")
    def api_test():
        return JSONResponse({"ok": True})

    return TestClient(app)


def setup_function():
    rate_limiter.reset(all_keys=True)
    rate_limiter.exempt_total = 0


def test_root_get_does_not_create_temporary_ban():
    client = make_client()
    for _ in range(150):
        response = client.get("/")
        assert response.status_code == 200
    status = rate_limit_status()
    assert status["exempt_total"] >= 150
    assert status["banned_count"] == 0


def test_gradio_api_info_get_does_not_create_temporary_ban():
    client = make_client()
    for _ in range(150):
        response = client.get("/api_info")
        assert response.status_code == 200
    assert rate_limit_status()["banned_count"] == 0


def test_api_post_still_gets_limited():
    client = make_client()
    saw_429 = False
    for _ in range(80):
        response = client.post("/api/test-rate-limit")
        if response.status_code == 429:
            saw_429 = True
            payload = response.json()
            assert payload["ok"] is False
            assert payload["scope"] == "api"
            break
    assert saw_429 is True
