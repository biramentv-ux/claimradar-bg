from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from local_ai_runtime import OLLAMA_BASE_URL, local_ai_status

LOCAL_LLM_ENABLED = os.getenv("LOCAL_LLM_ENABLED", "1").lower() not in {"0", "false", "no"}
LOCAL_LLM_TIMEOUT_SECONDS = int(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "180"))
LOCAL_LLM_TEMPERATURE = float(os.getenv("LOCAL_LLM_TEMPERATURE", "0.1"))
LOCAL_LLM_MAX_INPUT_CHARS = int(os.getenv("LOCAL_LLM_MAX_INPUT_CHARS", "24000"))
LOCAL_LLM_KEEP_ALIVE = os.getenv("LOCAL_LLM_KEEP_ALIVE", "10m")
MODEL_RE = re.compile(r"^[A-Za-z0-9_.:/@+-]{1,120}$")


def _ollama_url(path: str) -> str:
    return f"{OLLAMA_BASE_URL.rstrip('/')}{path}"


def _model_from_profile() -> str:
    try:
        from local_model_manager import read_model_config

        cfg = read_model_config()
        profile = cfg.get("active_profile") or local_ai_status().get("profile") or "balanced"
        if profile == "auto":
            profile = local_ai_status().get("profile") or "balanced"
        model = (cfg.get("ollama_models") or {}).get(profile)
        if model:
            return str(model)
    except Exception:
        pass
    return os.getenv("LOCAL_LLM_MODEL", "llama3.2:3b")


def _safe_model(model: str | None = None) -> str:
    value = (model or _model_from_profile()).strip()
    if not MODEL_RE.match(value):
        return "llama3.2:3b"
    return value


def _try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None
    return None


def ollama_status() -> Dict[str, Any]:
    try:
        response = requests.get(_ollama_url("/api/tags"), timeout=4)
        return {"available": response.ok, "status_code": response.status_code, "base_url": OLLAMA_BASE_URL, "selected_model": _safe_model()}
    except Exception as exc:
        return {"available": False, "error": str(exc), "base_url": OLLAMA_BASE_URL, "selected_model": _safe_model()}


def ollama_generate(prompt: str, model: str | None = None, system: str = "", json_mode: bool = False, timeout: int | None = None) -> Dict[str, Any]:
    prompt = str(prompt or "")[:LOCAL_LLM_MAX_INPUT_CHARS]
    body: Dict[str, Any] = {
        "model": _safe_model(model),
        "prompt": prompt,
        "stream": False,
        "keep_alive": LOCAL_LLM_KEEP_ALIVE,
        "options": {"temperature": LOCAL_LLM_TEMPERATURE},
    }
    if system:
        body["system"] = system
    if json_mode:
        body["format"] = "json"
    started = time.time()
    try:
        response = requests.post(_ollama_url("/api/generate"), json=body, timeout=timeout or LOCAL_LLM_TIMEOUT_SECONDS)
        payload = response.json()
        text = str(payload.get("response", "")) if isinstance(payload, dict) else ""
        return {
            "ok": response.ok,
            "status_code": response.status_code,
            "model": body["model"],
            "response": text,
            "json": _try_json(text) if json_mode else None,
            "duration_seconds": round(time.time() - started, 3),
            "raw": payload if isinstance(payload, dict) else {},
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "model": body["model"], "duration_seconds": round(time.time() - started, 3)}


def extract_claims(text: str, model: str | None = None) -> Dict[str, Any]:
    system = "You are a local claim extraction engine. Return only valid JSON."
    prompt = (
        "Extract factual claims from the Bulgarian or English text. "
        "Return JSON with key claims, where each claim has text, topic, confidence from 0 to 1, and checkability.\n\n"
        f"TEXT:\n{text[:LOCAL_LLM_MAX_INPUT_CHARS]}"
    )
    result = ollama_generate(prompt, model=model, system=system, json_mode=True)
    parsed = result.get("json")
    claims = []
    if isinstance(parsed, dict) and isinstance(parsed.get("claims"), list):
        claims = parsed["claims"]
    elif isinstance(parsed, list):
        claims = parsed
    return {"ok": result.get("ok", False), "model": result.get("model"), "claims": claims, "raw": result}


def local_verdict(text: str, evidence: List[Dict[str, Any]] | None = None, model: str | None = None) -> Dict[str, Any]:
    evidence = evidence or []
    system = "You are a cautious local fact-checking assistant. Return only valid JSON."
    prompt = (
        "Analyze the claim using the provided local evidence. "
        "Return JSON with verdict, confidence, reasoning, missing_evidence, and recommended_next_steps. "
        "Use verdict values: true, mostly_true, mixed, unsupported, misleading, false, unverifiable.\n\n"
        f"CLAIM_OR_TEXT:\n{text[:12000]}\n\nLOCAL_EVIDENCE:\n{json.dumps(evidence[:8], ensure_ascii=False)[:12000]}"
    )
    result = ollama_generate(prompt, model=model, system=system, json_mode=True)
    parsed = result.get("json") if isinstance(result.get("json"), dict) else {}
    return {"ok": result.get("ok", False), "model": result.get("model"), "verdict": parsed, "raw": result}


def register_local_llm_routes(app: FastAPI) -> None:
    @app.get("/api/local-ai/llm/status")
    def api_local_llm_status():
        return JSONResponse({"ok": True, "llm": {"enabled": LOCAL_LLM_ENABLED, **ollama_status()}})

    @app.post("/api/local-ai/llm/generate")
    async def api_local_llm_generate(request: Request):
        payload = await request.json()
        if not isinstance(payload, dict):
            return JSONResponse({"ok": False, "error": "invalid_payload"}, status_code=400)
        result = ollama_generate(str(payload.get("prompt", "")), model=payload.get("model"), system=str(payload.get("system", "")), json_mode=bool(payload.get("json_mode", False)))
        return JSONResponse(result, status_code=200 if result.get("ok") else 502)

    @app.post("/api/local-ai/claims/extract")
    async def api_local_claims_extract(request: Request):
        payload = await request.json()
        result = extract_claims(str((payload or {}).get("text", "")), model=(payload or {}).get("model"))
        return JSONResponse(result, status_code=200 if result.get("ok") else 502)

    @app.post("/api/local-ai/verdict")
    async def api_local_verdict(request: Request):
        payload = await request.json()
        evidence = payload.get("evidence") if isinstance(payload, dict) else []
        result = local_verdict(str((payload or {}).get("text", "")), evidence=evidence if isinstance(evidence, list) else [], model=(payload or {}).get("model"))
        return JSONResponse(result, status_code=200 if result.get("ok") else 502)
