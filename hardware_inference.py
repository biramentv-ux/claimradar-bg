from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel

INFERENCE_MODE = os.getenv("INFERENCE_MODE", "auto").strip().lower()  # auto | local | dedicated
INFERENCE_AUTO_GPU = os.getenv("INFERENCE_AUTO_GPU", "1").lower() not in {"0", "false", "no"}
WHISPER_DEVICE_REQUESTED = os.getenv("WHISPER_DEVICE", "auto").strip().lower()
WHISPER_CPU_COMPUTE_TYPE = os.getenv("WHISPER_CPU_COMPUTE_TYPE", os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
WHISPER_GPU_COMPUTE_TYPE = os.getenv("WHISPER_GPU_COMPUTE_TYPE", "float16")
WHISPER_GPU_FALLBACK_CPU = os.getenv("WHISPER_GPU_FALLBACK_CPU", "1").lower() not in {"0", "false", "no"}
DEDICATED_INFERENCE_ENABLED = os.getenv("DEDICATED_INFERENCE_ENABLED", "auto").strip().lower()  # 1 | 0 | auto
DEDICATED_TRANSCRIBE_URL = os.getenv("DEDICATED_TRANSCRIBE_URL", "").strip()
DEDICATED_INFERENCE_TOKEN = os.getenv("DEDICATED_INFERENCE_TOKEN", "").strip()
DEDICATED_TRANSCRIBE_TIMEOUT = int(os.getenv("DEDICATED_TRANSCRIBE_TIMEOUT", "180"))
DEDICATED_FALLBACK_LOCAL = os.getenv("DEDICATED_FALLBACK_LOCAL", "1").lower() not in {"0", "false", "no"}

_runtime_state: Dict[str, Any] = {
    "configured": False,
    "model_loaded": False,
    "model_load_error": "",
    "model_load_seconds": None,
    "last_transcribe_engine": "",
    "last_transcribe_error": "",
    "fallback_used": False,
}


def _env_bool(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value not in {"", "0", "false", "no", "none"}


def _run_cmd(cmd: List[str], timeout: int = 3) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout)
        return out.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def detect_gpu() -> Dict[str, Any]:
    cuda_visible = os.getenv("CUDA_VISIBLE_DEVICES", "")
    nvidia_visible = os.getenv("NVIDIA_VISIBLE_DEVICES", "")
    proc_gpu = Path("/proc/driver/nvidia/gpus").exists()
    nvidia_smi = _run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], timeout=3)
    torch_cuda = False
    torch_device_name = ""
    try:
        import torch  # type: ignore

        torch_cuda = bool(torch.cuda.is_available())
        if torch_cuda:
            torch_device_name = str(torch.cuda.get_device_name(torch.cuda.current_device()))
    except Exception:
        pass
    available = bool(torch_cuda or nvidia_smi or proc_gpu or _env_bool("HF_SPACE_GPU") or (cuda_visible and cuda_visible != "-1") or (nvidia_visible and nvidia_visible.lower() not in {"", "none", "void"}))
    return {
        "available": available,
        "torch_cuda_available": torch_cuda,
        "torch_device_name": torch_device_name,
        "nvidia_smi": nvidia_smi[:1000],
        "cuda_visible_devices": cuda_visible,
        "nvidia_visible_devices": nvidia_visible,
        "proc_nvidia_gpu": proc_gpu,
    }


def resolve_whisper_runtime(model_size: str) -> Dict[str, Any]:
    gpu = detect_gpu()
    requested = WHISPER_DEVICE_REQUESTED
    if requested in {"gpu", "cuda"}:
        device = "cuda"
    elif requested == "cpu":
        device = "cpu"
    elif INFERENCE_AUTO_GPU and gpu["available"]:
        device = "cuda"
    else:
        device = "cpu"
    compute_type = WHISPER_GPU_COMPUTE_TYPE if device == "cuda" else WHISPER_CPU_COMPUTE_TYPE
    return {
        "model_size": model_size,
        "device": device,
        "compute_type": compute_type,
        "requested_device": requested,
        "gpu": gpu,
        "gpu_fallback_cpu": WHISPER_GPU_FALLBACK_CPU,
    }


