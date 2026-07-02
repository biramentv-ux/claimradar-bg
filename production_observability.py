from __future__ import annotations

import json
import os
import time
import uuid
from html import escape
from pathlib import Path
from typing import Any, Callable, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

import app as app_module
from custom_domain import custom_domain_config
from external_queue import external_queue_status
from hardware_inference import inference_status
from monitoring import RECENT_ERRORS, RECENT_REQUESTS, public_metrics, read_events, write_event
from rate_limit_api import rate_limit_status
from search_providers import active_search_config, provider_order

JsonRowsReader = Callable[[Path, int], List[Dict[str, Any]]]

OBSERVABILITY_ENABLED = os.getenv("OBSERVABILITY_ENABLED", "1").lower() not in {"0", "false", "no"}
OBSERVABILITY_LOG_FILE = Path(os.getenv("OBSERVABILITY_LOG_FILE", "data/observability_events.jsonl"))
OBSERVABILITY_COST_FILE = Path(os.getenv("OBSERVABILITY_COST_FILE", "data/ai_usage_costs.jsonl"))
OBSERVABILITY_LATENCY_SLO_MS = int(os.getenv("OBSERVABILITY_LATENCY_SLO_MS", "2500"))
OBSERVABILITY_ERROR_RATE_SLO = float(os.getenv("OBSERVABILITY_ERROR_RATE_SLO", "0.05"))
OBSERVABILITY_PROMETHEUS_ENABLED = os.getenv("OBSERVABILITY_PROMETHEUS_ENABLED", "1").lower() not in {"0", "false", "no"}
OPENAI_INPUT_COST_PER_1M = float(os.getenv("OPENAI_INPUT_COST_PER_1M", "0"))
OPENAI_OUTPUT_COST_PER_1M = float(os.getenv("OPENAI_OUTPUT_COST_PER_1M", "0"))


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    if not OBSERVABILITY_ENABLED:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def _read_jsonl(path: Path, limit: int = 1000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
        except json.JSONDecodeError:
            continue
    return rows


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def record_ai_usage(provider: str, model: str, input_tokens: int = 0, output_tokens: int = 0, cost_usd: float | None = None, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    input_tokens = max(0, int(input_tokens or 0))
    output_tokens = max(0, int(output_tokens or 0))
    if cost_usd is None:
        if provider.lower() == "openai":
            cost_usd = (input_tokens / 1_000_000 * OPENAI_INPUT_COST_PER_1M) + (output_tokens / 1_000_000 * OPENAI_OUTPUT_COST_PER_1M)
        else:
            cost_usd = 0.0
    row = {
        "id": uuid.uuid4().hex[:12],
        "ts": _now_iso(),
        "provider": provider[:80] or "unknown",
        "model": model[:120] or "unknown",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": round(float(cost_usd or 0), 8),
        "meta": meta or {},
    }
    _append_jsonl(OBSERVABILITY_COST_FILE, row)
    write_event({"kind": "ai_usage", "level": "info", "message": f"AI usage recorded for {provider}/{model}", "data": {"tokens": row["total_tokens"], "cost_usd": row["cost_usd"]}})
    return row


def ai_cost_summary(limit: int = 5000) -> Dict[str, Any]:
    rows = _read_jsonl(OBSERVABILITY_COST_FILE, limit=limit)
    by_provider: Dict[str, Dict[str, Any]] = {}
    by_model: Dict[str, Dict[str, Any]] = {}
    total_tokens = 0
    total_cost = 0.0
    for row in rows:
        provider = str(row.get("provider") or "unknown")
        model = str(row.get("model") or "unknown")
        tokens = int(row.get("total_tokens") or 0)
        cost = _safe_float(row.get("cost_usd"))
        total_tokens += tokens
        total_cost += cost
        by_provider.setdefault(provider, {"tokens": 0, "cost_usd": 0.0, "calls": 0})
        by_provider[provider]["tokens"] += tokens
        by_provider[provider]["cost_usd"] = round(by_provider[provider]["cost_usd"] + cost, 8)
        by_provider[provider]["calls"] += 1
        by_model.setdefault(model, {"tokens": 0, "cost_usd": 0.0, "calls": 0})
        by_model[model]["tokens"] += tokens
        by_model[model]["cost_usd"] = round(by_model[model]["cost_usd"] + cost, 8)
        by_model[model]["calls"] += 1
    return {
        "events": len(rows),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 8),
        "by_provider": by_provider,
        "by_model": by_model,
        "recent": rows[-20:][::-1],
        "cost_config": {"openai_input_per_1m": OPENAI_INPUT_COST_PER_1M, "openai_output_per_1m": OPENAI_OUTPUT_COST_PER_1M},
    }


def provider_health() -> Dict[str, Any]:
    search_cfg = active_search_config()
    available = search_cfg.get("available_api_providers", {}) if isinstance(search_cfg, dict) else {}
    search_health = {}
    for provider in provider_order():
        configured = bool(available.get(provider, False)) if provider != "google" else bool(available.get("google_cse", False))
        if provider == "duckduckgo":
            configured = True
        search_health[provider] = {
            "configured": configured,
            "status": "configured" if configured else "missing_credentials",
            "strict_whitelist": bool(search_cfg.get("strict_whitelist", True)) if isinstance(search_cfg, dict) else True,
        }
    ai_health = {
        "openai": {
            "configured": bool(os.getenv("OPENAI_API_KEY", "")),
            "model": os.getenv("OPENAI_MODEL", ""),
            "status": "configured" if os.getenv("OPENAI_API_KEY", "") else "missing_credentials",
        },
        "dedicated_inference": inference_status(app_module).get("dedicated", {}),
    }
    return {"search": search_health, "ai": ai_health, "search_config": search_cfg}


def latency_percentiles() -> Dict[str, float]:
    values = sorted([_safe_float(row.get("latency_ms")) for row in list(RECENT_REQUESTS) if row.get("latency_ms") is not None])
    if not values:
        return {"p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}

    def pct(p: float) -> float:
        idx = min(len(values) - 1, max(0, int(round((len(values) - 1) * p))))
        return round(values[idx], 2)

    return {"p50_ms": pct(0.50), "p95_ms": pct(0.95), "p99_ms": pct(0.99)}


def slo_status(metrics: Dict[str, Any]) -> Dict[str, Any]:
    requests_total = int(metrics.get("requests_total") or 0)
    errors_total = int(metrics.get("errors_total") or 0)
    error_rate = (errors_total / requests_total) if requests_total else 0.0
    avg_latency = _safe_float(metrics.get("avg_latency_ms"))
    p = latency_percentiles()
    return {
        "ok": error_rate <= OBSERVABILITY_ERROR_RATE_SLO and p["p95_ms"] <= OBSERVABILITY_LATENCY_SLO_MS,
        "error_rate": round(error_rate, 6),
        "error_rate_slo": OBSERVABILITY_ERROR_RATE_SLO,
        "avg_latency_ms": round(avg_latency, 2),
        "latency_slo_ms": OBSERVABILITY_LATENCY_SLO_MS,
        **p,
    }


def observability_summary(job_store: Any, storage: Any, read_jsonl: JsonRowsReader) -> Dict[str, Any]:
    metrics = public_metrics()
    try:
        jobs = job_store.stats()
    except Exception as exc:
        jobs = {"error": str(exc)}
    try:
        db = storage.status()
    except Exception as exc:
        db = {"connected": False, "error": str(exc)}
    queue = external_queue_status(job_store)
    providers = provider_health()
    cost = ai_cost_summary()
    status = slo_status(metrics)
    return {
        "generated_at": _now_iso(),
        "enabled": OBSERVABILITY_ENABLED,
        "uptime": {"status": "up", "seconds": metrics.get("uptime_seconds", 0), "started_at": metrics.get("started_at")},
        "latency": {"avg_ms": metrics.get("avg_latency_ms", 0), "max_ms": metrics.get("max_latency_ms", 0), **latency_percentiles()},
        "errors": {"total": metrics.get("errors_total", 0), "error_rate": status["error_rate"], "recent_errors": list(RECENT_ERRORS)[:20]},
        "requests": {"total": metrics.get("requests_total", 0), "status_counts": metrics.get("status_counts", {}), "method_counts": metrics.get("method_counts", {}), "top_paths": metrics.get("top_paths", [])},
        "jobs": jobs,
        "queue": queue,
        "providers": providers,
        "cost": cost,
        "db": db,
        "custom_domain": custom_domain_config(),
        "slo": status,
        "events": read_events(limit=30),
        "links": {"dashboard": "/observability", "summary": "/api/observability/summary", "metrics": "/metrics", "providers": "/api/observability/providers", "costs": "/api/observability/costs"},
    }


def _prom_escape_label(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')[:160]


def prometheus_text(summary: Dict[str, Any]) -> str:
    metrics = []

    def line(name: str, value: Any, labels: Dict[str, Any] | None = None, help_text: str = "", typ: str = "gauge") -> None:
        if help_text:
            metrics.append(f"# HELP {name} {help_text}")
            metrics.append(f"# TYPE {name} {typ}")
        label_text = ""
        if labels:
            label_text = "{" + ",".join([f'{k}="{_prom_escape_label(v)}"' for k, v in labels.items()]) + "}"
        metrics.append(f"{name}{label_text} {float(value or 0)}")

    line("claimradar_up", 1, help_text="ClaimRadar app process is serving observability requests")
    line("claimradar_uptime_seconds", summary["uptime"].get("seconds", 0), help_text="Application uptime in seconds")
    line("claimradar_requests_total", summary["requests"].get("total", 0), help_text="Total observed HTTP requests", typ="counter")
    line("claimradar_errors_total", summary["errors"].get("total", 0), help_text="Total observed HTTP 4xx/5xx requests", typ="counter")
    line("claimradar_error_rate", summary["errors"].get("error_rate", 0), help_text="Observed error rate")
    line("claimradar_latency_avg_ms", summary["latency"].get("avg_ms", 0), help_text="Average HTTP latency in milliseconds")
    line("claimradar_latency_p95_ms", summary["latency"].get("p95_ms", 0), help_text="Recent p95 HTTP latency in milliseconds")
    line("claimradar_ai_tokens_total", summary["cost"].get("total_tokens", 0), help_text="Total recorded AI tokens", typ="counter")
    line("claimradar_ai_cost_usd_total", summary["cost"].get("total_cost_usd", 0), help_text="Total recorded AI cost in USD", typ="counter")
    line("claimradar_jobs_total", summary["jobs"].get("total", 0), help_text="Total jobs in job store")
    for status, count in (summary["jobs"].get("status_counts", {}) or {}).items():
        line("claimradar_jobs_by_status", count, {"status": status})
    for provider, health in (summary["providers"].get("search", {}) or {}).items():
        line("claimradar_search_provider_configured", 1 if health.get("configured") else 0, {"provider": provider})
    for provider, health in (summary["providers"].get("ai", {}) or {}).items():
        if isinstance(health, dict):
            line("claimradar_ai_provider_configured", 1 if health.get("configured") or health.get("enabled") else 0, {"provider": provider})
    metrics.append("")
    return "\n".join(metrics)


def observability_html(summary: Dict[str, Any], admin_key: str = "") -> str:
    def card(title: str, value: Any, hint: str = "") -> str:
        return f"<div class='card'><div class='muted'>{escape(title)}</div><div class='big'>{escape(str(value))}</div><div class='hint'>{escape(str(hint))}</div></div>"

    providers = summary.get("providers", {})
    search_rows = "".join([f"<tr><td>{escape(k)}</td><td>{escape(v.get('status',''))}</td><td>{'yes' if v.get('configured') else 'no'}</td></tr>" for k, v in (providers.get("search", {}) or {}).items()])
    ai_rows = "".join([f"<tr><td>{escape(k)}</td><td>{escape(str(v.get('status', v.get('enabled', '')))) if isinstance(v, dict) else ''}</td><td>{escape(str(v.get('model',''))) if isinstance(v, dict) else ''}</td></tr>" for k, v in (providers.get("ai", {}) or {}).items()])
    event_rows = "".join([f"<tr><td>{escape(str(e.get('ts','')))}</td><td>{escape(str(e.get('level','')))}</td><td>{escape(str(e.get('kind','')))}</td><td>{escape(str(e.get('message',''))[:180])}</td></tr>" for e in summary.get("events", [])[:20]])
    q = f"?admin_key={escape(admin_key)}" if admin_key else ""
    cards = "".join([
        card("Uptime", f"{summary['uptime'].get('seconds', 0)}s", summary['uptime'].get('status')),
        card("Requests", summary['requests'].get('total', 0), "total observed"),
        card("Error rate", summary['errors'].get('error_rate', 0), f"SLO <= {summary['slo'].get('error_rate_slo')}"),
        card("P95 latency", f"{summary['latency'].get('p95_ms', 0)} ms", f"SLO <= {summary['slo'].get('latency_slo_ms')} ms"),
        card("AI cost", f"${summary['cost'].get('total_cost_usd', 0)}", f"tokens: {summary['cost'].get('total_tokens', 0)}"),
        card("Jobs", summary['jobs'].get('total', 0), f"running: {summary['jobs'].get('running', 0)}"),
    ])
    return f"""<!doctype html><html lang='bg'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Production Observability · ClaimRadar BG</title><style>body{{margin:0;background:#020617;color:#e5e7eb;font-family:Arial,sans-serif}}main{{max-width:1240px;margin:auto;padding:28px 18px 70px}}.hero,.card,.panel{{border:1px solid rgba(34,211,238,.24);border-radius:24px;background:linear-gradient(135deg,rgba(2,6,23,.96),rgba(30,27,75,.72));box-shadow:0 0 34px rgba(34,211,238,.14)}}.hero{{padding:30px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-top:18px}}.card,.panel{{padding:18px;margin-top:16px}}h1{{font-size:48px;margin:8px 0;color:#fff}}h2{{color:#fff}}.muted{{color:#94a3b8;text-transform:uppercase;font-size:12px;letter-spacing:.08em}}.big{{font-size:28px;font-weight:900;color:#fff;margin:8px 0}}.hint,p,td{{color:#cbd5e1;line-height:1.55}}a.button{{display:inline-flex;border:1px solid rgba(34,211,238,.28);background:rgba(15,23,42,.78);color:#e0f2fe;border-radius:12px;padding:9px 11px;text-decoration:none;font-weight:700;margin:4px}}table{{width:100%;border-collapse:collapse}}td{{border-top:1px solid rgba(148,163,184,.18);padding:9px;vertical-align:top}}pre{{white-space:pre-wrap;background:rgba(15,23,42,.76);border-radius:14px;padding:14px;color:#cbd5e1;max-height:380px;overflow:auto}}</style></head><body><main><section class='hero'><div class='muted'>ClaimRadar BG · production observability</div><h1>Production Observability</h1><p>Uptime, latency, error rate, token cost, search provider health, AI provider health, jobs, queue, DB и recent events.</p><a class='button' href='/api/observability/summary{q}'>JSON summary</a><a class='button' href='/metrics'>Prometheus metrics</a><a class='button' href='/api/observability/providers{q}'>Providers</a><a class='button' href='/api/observability/costs{q}'>Costs</a><a class='button' href='/admin{q}'>Admin</a></section><section class='grid'>{cards}</section><section class='panel'><h2>Search provider health</h2><table><tr><td>Provider</td><td>Status</td><td>Configured</td></tr>{search_rows}</table></section><section class='panel'><h2>AI provider health</h2><table><tr><td>Provider</td><td>Status</td><td>Model</td></tr>{ai_rows}</table></section><section class='panel'><h2>Recent events</h2><table><tr><td>Time</td><td>Level</td><td>Kind</td><td>Message</td></tr>{event_rows}</table></section><section class='panel'><h2>Raw summary</h2><pre>{escape(json.dumps(summary, ensure_ascii=False, indent=2, default=str)[:9000])}</pre></section></main></body></html>"""


def _extract_admin_key(request: Request, payload: Dict[str, Any] | None = None) -> str:
    payload = payload or {}
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return str(payload.get("admin_key") or payload.get("api_key") or request.query_params.get("admin_key") or request.headers.get("x-admin-key") or request.headers.get("x-api-key") or "")


def register_observability_routes(app: FastAPI, can_admin: Callable[[str], bool], job_store: Any, storage: Any, read_jsonl: JsonRowsReader) -> None:
    def summary() -> Dict[str, Any]:
        return observability_summary(job_store, storage, read_jsonl)

    @app.get("/observability", response_class=HTMLResponse)
    def observability_dashboard(request: Request):
        return HTMLResponse(observability_html(summary(), admin_key=request.query_params.get("admin_key", "")))

    @app.get("/observability/status")
    def observability_status():
        data = summary()
        return JSONResponse({"ok": bool(data.get("slo", {}).get("ok", True)), "observability": data.get("slo"), "links": data.get("links")})

    @app.get("/api/observability/summary")
    def api_observability_summary():
        return JSONResponse({"ok": True, "observability": summary()})

    @app.get("/api/observability/providers")
    def api_observability_providers():
        return JSONResponse({"ok": True, "providers": provider_health()})

    @app.get("/api/observability/costs")
    def api_observability_costs():
        return JSONResponse({"ok": True, "cost": ai_cost_summary()})

    @app.post("/api/observability/ai-usage")
    async def api_observability_ai_usage(request: Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not can_admin(_extract_admin_key(request, payload)):
            return JSONResponse({"ok": False, "error": "admin_required"}, status_code=403)
        row = record_ai_usage(
            provider=str(payload.get("provider") or "openai"),
            model=str(payload.get("model") or os.getenv("OPENAI_MODEL", "unknown")),
            input_tokens=int(payload.get("input_tokens") or 0),
            output_tokens=int(payload.get("output_tokens") or 0),
            cost_usd=payload.get("cost_usd"),
            meta=payload.get("meta") if isinstance(payload.get("meta"), dict) else {},
        )
        return JSONResponse({"ok": True, "usage": row, "cost": ai_cost_summary()})

    @app.get("/metrics")
    def prometheus_metrics():
        if not OBSERVABILITY_PROMETHEUS_ENABLED:
            return Response("# Prometheus metrics disabled\n", media_type="text/plain; version=0.0.4; charset=utf-8")
        return Response(prometheus_text(summary()), media_type="text/plain; version=0.0.4; charset=utf-8")
