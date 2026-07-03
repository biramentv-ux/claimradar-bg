from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from local_ai_runtime import local_ai_status

LOCAL_TRANSCRIPTION_ENABLED = os.getenv("LOCAL_TRANSCRIPTION_ENABLED", "1").lower() not in {"0", "false", "no"}
LOCAL_TRANSCRIPTION_MAX_MB = int(os.getenv("LOCAL_TRANSCRIPTION_MAX_MB", "2048"))
LOCAL_TRANSCRIPTION_TMP_DIR = Path(os.getenv("LOCAL_TRANSCRIPTION_TMP_DIR", "data/local_ai/tmp")).expanduser()


def transcription_config() -> Dict[str, Any]:
    status = local_ai_status()
    cfg = status.get("transcription") or {}
    try:
        from local_model_manager import read_model_config

        saved = read_model_config()
        profile = saved.get("active_profile") if saved.get("active_profile") != "auto" else status.get("profile")
        whisper_models = saved.get("whisper_models") or {}
        cfg["engine"] = saved.get("transcription_engine", cfg.get("engine", "faster-whisper"))
        cfg["model"] = whisper_models.get(profile, cfg.get("model", "large-v3"))
        cfg["device"] = saved.get("whisper_device", cfg.get("device", "auto"))
        cfg["compute_type"] = saved.get("whisper_compute_type", cfg.get("compute_type", "int8"))
        cfg.setdefault("whisperx", {})["enabled"] = bool(saved.get("whisperx_enabled", False))
    except Exception:
        pass
    return cfg


def _segments_to_dicts(segments: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for seg in segments or []:
        if isinstance(seg, dict):
            rows.append({"start": seg.get("start"), "end": seg.get("end"), "text": str(seg.get("text", "")).strip(), "speaker": seg.get("speaker")})
        else:
            rows.append({"start": getattr(seg, "start", None), "end": getattr(seg, "end", None), "text": str(getattr(seg, "text", "")).strip()})
    return rows


def transcribe_with_faster_whisper(path: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    started = time.time()
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        return {"ok": False, "error": "faster_whisper_not_installed", "details": str(exc)}
    try:
        model = WhisperModel(str(cfg.get("model") or "large-v3"), device=str(cfg.get("device") or "auto"), compute_type=str(cfg.get("compute_type") or "int8"))
        segments, info = model.transcribe(path, beam_size=5, vad_filter=True)
        rows = _segments_to_dicts(list(segments))
        return {
            "ok": True,
            "engine": "faster-whisper",
            "model": cfg.get("model"),
            "device": cfg.get("device"),
            "compute_type": cfg.get("compute_type"),
            "language": getattr(info, "language", None),
            "language_probability": getattr(info, "language_probability", None),
            "duration_seconds": round(time.time() - started, 3),
            "text": " ".join(row.get("text", "") for row in rows).strip(),
            "segments": rows,
        }
    except Exception as exc:
        return {"ok": False, "error": "faster_whisper_transcription_failed", "details": str(exc), "duration_seconds": round(time.time() - started, 3)}


def transcribe_with_whisperx(path: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    started = time.time()
    try:
        import whisperx
    except Exception as exc:
        return {"ok": False, "error": "whisperx_not_installed", "details": str(exc)}
    try:
        device = "cuda" if str(cfg.get("device")) == "cuda" else "cpu"
        compute_type = str(cfg.get("compute_type") or ("float16" if device == "cuda" else "int8"))
        model_name = str(cfg.get("model") or "large-v3")
        model = whisperx.load_model(model_name, device, compute_type=compute_type)
        audio = whisperx.load_audio(path)
        result = model.transcribe(audio, batch_size=int((cfg.get("whisperx") or {}).get("batch_size") or 8))
        try:
            align_model, metadata = whisperx.load_align_model(language_code=result.get("language", "en"), device=device)
            result = whisperx.align(result.get("segments", []), align_model, metadata, audio, device, return_char_alignments=False)
        except Exception as exc:
            result.setdefault("alignment_warning", str(exc))
        rows = _segments_to_dicts(result.get("segments", []))
        return {
            "ok": True,
            "engine": "whisperx",
            "model": model_name,
            "device": device,
            "compute_type": compute_type,
            "language": result.get("language"),
            "duration_seconds": round(time.time() - started, 3),
            "text": " ".join(row.get("text", "") for row in rows).strip(),
            "segments": rows,
            "raw_keys": sorted(result.keys()),
        }
    except Exception as exc:
        return {"ok": False, "error": "whisperx_transcription_failed", "details": str(exc), "duration_seconds": round(time.time() - started, 3)}


def local_transcribe_file(path: str, engine: str | None = None) -> Dict[str, Any]:
    cfg = transcription_config()
    selected = (engine or cfg.get("engine") or "faster-whisper").strip().lower()
    if selected == "whisperx":
        return transcribe_with_whisperx(path, cfg)
    return transcribe_with_faster_whisper(path, cfg)


async def _save_request_upload(request: Request) -> Dict[str, Any]:
    LOCAL_TRANSCRIPTION_TMP_DIR.mkdir(parents=True, exist_ok=True)
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        return {"ok": False, "error": "missing_file"}
    suffix = Path(getattr(upload, "filename", "audio.bin") or "audio.bin").suffix or ".bin"
    target = Path(tempfile.mkstemp(prefix="claimradar_audio_", suffix=suffix, dir=str(LOCAL_TRANSCRIPTION_TMP_DIR))[1])
    size = 0
    with target.open("wb") as fh:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > LOCAL_TRANSCRIPTION_MAX_MB * 1024 * 1024:
                target.unlink(missing_ok=True)
                return {"ok": False, "error": "file_too_large", "max_mb": LOCAL_TRANSCRIPTION_MAX_MB}
            fh.write(chunk)
    return {"ok": True, "path": str(target), "size_bytes": size}


def register_local_transcription_routes(app: FastAPI) -> None:
    @app.get("/api/local-ai/transcribe/status")
    def api_transcribe_status():
        return JSONResponse({"ok": True, "transcription": {"enabled": LOCAL_TRANSCRIPTION_ENABLED, **transcription_config()}})

    @app.post("/api/local-ai/transcribe")
    async def api_transcribe(request: Request):
        saved = await _save_request_upload(request)
        if not saved.get("ok"):
            return JSONResponse(saved, status_code=400)
        engine = request.query_params.get("engine") or None
        result = local_transcribe_file(str(saved["path"]), engine=engine)
        result["input"] = {"size_bytes": saved.get("size_bytes")}
        return JSONResponse(result, status_code=200 if result.get("ok") else 501)
