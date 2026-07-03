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

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import auth_launch
from owasp_hardening import OWASPHardeningMiddleware, owasp_status, register_owasp_routes

client = TestClient(auth_launch.app)


def make_minimal_client():
    app = FastAPI()
    app.add_middleware(OWASPHardeningMiddleware)
    register_owasp_routes(app)

    @app.get("/")
    def home():
        return JSONResponse({"ok": True})

    @app.post("/api/write")
    def api_write():
        return JSONResponse({"ok": True})

    @app.get("/admin/private")
    def admin_private():
        return JSONResponse({"ok": True})

    @app.get("/cookie")
    def cookie_route():
        response = Response("ok", media_type="text/plain")
        response.set_cookie("claimradar_session", "test")
        return response

    return TestClient(app)


def test_owasp_status_endpoint_maps_api_top_10():
    response = client.get("/api/security/owasp/status")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    controls = data["owasp"]["controls"]
    assert "API1_BOLA" in controls
    assert "API4_Resource_Consumption" in controls
    assert "API8_Security_Misconfiguration" in controls
    assert data["owasp"]["cookie_hardening_enabled"] in {True, False}
    assert data["owasp"]["security_txt_enabled"] in {True, False}


def test_security_headers_are_present_on_html_response():
    response = client.get("/product")
    assert response.status_code == 200
    assert response.headers["x-claimradar-owasp-hardening"] == "enabled"
    assert "content-security-policy" in response.headers
    assert "strict-transport-security" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-xss-protection"] == "0"
    assert response.headers["x-permitted-cross-domain-policies"] == "none"


def test_minimal_app_headers_allow_huggingface_frame_ancestors():
    response = make_minimal_client().get("/")
    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "object-src 'none'" in csp
    assert "frame-ancestors" in csp
    assert "huggingface.co" in csp
    assert response.headers["origin-agent-cluster"] == "?1"


def test_disallowed_trace_method_is_blocked():
    response = make_minimal_client().request("TRACE", "/")
    assert response.status_code == 405
    assert response.json()["error"] == "method_not_allowed_by_security_policy"


def test_suspicious_crlf_and_path_traversal_are_blocked():
    local_client = make_minimal_client()
    crlf = local_client.get("/?q=%0d%0aX-Injected:yes")
    assert crlf.status_code == 400
    assert crlf.json()["error"] == "suspicious_input_blocked"
    traversal = local_client.get("/api/security/owasp/status?file=..%2f..%2fetc%2fpasswd")
    assert traversal.status_code == 400
    assert traversal.json()["error"] == "suspicious_input_blocked"


def test_api_write_content_type_guard():
    response = make_minimal_client().post("/api/write", content="not json", headers={"content-type": "text/plain"})
    assert response.status_code == 415
    assert response.json()["error"] == "unsupported_api_content_type"


def test_sensitive_admin_paths_use_no_store_cache_headers():
    response = make_minimal_client().get("/admin/private")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"


def test_cookie_hardening_adds_safe_cookie_flags():
    response = make_minimal_client().get("/cookie")
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_security_txt_and_headers_endpoints():
    local_client = make_minimal_client()
    security_txt = local_client.get("/.well-known/security.txt")
    assert security_txt.status_code == 200
    assert "Contact:" in security_txt.text
    headers = local_client.get("/api/security/owasp/headers")
    assert headers.status_code == 200
    assert headers.json()["ok"] is True
    assert "Content-Security-Policy" in headers.json()["headers"]


def test_owasp_status_reports_header_inventory():
    status = owasp_status()
    assert "headers" in status
    assert "X-XSS-Protection" in status["headers"]
    assert "Content-Security-Policy" in status["headers"]
