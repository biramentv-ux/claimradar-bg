from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List

import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from local_ai_runtime import LOCAL_AI_DATA_DIR, LOCAL_AI_MODELS_DIR, OLLAMA_BASE_URL, WHISPER_MODEL_BALANCED, WHISPER_MODEL_LOW, WHISPER_MODEL_POWER, local_ai_status

MODEL_MANAGER_ENABLED = os.getenv("MODEL_MANAGER_ENABLED", "1").lower() not in {"0", "false", "no"}
MODEL_MANAGER_CONFIG_PATH = Path(os.getenv("MODEL_MANAGER_CONFIG_PATH", str(LOCAL_AI_DATA_DIR / "model_manager.json"))).expanduser()
MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9_.:/@+-]{1,120}$")
ALLOWED_PROFILES = {"low", "balanced", "power"}
ALLOWED_TRANSCRIPTION_ENGINES = {"faster-whisper", "whisperx"}
ALLOWED_COMPUTE_TYPES = {"int8", "int8_float16", "float16", "float32"}
ALLOWED_DEVICES = {"auto", "cpu", "cuda"}
DEFAULT_OLLAMA_MODELS = {"low": "llama3.2:3b", "balanced": "llama3.1:8b", "power": "llama3.1:8b"}
DEFAULT_WHISPER_MODELS = {"low": WHISPER_MODEL_LOW, "balanced": WHISPER_MODEL_BALANCED, "power": WHISPER_MODEL_POWER}


def default_model_config() -> Dict[str, Any]:
    return {
        "active_profile": "auto",
        "offline_mode": True,
        "online_evidence_mode": False,
        "ollama_models": DEFAULT_OLLAMA_MODELS.copy(),
        "whisper_models": DEFAULT_WHISPER_MODELS.copy(),
        "transcription_engine": os.getenv("TRANSCRIPTION_ENGINE", "faster-whisper"),
        "whisper_device": os.getenv("WHISPER_DEVICE", "auto"),
        "whisper_compute_type": os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        "whisperx_enabled": os.getenv("WHISPERX_ENABLED", "1").lower() not in {"0", "false", "no"},
        "updated_at": None,
    }


def read_model_config() -> Dict[str, Any]:
    cfg = default_model_config()
    try:
        if MODEL_MANAGER_CONFIG_PATH.exists():
            saved = json.loads(MODEL_MANAGER_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                cfg.update(saved)
    except Exception:
        pass
    cfg.setdefault("ollama_models", DEFAULT_OLLAMA_MODELS.copy())
    cfg.setdefault("whisper_models", DEFAULT_WHISPER_MODELS.copy())
    return cfg


def _valid_model_name(value: Any) -> bool:
    return isinstance(value, str) and bool(MODEL_NAME_RE.match(value.strip()))


def sanitize_model_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    current = read_model_config()
    active_profile = str(payload.get("active_profile", current.get("active_profile", "auto"))).strip().lower()
    if active_profile not in {"auto", *ALLOWED_PROFILES}:
        active_profile = "auto"
    ollama_models = dict(current.get("ollama_models") or DEFAULT_OLLAMA_MODELS)
    whisper_models = dict(current.get("whisper_models") or DEFAULT_WHISPER_MODELS)
    for profile, model in dict(payload.get("ollama_models") or {}).items():
        profile = str(profile).strip().lower()
        if profile in ALLOWED_PROFILES and _valid_model_name(model):
            ollama_models[profile] = str(model).strip()
    for profile, model in dict(payload.get("whisper_models") or {}).items():
        profile = str(profile).strip().lower()
        if profile in ALLOWED_PROFILES and _valid_model_name(model):
            whisper_models[profile] = str(model).strip()
    engine = str(payload.get("transcription_engine", current.get("transcription_engine", "faster-whisper"))).strip().lower()
    if engine not in ALLOWED_TRANSCRIPTION_ENGINES:
        engine = "faster-whisper"
    device = str(payload.get("whisper_device", current.get("whisper_device", "auto"))).strip().lower()
    if device not in ALLOWED_DEVICES:
        device = "auto"
    compute_type = str(payload.get("whisper_compute_type", current.get("whisper_compute_type", "int8"))).strip().lower()
    if compute_type not in ALLOWED_COMPUTE_TYPES:
        compute_type = "int8"
    return {
        "active_profile": active_profile,
        "offline_mode": bool(payload.get("offline_mode", current.get("offline_mode", True))),
        "online_evidence_mode": bool(payload.get("online_evidence_mode", current.get("online_evidence_mode", False))),
        "ollama_models": ollama_models,
        "whisper_models": whisper_models,
        "transcription_engine": engine,
        "whisper_device": device,
        "whisper_compute_type": compute_type,
        "whisperx_enabled": bool(payload.get("whisperx_enabled", current.get("whisperx_enabled", True))),
        "updated_at": time.time(),
    }


def save_model_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    config = sanitize_model_config(payload)
    MODEL_MANAGER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_MANAGER_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config


def _ollama_url(path: str) -> str:
    return f"{OLLAMA_BASE_URL.rstrip('/')}{path}"


def ollama_health() -> Dict[str, Any]:
    try:
        response = requests.get(_ollama_url("/api/tags"), timeout=3)
        return {"available": response.ok, "status_code": response.status_code, "base_url": OLLAMA_BASE_URL}
    except Exception as exc:
        return {"available": False, "error": str(exc), "base_url": OLLAMA_BASE_URL}


def ollama_list_models() -> Dict[str, Any]:
    try:
        response = requests.get(_ollama_url("/api/tags"), timeout=8)
        response.raise_for_status()
        data = response.json()
        models = data.get("models") if isinstance(data, dict) else []
        return {"ok": True, "models": models if isinstance(models, list) else []}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "models": []}


