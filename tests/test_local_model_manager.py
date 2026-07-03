import importlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def load_manager(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_MANAGER_CONFIG_PATH", str(tmp_path / "model_manager.json"))
    import local_model_manager
    import local_model_manager_static
    return importlib.reload(local_model_manager), importlib.reload(local_model_manager_static)


def test_model_config_saves_profile_and_models(monkeypatch, tmp_path):
    manager, _ = load_manager(monkeypatch, tmp_path)
    config = manager.save_model_config({
        "active_profile": "power",
        "ollama_models": {"low": "llama3.2:3b", "power": "qwen2.5:14b"},
        "whisper_models": {"low": "base", "balanced": "small", "power": "large-v3"},
        "transcription_engine": "whisperx",
        "whisper_device": "cuda",
        "whisper_compute_type": "float16",
        "whisperx_enabled": True,
        "offline_mode": True,
        "online_evidence_mode": True,
    })
    assert config["active_profile"] == "power"
    assert config["ollama_models"]["low"] == "llama3.2:3b"
    assert config["ollama_models"]["power"] == "qwen2.5:14b"
    assert config["whisper_models"]["power"] == "large-v3"
    assert config["transcription_engine"] == "whisperx"


def test_model_manager_routes(monkeypatch, tmp_path):
    manager, static = load_manager(monkeypatch, tmp_path)
    app = FastAPI()
    static.register_local_model_manager_static_routes(app)
    manager.register_local_model_manager_routes(app)
    client = TestClient(app)
    assert client.get("/local-ai/models").status_code == 200
    assert "Local Model Manager" in client.get("/local-ai/models").text
    assert "refreshAll" in client.get("/local-ai/model-manager.js").text
    status = client.get("/api/local-ai/model-manager/status")
    assert status.status_code == 200
    assert status.json()["ok"] is True
    saved = client.post("/api/local-ai/model-manager/config", json={"active_profile": "low", "whisper_models": {"power": "large-v3"}})
    assert saved.status_code == 200
    assert saved.json()["config"]["active_profile"] == "low"


def test_whisper_cache_scanner_reports_configured_models(monkeypatch, tmp_path):
    manager, _ = load_manager(monkeypatch, tmp_path)
    cache_root = tmp_path / "hf-cache" / "models--Systran--faster-whisper-large-v3"
    cache_root.mkdir(parents=True)
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(tmp_path / "hf-cache"))
    manager = importlib.reload(manager)
    result = manager.scan_whisper_cache()
    assert "large-v3" in result["matches"]
    assert any("large-v3" in path for path in result["matches"]["large-v3"])


def test_ollama_download_rejects_invalid_model_name(monkeypatch, tmp_path):
    manager, _ = load_manager(monkeypatch, tmp_path)
    result = manager.ollama_download_model("invalid model")
    assert result["ok"] is False
    assert result["error"] == "invalid_model_name"


def test_desktop_doc_mentions_model_manager():
    doc = Path("docs/DESKTOP_LOCAL_AI_PLATFORM_BG.md").read_text(encoding="utf-8")
    assert "Model Manager" in doc
    assert "Ollama status" in doc
    assert "WhisperX" in doc