def dedicated_enabled() -> bool:
    if INFERENCE_MODE == "local":
        return False
    if not DEDICATED_TRANSCRIBE_URL:
        return False
    if DEDICATED_INFERENCE_ENABLED in {"1", "true", "yes", "on"}:
        return True
    if DEDICATED_INFERENCE_ENABLED == "auto" and INFERENCE_MODE in {"auto", "dedicated"}:
        return True
    return False


def dedicated_config() -> Dict[str, Any]:
    return {
        "enabled": dedicated_enabled(),
        "mode": INFERENCE_MODE,
        "transcribe_url_configured": bool(DEDICATED_TRANSCRIBE_URL),
        "token_configured": bool(DEDICATED_INFERENCE_TOKEN),
        "timeout_seconds": DEDICATED_TRANSCRIBE_TIMEOUT,
        "fallback_local": DEDICATED_FALLBACK_LOCAL,
    }


def inference_status(app_module: Any | None = None) -> Dict[str, Any]:
    model_size = getattr(app_module, "MODEL_SIZE", os.getenv("WHISPER_MODEL_SIZE", "base")) if app_module is not None else os.getenv("WHISPER_MODEL_SIZE", "base")
    runtime = resolve_whisper_runtime(str(model_size))
    if app_module is not None:
        runtime["active_device"] = getattr(app_module, "DEVICE", runtime["device"])
        runtime["active_compute_type"] = getattr(app_module, "COMPUTE_TYPE", runtime["compute_type"])
    return {
        "runtime": runtime,
        "dedicated": dedicated_config(),
        "state": dict(_runtime_state),
        "space": {
            "space_id": os.getenv("SPACE_ID", ""),
            "space_host": os.getenv("SPACE_HOST", ""),
            "space_hardware": os.getenv("SPACE_HARDWARE", ""),
            "hf_space_url": os.getenv("HF_SPACE_URL", ""),
        },
        "recommendation": recommendation(runtime),
        "env": {
            "INFERENCE_MODE": INFERENCE_MODE,
            "INFERENCE_AUTO_GPU": INFERENCE_AUTO_GPU,
            "WHISPER_DEVICE": WHISPER_DEVICE_REQUESTED,
            "WHISPER_CPU_COMPUTE_TYPE": WHISPER_CPU_COMPUTE_TYPE,
            "WHISPER_GPU_COMPUTE_TYPE": WHISPER_GPU_COMPUTE_TYPE,
        },
    }


def recommendation(runtime: Dict[str, Any]) -> Dict[str, Any]:
    gpu = runtime.get("gpu", {})
    if runtime.get("device") == "cuda" and gpu.get("available"):
        return {"profile": "gpu-ready", "message": "Local GPU inference is selected. Use float16 for speed or int8_float16 for lower VRAM."}
    if dedicated_enabled():
        return {"profile": "dedicated-offload", "message": "Dedicated transcription endpoint is configured and local fallback is available."}
    return {"profile": "cpu-safe", "message": "CPU-safe mode is active. For faster transcription, upgrade the Space hardware to GPU or configure DEDICATED_TRANSCRIBE_URL."}


def _segment_to_srt(segments: List[Dict[str, Any]]) -> str:
    def ts(seconds: float) -> str:
        ms = int((seconds - int(seconds)) * 1000)
        total = int(seconds)
        return f"{total//3600:02}:{(total%3600)//60:02}:{total%60:02},{ms:03}"

    blocks = []
    for i, seg in enumerate(segments, 1):
        blocks.append(f"{i}\n{ts(float(seg.get('start', 0)))} --> {ts(float(seg.get('end', 0)))}\n{str(seg.get('text', '')).strip()}\n")
    return "\n".join(blocks)


def _write_srt(text: str) -> str:
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".srt", mode="w", encoding="utf-8")
    out.write(text)
    out.close()
    return out.name


