import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


def load_mobile(monkeypatch):
    monkeypatch.setenv("MOBILE_REMOTE_ENABLED", "1")
    monkeypatch.setenv("MOBILE_REMOTE_REQUIRE_PIN", "1")
    monkeypatch.setenv("MOBILE_REMOTE_PIN", "123456")
    import mobile_remote_control
    return importlib.reload(mobile_remote_control)


def test_mobile_status_and_pairing_page(monkeypatch):
    mobile = load_mobile(monkeypatch)
    app = FastAPI()
    mobile.register_mobile_remote_routes(app)
    client = TestClient(app)
    status = client.get("/api/mobile/status")
    assert status.status_code == 200
    assert status.json()["mobile"]["require_pin"] is True
    pair = client.get("/mobile/pair")
    assert pair.status_code == 200
    assert "123456" in pair.text
    assert "/mobile" in pair.text


def test_mobile_pairing_rejects_bad_pin_and_accepts_good_pin(monkeypatch):
    mobile = load_mobile(monkeypatch)
    app = FastAPI()
    mobile.register_mobile_remote_routes(app)
    client = TestClient(app)
    assert client.post("/api/mobile/pair", json={"pin": "000000"}).status_code == 403
    ok = client.post("/api/mobile/pair", json={"pin": "123456"})
    assert ok.status_code == 200
    assert ok.json()["ok"] is True
    assert ok.json()["token"]


def test_mobile_analyze_requires_pairing(monkeypatch):
    mobile = load_mobile(monkeypatch)
    app = FastAPI()
    mobile.register_mobile_remote_routes(app)
    client = TestClient(app)
    response = client.post("/api/mobile/analyze", json={"text": "test"})
    assert response.status_code == 401
    assert response.json()["error"] == "mobile_pairing_required"


def test_local_desktop_launch_supports_lan_binding():
    source = open("local_desktop_launch.py", encoding="utf-8").read()
    assert "MOBILE_REMOTE_BIND_LAN" in source
    assert "0.0.0.0" in source


def test_desktop_ui_links_phone_remote():
    source = open("local_desktop_ui.py", encoding="utf-8").read()
    assert "/mobile/pair" in source
    assert "Pair Phone Remote" in source
