import importlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_evidence_mode_switch_uses_local_first(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_SQLITE_PATH", str(tmp_path / "evidence.db"))
    import local_storage_sqlite
    import local_archive
    import local_evidence_router
    importlib.reload(local_storage_sqlite)
    archive = importlib.reload(local_archive)
    router = importlib.reload(local_evidence_router)
    archive.import_text_to_archive("Local source", "ClaimRadar локален evidence режим работи.")
    offline = router.evidence_search("локален evidence", mode="offline")
    assert offline["web"] == []
    assert offline["local"]
    hybrid = router.evidence_search("локален evidence", mode="hybrid")
    assert hybrid["results"][0]["kind"] == "local_archive"


def test_model_download_rejects_invalid_name():
    import local_model_downloads
    downloads = importlib.reload(local_model_downloads)
    assert downloads.start_model_download("bad model name")["error"] == "invalid_model_name"


def test_hardware_benchmark_routes():
    import local_hardware_benchmark
    bench = importlib.reload(local_hardware_benchmark)
    app = FastAPI()
    bench.register_hardware_benchmark_routes(app)
    result = TestClient(app).post("/api/local-ai/benchmark/run", json={"include_llm": False})
    assert result.status_code == 200
    assert result.json()["benchmark"]["recommended_profile"] in {"low", "balanced", "power"}


def test_desktop_ui_routes():
    import local_desktop_ui
    ui = importlib.reload(local_desktop_ui)
    app = FastAPI()
    ui.register_desktop_ui_routes(app)
    response = TestClient(app).get("/desktop")
    assert response.status_code == 200
    assert "Local Model Manager" in response.text
    assert "Evidence Mode" in response.text


def test_desktop_config_files_updated():
    main = Path("desktop/electron/main.js").read_text(encoding="utf-8")
    package = Path("desktop/electron/package.json").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/desktop-windows-build.yml").read_text(encoding="utf-8")
    assert "/desktop" in main
    assert "publisherName" in package
    assert "requestedExecutionLevel" in package
    assert "GITHUB_STEP_SUMMARY" in workflow
