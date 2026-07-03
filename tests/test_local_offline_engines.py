import importlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_local_llm_json_parser_and_invalid_model_fallback(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_MODEL", "bad model with spaces")
    import local_llm_engine
    llm = importlib.reload(local_llm_engine)
    assert llm._safe_model() == "llama3.2:3b"
    assert llm._try_json('prefix {"claims": []} suffix') == {"claims": []}


def test_local_llm_routes_without_ollama(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    import local_llm_engine
    llm = importlib.reload(local_llm_engine)
    app = FastAPI()
    llm.register_local_llm_routes(app)
    client = TestClient(app)
    status = client.get("/api/local-ai/llm/status")
    assert status.status_code == 200
    assert status.json()["ok"] is True
    assert status.json()["llm"]["available"] is False


def test_local_sqlite_store_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_SQLITE_PATH", str(tmp_path / "claimradar.db"))
    import local_storage_sqlite
    sqlite_mod = importlib.reload(local_storage_sqlite)
    store = sqlite_mod.LocalSQLiteStore(tmp_path / "claimradar.db")
    saved = store.save_check("Claim text", {"verdict": "unsupported"}, title="Check 1")
    assert saved["id"].startswith("check_")
    assert store.get_check(saved["id"])["result"]["verdict"] == "unsupported"
    source = store.save_source("Source", "Пробен локален архив за проверка", metadata={"kind": "test"})
    store.save_chunk(source["id"], 0, "Пробен локален архив за проверка")
    assert store.search_chunks("локален архив")


def test_local_archive_import_and_search(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_SQLITE_PATH", str(tmp_path / "archive.db"))
    import local_storage_sqlite
    import local_archive
    importlib.reload(local_storage_sqlite)
    archive = importlib.reload(local_archive)
    imported = archive.import_text_to_archive("Документ", "Това е локален документ за енергетика и факти.")
    assert imported["chunks_created"] >= 1
    found = archive.search_archive("енергетика факти")
    assert found["count"] >= 1


def test_local_transcription_config_and_missing_dependency(monkeypatch):
    import local_transcription
    tr = importlib.reload(local_transcription)
    cfg = tr.transcription_config()
    assert "model" in cfg
    result = tr.local_transcribe_file("/tmp/not-existing.wav", engine="faster-whisper")
    assert result["ok"] is False or "engine" in result


def test_desktop_windows_build_workflow_exists():
    workflow = Path(".github/workflows/desktop-windows-build.yml").read_text(encoding="utf-8")
    assert "windows-latest" in workflow
    assert "build_desktop_backend.py" in workflow
    assert "npm run dist" in workflow
    assert "actions/upload-artifact" in workflow
