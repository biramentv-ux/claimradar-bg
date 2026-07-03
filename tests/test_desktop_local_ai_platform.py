import json
import os
from pathlib import Path


def test_local_ai_runtime_profiles(monkeypatch):
    monkeypatch.setenv("LOCAL_AI_PROFILE", "auto")
    monkeypatch.setenv("LOCAL_AI_RAM_GB", "8")
    import importlib
    import local_ai_runtime
    runtime = importlib.reload(local_ai_runtime)
    low = runtime.local_ai_status()
    assert low["profile"] == "low"
    assert low["transcription"]["compute_type"] == "int8"

    monkeypatch.setenv("LOCAL_AI_RAM_GB", "16")
    runtime = importlib.reload(local_ai_runtime)
    balanced = runtime.local_ai_status()
    assert balanced["profile"] in {"balanced", "low"}
    assert "offline" in balanced["modes"]
    assert "online_evidence" in balanced["modes"]


def test_local_ai_power_profile_contract(monkeypatch):
    monkeypatch.setenv("LOCAL_AI_PROFILE", "power")
    import importlib
    import local_ai_runtime
    runtime = importlib.reload(local_ai_runtime)
    status = runtime.local_ai_status()
    assert status["profile"] == "power"
    assert status["transcription"]["model"] == "large-v3"
    assert status["transcription"]["whisperx"]["enabled"] in {True, False}
    assert status["ollama"]["base_url"].startswith("http://127.0.0.1")


def test_electron_desktop_shell_files_exist_and_are_safe():
    package = json.loads(Path("desktop/electron/package.json").read_text(encoding="utf-8"))
    main = Path("desktop/electron/main.js").read_text(encoding="utf-8")
    preload = Path("desktop/electron/preload.js").read_text(encoding="utf-8")
    assert package["main"] == "main.js"
    assert "electron-builder" in package["devDependencies"]
    assert "nsis" in json.dumps(package["build"])
    assert "portable" in json.dumps(package["build"])
    assert "nodeIntegration: false" in main
    assert "contextIsolation: true" in main
    assert "sandbox: true" in main
    assert "contextBridge.exposeInMainWorld" in preload


def test_desktop_build_scripts_exist_and_reference_pyinstaller():
    backend = Path("scripts/build_desktop_backend.py").read_text(encoding="utf-8")
    portable = Path("scripts/build_windows_portable.py").read_text(encoding="utf-8")
    launch = Path("local_desktop_launch.py").read_text(encoding="utf-8")
    assert "PyInstaller" in backend
    assert "local_desktop_launch.py" in backend
    assert "npm" in portable
    assert "LOCAL_AI_MODE" in launch
    assert "OLLAMA_BASE_URL" in launch


def test_desktop_documentation_covers_required_phases():
    doc = Path("docs/DESKTOP_LOCAL_AI_PLATFORM_BG.md").read_text(encoding="utf-8")
    for phrase in [
        "Electron desktop shell",
        "локален Python/FastAPI backend sidecar",
        "Ollama",
        "faster-whisper",
        "WhisperX",
        "large-v3",
        "Offline Mode",
        "Online Evidence Mode",
        "Фаза 1",
        "Фаза 2",
        "Фаза 3",
        "Фаза 4",
        "Фаза 5",
    ]:
        assert phrase in doc
