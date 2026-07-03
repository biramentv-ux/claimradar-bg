from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse

LOCAL_AI_ENABLED = os.getenv("LOCAL_AI_ENABLED", "1").lower() not in {"0", "false", "no"}
LOCAL_AI_MODE = os.getenv("LOCAL_AI_MODE", "offline").strip().lower()  # offline | online_evidence | hybrid
LOCAL_AI_PROFILE = os.getenv("LOCAL_AI_PROFILE", "auto").strip().lower()  # auto | low | balanced | power
LOCAL_AI_DATA_DIR = Path(os.getenv("LOCAL_AI_DATA_DIR", "data/local_ai")).expanduser()
LOCAL_AI_ARCHIVE_DIR = Path(os.getenv("LOCAL_AI_ARCHIVE_DIR", str(LOCAL_AI_DATA_DIR / "archive"))).expanduser()
LOCAL_AI_MODELS_DIR = Path(os.getenv("LOCAL_AI_MODELS_DIR", str(LOCAL_AI_DATA_DIR / "models"))).expanduser()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL_LOW = os.getenv("OLLAMA_MODEL_LOW", "llama3.2:3b")
OLLAMA_MODEL_BALANCED = os.getenv("OLLAMA_MODEL_BALANCED", "llama3.1:8b")
OLLAMA_MODEL_POWER = os.getenv("OLLAMA_MODEL_POWER", "llama3.1:8b")
TRANSCRIPTION_ENGINE = os.getenv("TRANSCRIPTION_ENGINE", "faster-whisper").strip().lower()  # faster-whisper | whisperx
WHISPER_MODEL_LOW = os.getenv("WHISPER_MODEL_LOW", "base")
WHISPER_MODEL_BALANCED = os.getenv("WHISPER_MODEL_BALANCED", "small")
WHISPER_MODEL_POWER = os.getenv("WHISPER_MODEL_POWER", "large-v3")
WHISPERX_ENABLED = os.getenv("WHISPERX_ENABLED", "1").lower() not in {"0", "false", "no"}
ONLINE_EVIDENCE_PROVIDERS = [p.strip() for p in os.getenv("ONLINE_EVIDENCE_PROVIDERS", "brave,tavily,serpapi").split(",") if p.strip()]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def total_ram_gb() -> float:
    override = os.getenv("LOCAL_AI_RAM_GB", "").strip()
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round((pages * page_size) / (1024 ** 3), 2)
        except Exception:
            return 0.0
    return 0.0


def nvidia_gpu_summary() -> Dict[str, Any]:
    if os.getenv("LOCAL_AI_FORCE_CUDA", "").lower() in {"1", "true", "yes"}:
        return {"available": True, "name": "forced-cuda", "vram_mb": _safe_int(os.getenv("LOCAL_AI_VRAM_MB", "8192"), 8192)}
    if not shutil.which("nvidia-smi"):
        return {"available": False, "name": "", "vram_mb": 0}
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        line = (proc.stdout or "").splitlines()[0]
        name, vram = [part.strip() for part in line.split(",", 1)]
        return {"available": True, "name": name, "vram_mb": _safe_int(vram, 0)}
    except Exception:
        return {"available": False, "name": "", "vram_mb": 0}


def detect_hardware() -> Dict[str, Any]:
    gpu = nvidia_gpu_summary()
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count() or 1,
        "ram_gb": total_ram_gb(),
        "gpu": gpu,
        "disk_free_gb": round(shutil.disk_usage(Path.cwd()).free / (1024 ** 3), 2),
    }


def choose_profile(hw: Dict[str, Any] | None = None) -> str:
    requested = LOCAL_AI_PROFILE
    if requested in {"low", "balanced", "power"}:
        return requested
    hw = hw or detect_hardware()
    ram = float(hw.get("ram_gb") or 0)
    cpu = int(hw.get("cpu_count") or 1)
    gpu = hw.get("gpu") or {}
    vram = int(gpu.get("vram_mb") or 0)
    if gpu.get("available") and vram >= 10000 and ram >= 24:
        return "power"
    if ram >= 14 and cpu >= 6:
        return "balanced"
    return "low"


