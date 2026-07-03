from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from local_ai_runtime import choose_profile, detect_hardware, local_ai_status

BENCHMARK_LLM_PROMPT = os.getenv("BENCHMARK_LLM_PROMPT", "Respond with one short JSON object: {\"ok\": true}.")
BENCHMARK_TRANSCRIPTION_SAMPLE_SECONDS = int(os.getenv("BENCHMARK_TRANSCRIPTION_SAMPLE_SECONDS", "0"))
LAST_BENCHMARK: Dict[str, Any] = {}


def run_cpu_benchmark() -> Dict[str, Any]:
    started = time.time()
    total = 0
    for i in range(1, 250000):
        total += (i * i) % 97
    duration = time.time() - started
    return {"duration_seconds": round(duration, 4), "score": round(250000 / max(duration, 0.001), 2), "checksum": total}


def run_llm_benchmark() -> Dict[str, Any]:
    try:
        from local_llm_engine import ollama_generate

        result = ollama_generate(BENCHMARK_LLM_PROMPT, json_mode=True, timeout=45)
        raw = result.get("raw") or {}
        eval_count = int(raw.get("eval_count") or 0)
        eval_duration = int(raw.get("eval_duration") or 0)
        token_per_second = round(eval_count / eval_duration * 1_000_000_000, 2) if eval_count and eval_duration else 0
        return {"available": bool(result.get("ok")), "token_per_second": token_per_second, "duration_seconds": result.get("duration_seconds"), "model": result.get("model"), "error": result.get("error")}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def recommend_profile(hw: Dict[str, Any], cpu: Dict[str, Any], llm: Dict[str, Any]) -> str:
    base = choose_profile(hw)
    if llm.get("token_per_second", 0) and llm.get("token_per_second", 0) < 6:
        return "low"
    if base == "power" and cpu.get("duration_seconds", 9) < 0.15:
        return "power"
    return base


def run_hardware_benchmark(include_llm: bool = False) -> Dict[str, Any]:
    hw = detect_hardware()
    cpu = run_cpu_benchmark()
    llm = run_llm_benchmark() if include_llm else {"skipped": True}
    recommended = recommend_profile(hw, cpu, llm if isinstance(llm, dict) else {})
    result = {"hardware": hw, "cpu": cpu, "llm": llm, "recommended_profile": recommended, "local_ai": local_ai_status(), "created_at": time.time()}
    LAST_BENCHMARK.clear()
    LAST_BENCHMARK.update(result)
    return result


def register_hardware_benchmark_routes(app: FastAPI) -> None:
    @app.get("/api/local-ai/benchmark/status")
    def api_benchmark_status():
        return JSONResponse({"ok": True, "benchmark": LAST_BENCHMARK or {"status": "not_run"}})

    @app.post("/api/local-ai/benchmark/run")
    async def api_benchmark_run(request: Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        result = run_hardware_benchmark(include_llm=bool((payload or {}).get("include_llm", False)))
        return JSONResponse({"ok": True, "benchmark": result})
