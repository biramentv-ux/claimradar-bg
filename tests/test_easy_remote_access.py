import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_easy_remote_routes_without_tunnel_binary(monkeypatch):
    monkeypatch.setenv("REMOTE_CLOUDFLARED_PATH", "/tmp/missing-cloudflared")
    monkeypatch.setenv("REMOTE_NGROK_PATH", "/tmp/missing-ngrok")
    import easy_remote_access
    remote = importlib.reload(easy_remote_access)
    app = FastAPI()
    remote.register_easy_remote_access_routes(app)
    client = TestClient(app)
    page = client.get("/remote-simple")
    assert page.status_code == 200
    assert "Лесен достъп извън Wi" in page.text
    status = client.get("/api/remote-simple/status")
    assert status.status_code == 200
    start = client.post("/api/remote-simple/start", json={"provider": "cloudflare"})
    assert start.status_code == 400
    assert start.json()["error"] in {"cloudflared_not_found", "ngrok_not_found"}
    assert "help" in start.json()


def test_easy_remote_url_parser_sets_mobile_url(monkeypatch):
    import easy_remote_access
    remote = importlib.reload(easy_remote_access)
    remote._append_log("Visit https://abc-test.trycloudflare.com for your tunnel")
    status = remote.remote_status()
    assert status["public_url"] == "https://abc-test.trycloudflare.com"
    assert status["mobile_url"] == "https://abc-test.trycloudflare.com/mobile"


def test_desktop_ui_links_easy_remote():
    import local_desktop_ui
    ui = importlib.reload(local_desktop_ui)
    assert "/remote-simple" in ui.PAGE
    assert "Easy Remote" in ui.PAGE