def ollama_download_model(model: str) -> Dict[str, Any]:
    model = str(model or "").strip()
    if not _valid_model_name(model):
        return {"ok": False, "error": "invalid_model_name"}
    try:
        response = requests.post(_ollama_url("/api/pull"), json={"model": model, "stream": False}, timeout=1800)
        payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"text": response.text[-1000:]}
        return {"ok": response.ok, "status_code": response.status_code, "model": model, "response": payload}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "model": model}


def candidate_cache_dirs() -> List[Path]:
    dirs = [
        LOCAL_AI_MODELS_DIR,
        Path(os.getenv("HF_HOME", "~/.cache/huggingface")).expanduser(),
        Path(os.getenv("HUGGINGFACE_HUB_CACHE", "~/.cache/huggingface/hub")).expanduser(),
        Path(os.getenv("TRANSFORMERS_CACHE", "~/.cache/huggingface/transformers")).expanduser(),
    ]
    unique: List[Path] = []
    seen = set()
    for path in dirs:
        text = str(path)
        if text not in seen:
            seen.add(text)
            unique.append(path)
    return unique


def scan_whisper_cache() -> Dict[str, Any]:
    config = read_model_config()
    wanted = sorted(set((config.get("whisper_models") or {}).values()) | {"large-v3", "small", "base", "tiny"})
    matches: Dict[str, List[str]] = {model: [] for model in wanted}
    scanned_dirs: List[str] = []
    for root in candidate_cache_dirs():
        if not root.exists():
            continue
        scanned_dirs.append(str(root))
        try:
            for item in list(root.rglob("*"))[:1500]:
                if not item.is_dir():
                    continue
                item_text = str(item).lower().replace("_", "-")
                for model in wanted:
                    tokens = [token for token in re.split(r"[^A-Za-z0-9]+", model.lower()) if token]
                    if tokens and all(token in item_text for token in tokens):
                        matches[model].append(str(item))
        except Exception:
            continue
    return {"configured_models": config.get("whisper_models"), "cache_dirs": [str(path) for path in candidate_cache_dirs()], "scanned_existing_dirs": scanned_dirs, "matches": {model: sorted(set(paths))[:20] for model, paths in matches.items()}}


def model_manager_status() -> Dict[str, Any]:
    return {"enabled": MODEL_MANAGER_ENABLED, "config_path": str(MODEL_MANAGER_CONFIG_PATH), "config": read_model_config(), "local_ai": local_ai_status(), "ollama": ollama_health(), "whisper_cache": scan_whisper_cache()}