def dedicated_transcribe(path: str, language: str) -> Dict[str, Any]:
    headers = {}
    if DEDICATED_INFERENCE_TOKEN:
        headers["Authorization"] = f"Bearer {DEDICATED_INFERENCE_TOKEN}"
    with open(path, "rb") as fh:
        files = {"file": (Path(path).name, fh, "application/octet-stream")}
        data = {"language": language}
        response = requests.post(DEDICATED_TRANSCRIBE_URL, headers=headers, files=files, data=data, timeout=DEDICATED_TRANSCRIBE_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    transcript = str(payload.get("transcript") or payload.get("text") or "").strip()
    segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
    srt_text = str(payload.get("srt") or "")
    if not srt_text and segments:
        srt_text = _segment_to_srt(segments)
    return {"transcript": transcript, "segments": segments, "srt": srt_text, "raw": payload}


def configure_app_module(app_module: Any) -> Dict[str, Any]:
    model_size = os.getenv("WHISPER_MODEL_SIZE", getattr(app_module, "MODEL_SIZE", "base"))
    runtime = resolve_whisper_runtime(model_size)
    app_module.MODEL_SIZE = runtime["model_size"]
    app_module.DEVICE = runtime["device"]
    app_module.COMPUTE_TYPE = runtime["compute_type"]
    app_module._model = None
    original_transcribe_file = getattr(app_module, "transcribe_file", None)

    def get_model():
        if getattr(app_module, "_model", None) is None:
            started = time.time()
            try:
                app_module._model = WhisperModel(app_module.MODEL_SIZE, device=app_module.DEVICE, compute_type=app_module.COMPUTE_TYPE)
                _runtime_state.update({"configured": True, "model_loaded": True, "model_load_error": "", "model_load_seconds": round(time.time() - started, 3), "fallback_used": False})
            except Exception as exc:
                _runtime_state.update({"model_loaded": False, "model_load_error": str(exc)[:500]})
                if app_module.DEVICE == "cuda" and WHISPER_GPU_FALLBACK_CPU:
                    app_module.DEVICE = "cpu"
                    app_module.COMPUTE_TYPE = WHISPER_CPU_COMPUTE_TYPE
                    app_module._model = WhisperModel(app_module.MODEL_SIZE, device="cpu", compute_type=app_module.COMPUTE_TYPE)
                    _runtime_state.update({"configured": True, "model_loaded": True, "model_load_seconds": round(time.time() - started, 3), "fallback_used": True})
                else:
                    raise
        return app_module._model

    app_module.get_model = get_model

    if callable(original_transcribe_file):
        def transcribe_file(file_path):
            if not file_path:
                return "", None, "Качи аудио или видео файл."
            path = getattr(file_path, "name", file_path)
            if dedicated_enabled():
                try:
                    result = dedicated_transcribe(str(path), getattr(app_module, "LANGUAGE", "bg"))
                    transcript = result["transcript"]
                    srt_path = _write_srt(result.get("srt") or "") if result.get("srt") else None
                    _runtime_state.update({"last_transcribe_engine": "dedicated", "last_transcribe_error": ""})
                    return transcript, srt_path, f"Готово. Дължина: {len(transcript)} символа. Engine: dedicated inference"
                except Exception as exc:
                    _runtime_state.update({"last_transcribe_engine": "dedicated_failed", "last_transcribe_error": str(exc)[:500]})
                    if not DEDICATED_FALLBACK_LOCAL:
                        return "", None, f"Dedicated inference не успя и fallback е изключен: {str(exc)[:180]}"
            out = original_transcribe_file(file_path)
            _runtime_state.update({"last_transcribe_engine": f"local:{app_module.DEVICE}/{app_module.COMPUTE_TYPE}"})
            return out

        app_module.transcribe_file = transcribe_file

    _runtime_state["configured"] = True
    return inference_status(app_module)


def register_inference_routes(app: FastAPI, app_module: Any) -> None:
    @app.get("/inference/status")
    def public_inference_status():
        return JSONResponse({"ok": True, "inference": inference_status(app_module)})

    @app.get("/api/inference/status")
    def api_inference_status():
        return JSONResponse({"ok": True, "inference": inference_status(app_module)})

    @app.get("/api/inference/recommendation")
    def api_inference_recommendation():
        status = inference_status(app_module)
        return JSONResponse({"ok": True, "recommendation": status["recommendation"], "runtime": status["runtime"], "dedicated": status["dedicated"]})
