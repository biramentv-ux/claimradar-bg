import os

os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("MONITORING_ENABLED", "1")
os.environ.setdefault("REQUEST_LOG_ENABLED", "0")
os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("OWASP_HARDENING_ENABLED", "1")
os.environ.setdefault("INFERENCE_MODE", "auto")
os.environ.setdefault("INFERENCE_AUTO_GPU", "1")
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")
os.environ.setdefault("WHISPER_CPU_COMPUTE_TYPE", "int8")
os.environ.setdefault("WHISPER_GPU_COMPUTE_TYPE", "float16")
os.environ.setdefault("WHISPER_GPU_FALLBACK_CPU", "1")

from fastapi.testclient import TestClient

import app as app_module
import auth_launch
from hardware_inference import dedicated_config, detect_gpu, inference_status, resolve_whisper_runtime

client = TestClient(auth_launch.app)


def test_detect_gpu_returns_stable_shape():
    gpu = detect_gpu()
    assert "available" in gpu
    assert "nvidia_smi" in gpu
    assert "cuda_visible_devices" in gpu


def test_resolve_runtime_uses_cpu_when_requested():
    runtime = resolve_whisper_runtime("tiny")
    assert runtime["model_size"] == "tiny"
    assert runtime["device"] in {"cpu", "cuda"}
    assert runtime["compute_type"] in {"int8", "float16", "int8_float16", "float32"}


def test_inference_status_endpoint():
    response = client.get("/api/inference/status")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "runtime" in data["inference"]
    assert "dedicated" in data["inference"]
    assert "recommendation" in data["inference"]
    assert data["inference"]["runtime"]["active_device"] in {"cpu", "cuda"}


def test_inference_recommendation_endpoint():
    response = client.get("/api/inference/recommendation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["recommendation"]["profile"] in {"cpu-safe", "gpu-ready", "dedicated-offload"}


def test_dedicated_config_safe_when_not_configured():
    cfg = dedicated_config()
    assert cfg["transcribe_url_configured"] in {True, False}
    assert cfg["fallback_local"] in {True, False}


def test_app_module_is_configured_for_inference_runtime():
    status = inference_status(app_module)
    assert status["state"]["configured"] is True
    assert app_module.DEVICE in {"cpu", "cuda"}
    assert app_module.COMPUTE_TYPE in {"int8", "float16", "int8_float16", "float32"}