def model_manager_page() -> HTMLResponse:
    return HTMLResponse("""<!doctype html><html lang='bg'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>ClaimRadar BG Model Manager</title><style>body{margin:0;font-family:Arial,sans-serif;background:#020617;color:#e5e7eb}.shell{padding:24px;max-width:1160px;margin:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px}.card{border:1px solid rgba(34,211,238,.25);border-radius:20px;padding:18px;background:#0f172a}.kicker{color:#67e8f9;text-transform:uppercase;letter-spacing:.14em;font-weight:800;font-size:12px}input,select{box-sizing:border-box;width:100%;margin-top:6px;padding:10px;border-radius:12px;border:1px solid #164e63;background:#020617;color:#fff}label{display:block;margin-top:12px;color:#cbd5e1}button{margin-top:12px;padding:11px 14px;border:0;border-radius:14px;background:linear-gradient(90deg,#0891b2,#7c3aed);color:#fff;font-weight:700}pre{white-space:pre-wrap;max-height:360px;overflow:auto;background:#020617;border-radius:14px;padding:12px}</style></head><body><main class='shell'><div class='kicker'>ClaimRadar BG Desktop</div><h1>Local Model Manager</h1><p>Ollama модели, Low/Balanced/Power профили, faster-whisper/WhisperX и Whisper cache.</p><div class='grid'><section class='card'><h2>Runtime</h2><label>Профил</label><select id='profile'><option>auto</option><option>low</option><option>balanced</option><option>power</option></select><label>Engine</label><select id='engine'><option>faster-whisper</option><option>whisperx</option></select><label>Device</label><select id='device'><option>auto</option><option>cpu</option><option>cuda</option></select><label>Compute</label><select id='compute'><option>int8</option><option>int8_float16</option><option>float16</option><option>float32</option></select><label><input id='offline' type='checkbox'> Offline Mode</label><label><input id='online' type='checkbox'> Online Evidence Mode</label><button onclick='saveConfig()'>Запази</button></section><section class='card'><h2>Ollama</h2><label>Low</label><input id='ollamaLow'><label>Balanced</label><input id='ollamaBalanced'><label>Power</label><input id='ollamaPower'><button onclick='listOllama()'>List models</button><button onclick='downloadSelected()'>Download selected model</button><pre id='ollamaOut'>—</pre></section><section class='card'><h2>Whisper</h2><label>Low</label><input id='whisperLow'><label>Balanced</label><input id='whisperBalanced'><label>Power</label><input id='whisperPower'><label><input id='whisperx' type='checkbox'> WhisperX</label><button onclick='refreshCache()'>Провери cache</button><pre id='cacheOut'>—</pre></section><section class='card'><h2>Status</h2><button onclick='refreshAll()'>Refresh</button><pre id='statusOut'>Loading...</pre></section></div></main><script src='/local-ai/model-manager.js'></script></body></html>""")


def register_local_model_manager_routes(app: FastAPI) -> None:
    @app.get("/local-ai/models")
    def local_ai_models_page():
        if not MODEL_MANAGER_ENABLED:
            return JSONResponse({"ok": False, "error": "model_manager_disabled"}, status_code=404)
        return model_manager_page()

    @app.get("/model-manager")
    def model_manager_alias():
        return model_manager_page()

    @app.get("/api/local-ai/model-manager/status")
    def api_model_manager_status():
        return JSONResponse({"ok": True, "model_manager": model_manager_status()})

    @app.get("/api/local-ai/model-manager/config")
    def api_get_model_config():
        return JSONResponse({"ok": True, "config": read_model_config()})

    @app.post("/api/local-ai/model-manager/config")
    async def api_save_model_config(request: Request):
        payload = await request.json()
        if not isinstance(payload, dict):
            return JSONResponse({"ok": False, "error": "invalid_payload"}, status_code=400)
        return JSONResponse({"ok": True, "config": save_model_config(payload)})

    @app.get("/api/local-ai/ollama/models")
    def api_ollama_models():
        return JSONResponse(ollama_list_models())

    @app.post("/api/local-ai/ollama/download")
    async def api_ollama_download(request: Request):
        payload = await request.json()
        model = payload.get("model") if isinstance(payload, dict) else ""
        result = ollama_download_model(str(model or ""))
        return JSONResponse(result, status_code=200 if result.get("ok") else 400)

    @app.get("/api/local-ai/whisper/cache")
    def api_whisper_cache():
        return JSONResponse({"ok": True, "whisper_cache": scan_whisper_cache()})