def profile_config(profile: str) -> Dict[str, Any]:
    if profile == "power":
        return {
            "profile": "power",
            "ollama_model": OLLAMA_MODEL_POWER,
            "whisper_model": WHISPER_MODEL_POWER,
            "whisper_device": "cuda",
            "whisper_compute_type": "float16",
            "whisperx": {"enabled": WHISPERX_ENABLED, "batch_size": 16, "diarization": True},
            "limits": {"max_media_mb": 2048, "batch_jobs": 4, "realtime": True},
        }
    if profile == "balanced":
        return {
            "profile": "balanced",
            "ollama_model": OLLAMA_MODEL_BALANCED,
            "whisper_model": WHISPER_MODEL_BALANCED,
            "whisper_device": "auto",
            "whisper_compute_type": "int8_float16",
            "whisperx": {"enabled": WHISPERX_ENABLED, "batch_size": 8, "diarization": False},
            "limits": {"max_media_mb": 512, "batch_jobs": 2, "realtime": True},
        }
    return {
        "profile": "low",
        "ollama_model": OLLAMA_MODEL_LOW,
        "whisper_model": WHISPER_MODEL_LOW,
        "whisper_device": "cpu",
        "whisper_compute_type": "int8",
        "whisperx": {"enabled": False, "batch_size": 1, "diarization": False},
        "limits": {"max_media_mb": 120, "batch_jobs": 1, "realtime": False},
    }


def runtime_modes() -> Dict[str, Any]:
    return {
        "offline": {
            "claim_detection": "local_ollama",
            "verdict": "local_ollama",
            "transcription": TRANSCRIPTION_ENGINE,
            "evidence": "local_archive",
            "database": "sqlite_or_local_files",
            "internet_required": False,
        },
        "online_evidence": {
            "claim_detection": "local_ollama",
            "verdict": "local_ollama_with_online_evidence",
            "transcription": TRANSCRIPTION_ENGINE,
            "evidence": ONLINE_EVIDENCE_PROVIDERS,
            "database": "sqlite_or_local_files",
            "internet_required": True,
        },
        "hybrid": {
            "claim_detection": "local_first",
            "verdict": "local_first_cloud_optional",
            "transcription": TRANSCRIPTION_ENGINE,
            "evidence": ["local_archive", *ONLINE_EVIDENCE_PROVIDERS],
            "database": "sqlite_local_plus_optional_sync",
            "internet_required": "only_for_online_evidence_or_sync",
        },
    }


def local_ai_status() -> Dict[str, Any]:
    hw = detect_hardware()
    profile = choose_profile(hw)
    config = profile_config(profile)
    return {
        "enabled": LOCAL_AI_ENABLED,
        "mode": LOCAL_AI_MODE,
        "profile": profile,
        "hardware": hw,
        "config": config,
        "paths": {
            "data_dir": str(LOCAL_AI_DATA_DIR),
            "archive_dir": str(LOCAL_AI_ARCHIVE_DIR),
            "models_dir": str(LOCAL_AI_MODELS_DIR),
        },
        "ollama": {"base_url": OLLAMA_BASE_URL, "selected_model": config["ollama_model"]},
        "transcription": {
            "engine": TRANSCRIPTION_ENGINE,
            "model": config["whisper_model"],
            "device": config["whisper_device"],
            "compute_type": config["whisper_compute_type"],
            "whisperx": config["whisperx"],
        },
        "modes": runtime_modes(),
    }


def register_local_ai_runtime_routes(app: FastAPI) -> None:
    @app.get("/local-ai/status")
    def local_ai_status_route():
        return JSONResponse({"ok": True, "local_ai": local_ai_status()})

    @app.get("/api/local-ai/status")
    def api_local_ai_status_route():
        return JSONResponse({"ok": True, "local_ai": local_ai_status()})
