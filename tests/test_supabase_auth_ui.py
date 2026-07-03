import importlib
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("MONITORING_ENABLED", "1")
os.environ.setdefault("REQUEST_LOG_ENABLED", "0")
os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")


def load_auth_ui(monkeypatch):
    monkeypatch.setenv("SUPABASE_AUTH_UI_ENABLED", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://rsknkjmzjpewhebwfffz.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    import supabase_auth_ui
    return importlib.reload(supabase_auth_ui)


def make_client(module):
    app = FastAPI()
    module.register_supabase_auth_ui_routes(app)
    return TestClient(app)


def test_supabase_auth_config_exposes_only_public_client_config(monkeypatch):
    module = load_auth_ui(monkeypatch)
    cfg = module.supabase_auth_config()
    assert cfg["enabled"] is True
    assert cfg["configured"] is True
    assert cfg["supabase_url"] == "https://rsknkjmzjpewhebwfffz.supabase.co"
    assert cfg["supabase_publishable_key"] == "sb_publishable_test"
    assert "secret" not in " ".join(cfg.keys()).lower()


def test_supabase_auth_routes_are_registered(monkeypatch):
    module = load_auth_ui(monkeypatch)
    client = make_client(module)
    for path, marker in [
        ("/signup", 'data-supabase-auth-page="signup"'),
        ("/login", 'data-supabase-auth-page="login"'),
        ("/logout", 'data-supabase-auth-page="logout"'),
        ("/account", 'data-supabase-auth-page="account"'),
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert marker in response.text
        assert "@supabase/supabase-js" in response.text


def test_signup_login_account_pages_include_expected_supabase_calls(monkeypatch):
    module = load_auth_ui(monkeypatch)
    client = make_client(module)
    assert "signUp" in client.get("/signup").text
    assert "emailRedirectTo" in client.get("/signup").text
    assert "signInWithPassword" in client.get("/login").text
    account = client.get("/account").text
    assert "getSession" in account
    assert "claimradar_profiles" in account
    assert "access_token" in account
    assert "signOut" in client.get("/logout").text


def test_api_auth_supabase_config_endpoint(monkeypatch):
    module = load_auth_ui(monkeypatch)
    client = make_client(module)
    response = client.get("/api/auth/supabase/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["supabase_publishable_key"] == "sb_publishable_test"


def test_auth_ui_can_be_disabled(monkeypatch):
    monkeypatch.setenv("SUPABASE_AUTH_UI_ENABLED", "0")
    monkeypatch.setenv("SUPABASE_URL", "https://rsknkjmzjpewhebwfffz.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    import supabase_auth_ui
    module = importlib.reload(supabase_auth_ui)
    response = make_client(module).get("/signup")
    assert response.status_code == 404
    assert response.json()["error"] == "supabase_auth_ui_disabled"
