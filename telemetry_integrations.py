from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", os.getenv("SERVICE_NAME", "claimradar-bg"))
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "4.3-telemetry-sentry-codeql")
DEPLOYMENT_ENVIRONMENT = os.getenv("DEPLOYMENT_ENVIRONMENT", os.getenv("SENTRY_ENVIRONMENT", "production"))
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "1").lower() not in {"0", "false", "no"}
OTEL_CONSOLE_EXPORTER_ENABLED = os.getenv("OTEL_CONSOLE_EXPORTER_ENABLED", "0").lower() in {"1", "true", "yes"}
OTEL_FASTAPI_INSTRUMENTATION_ENABLED = os.getenv("OTEL_FASTAPI_INSTRUMENTATION_ENABLED", "1").lower() not in {"0", "false", "no"}
OTEL_REQUESTS_INSTRUMENTATION_ENABLED = os.getenv("OTEL_REQUESTS_INSTRUMENTATION_ENABLED", "1").lower() not in {"0", "false", "no"}
OTEL_SAMPLE_RATE = float(os.getenv("OTEL_SAMPLE_RATE", "1.0"))
SENTRY_ENABLED = os.getenv("SENTRY_ENABLED", "1").lower() not in {"0", "false", "no"}
SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
SENTRY_PROFILES_SAMPLE_RATE = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0"))
SENTRY_SEND_DEFAULT_PII = os.getenv("SENTRY_SEND_DEFAULT_PII", "0").lower() in {"1", "true", "yes"}
SENTRY_TEST_EVENTS_ENABLED = os.getenv("SENTRY_TEST_EVENTS_ENABLED", "1").lower() not in {"0", "false", "no"}

SENSITIVE_KEYWORDS = {
    "admin_key",
    "api_key",
    "auth_token",
    "authorization",
    "cookie",
    "dsn",
    "jwt",
    "key",
    "password",
    "secret",
    "session",
    "token",
}

_TELEMETRY_STATE: Dict[str, Any] = {
    "initialized": False,
    "otel_enabled": OTEL_ENABLED,
    "otel_available": False,
    "otel_error": "",
    "otel_trace_exporter": "none",
    "sentry_enabled": SENTRY_ENABLED,
    "sentry_available": False,
    "sentry_configured": bool(SENTRY_DSN),
    "sentry_error": "",
    "sentry_last_event_id": "",
    "sentry_last_test_event_id": "",
    "sentry_scrubber_enabled": True,
    "last_manual_span": None,
    "init_ts": None,
}


def _resource_attributes() -> Dict[str, str]:
    return {
        "service.name": SERVICE_NAME,
        "service.version": SERVICE_VERSION,
        "deployment.environment": DEPLOYMENT_ENVIRONMENT,
    }


def _is_sensitive_key(key: Any) -> bool:
    key_l = str(key).lower()
    return any(token in key_l for token in SENSITIVE_KEYWORDS)


def scrub_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[Filtered]" if _is_sensitive_key(key) else scrub_sensitive(val) for key, val in value.items()}
    if isinstance(value, list):
        return [scrub_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_sensitive(item) for item in value)
    return value


def sentry_before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Dict[str, Any] | None:
    event = scrub_sensitive(event)
    event.setdefault("tags", {})["service.name"] = SERVICE_NAME
    event.setdefault("tags", {})["deployment.environment"] = DEPLOYMENT_ENVIRONMENT
    return event


def sentry_before_breadcrumb(crumb: Dict[str, Any], hint: Dict[str, Any]) -> Dict[str, Any] | None:
    return scrub_sensitive(crumb)


def init_sentry() -> Dict[str, Any]:
    if not SENTRY_ENABLED:
        _TELEMETRY_STATE.update({"sentry_enabled": False, "sentry_available": False, "sentry_error": "disabled"})
        return dict(_TELEMETRY_STATE)
    if not SENTRY_DSN:
        _TELEMETRY_STATE.update({"sentry_available": False, "sentry_configured": False, "sentry_error": "SENTRY_DSN not configured"})
        return dict(_TELEMETRY_STATE)
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=DEPLOYMENT_ENVIRONMENT,
            release=SERVICE_VERSION,
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
            integrations=[FastApiIntegration(transaction_style="endpoint"), StarletteIntegration(transaction_style="endpoint")],
            send_default_pii=SENTRY_SEND_DEFAULT_PII,
            before_send=sentry_before_send,
            before_breadcrumb=sentry_before_breadcrumb,
        )
        sentry_sdk.set_tag("service.name", SERVICE_NAME)
        sentry_sdk.set_tag("deployment.environment", DEPLOYMENT_ENVIRONMENT)
        _TELEMETRY_STATE.update({"sentry_available": True, "sentry_configured": True, "sentry_error": ""})
    except Exception as exc:
        _TELEMETRY_STATE.update({"sentry_available": False, "sentry_error": str(exc)[:500]})
    return dict(_TELEMETRY_STATE)


def init_opentelemetry(app: Optional[FastAPI] = None) -> Dict[str, Any]:
    if not OTEL_ENABLED:
        _TELEMETRY_STATE.update({"otel_enabled": False, "otel_available": False, "otel_error": "disabled"})
        return dict(_TELEMETRY_STATE)
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

        provider = TracerProvider(
            resource=Resource.create(_resource_attributes()),
            sampler=ParentBased(TraceIdRatioBased(max(0.0, min(1.0, OTEL_SAMPLE_RATE)))),
        )
        exporter_name = "none"
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip() or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
        if endpoint:
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            exporter_name = "otlp_http"
        if OTEL_CONSOLE_EXPORTER_ENABLED:
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
            exporter_name = "console" if exporter_name == "none" else f"{exporter_name}+console"
        trace.set_tracer_provider(provider)
        if app is not None and OTEL_FASTAPI_INSTRUMENTATION_ENABLED:
            FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        if OTEL_REQUESTS_INSTRUMENTATION_ENABLED:
            RequestsInstrumentor().instrument()
        _TELEMETRY_STATE.update({"otel_available": True, "otel_error": "", "otel_trace_exporter": exporter_name})
    except Exception as exc:
        _TELEMETRY_STATE.update({"otel_available": False, "otel_error": str(exc)[:500]})
    return dict(_TELEMETRY_STATE)


def init_telemetry(app: Optional[FastAPI] = None) -> Dict[str, Any]:
    _TELEMETRY_STATE["init_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    init_sentry()
    init_opentelemetry(app)
    _TELEMETRY_STATE["initialized"] = True
    return telemetry_status()


def telemetry_status() -> Dict[str, Any]:
    return {
        **_TELEMETRY_STATE,
        "service": _resource_attributes(),
        "otel": {
            "enabled": OTEL_ENABLED,
            "sample_rate": OTEL_SAMPLE_RATE,
            "console_exporter_enabled": OTEL_CONSOLE_EXPORTER_ENABLED,
            "fastapi_instrumentation_enabled": OTEL_FASTAPI_INSTRUMENTATION_ENABLED,
            "requests_instrumentation_enabled": OTEL_REQUESTS_INSTRUMENTATION_ENABLED,
            "otlp_endpoint_configured": bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "") or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "")),
        },
        "sentry": {
            "enabled": SENTRY_ENABLED,
            "available": _TELEMETRY_STATE.get("sentry_available", False),
            "dsn_configured": bool(SENTRY_DSN),
            "environment": DEPLOYMENT_ENVIRONMENT,
            "send_default_pii": SENTRY_SEND_DEFAULT_PII,
            "scrubber_enabled": True,
            "test_events_enabled": SENTRY_TEST_EVENTS_ENABLED,
            "traces_sample_rate": SENTRY_TRACES_SAMPLE_RATE,
            "profiles_sample_rate": SENTRY_PROFILES_SAMPLE_RATE,
            "last_event_id": _TELEMETRY_STATE.get("sentry_last_event_id", ""),
            "last_test_event_id": _TELEMETRY_STATE.get("sentry_last_test_event_id", ""),
        },
    }


@contextmanager
def traced_span(name: str, **attributes: Any) -> Iterator[Dict[str, Any]]:
    span_id = uuid.uuid4().hex[:12]
    _TELEMETRY_STATE["last_manual_span"] = {"id": span_id, "name": name, "attributes": attributes, "started_at": time.time()}
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer(SERVICE_NAME)
        with tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                try:
                    span.set_attribute(str(key), value if isinstance(value, (str, int, float, bool)) else str(value))
                except Exception:
                    pass
            yield {"span_id": span_id, "otel": True}
    except Exception:
        yield {"span_id": span_id, "otel": False}
    finally:
        if isinstance(_TELEMETRY_STATE.get("last_manual_span"), dict):
            _TELEMETRY_STATE["last_manual_span"]["finished_at"] = time.time()


def capture_exception(exc: Exception, **context: Any) -> str:
    event_id = ""
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in scrub_sensitive(context).items():
                scope.set_extra(str(key), value)
            captured = sentry_sdk.capture_exception(exc)
            event_id = str(captured or "")
            _TELEMETRY_STATE["sentry_last_event_id"] = event_id
    except Exception as sentry_exc:
        _TELEMETRY_STATE["sentry_error"] = str(sentry_exc)[:500]
    return event_id


def capture_message(message: str, level: str = "info", **context: Any) -> str:
    event_id = ""
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in scrub_sensitive(context).items():
                scope.set_extra(str(key), value)
            captured = sentry_sdk.capture_message(message[:500], level=level)
            event_id = str(captured or "")
            _TELEMETRY_STATE["sentry_last_event_id"] = event_id
    except Exception as sentry_exc:
        _TELEMETRY_STATE["sentry_error"] = str(sentry_exc)[:500]
    return event_id


def _extract_admin_key(request: Request, payload: Dict[str, Any] | None = None) -> str:
    payload = payload or {}
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return str(payload.get("admin_key") or payload.get("api_key") or request.query_params.get("admin_key") or request.headers.get("x-admin-key") or request.headers.get("x-api-key") or "")


def register_telemetry_routes(app: FastAPI) -> None:
    @app.get("/telemetry/status")
    def public_telemetry_status():
        return JSONResponse({"ok": True, "telemetry": telemetry_status()})

    @app.get("/api/telemetry/status")
    def api_telemetry_status():
        return JSONResponse({"ok": True, "telemetry": telemetry_status()})

    @app.post("/api/telemetry/test-span")
    def api_telemetry_test_span():
        with traced_span("claimradar.test_span", route="/api/telemetry/test-span") as span:
            return JSONResponse({"ok": True, "span": span, "telemetry": telemetry_status()})


def register_sentry_routes(app: FastAPI, can_admin: Callable[[str], bool]) -> None:
    @app.get("/sentry/status")
    def public_sentry_status():
        return JSONResponse({"ok": True, "sentry": telemetry_status()["sentry"]})

    @app.get("/api/sentry/status")
    def api_sentry_status():
        return JSONResponse({"ok": True, "sentry": telemetry_status()["sentry"]})

    @app.post("/api/sentry/test-event")
    async def api_sentry_test_event(request: Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not can_admin(_extract_admin_key(request, payload)):
            return JSONResponse({"ok": False, "error": "admin_required"}, status_code=403)
        if not SENTRY_TEST_EVENTS_ENABLED:
            return JSONResponse({"ok": False, "error": "sentry_test_events_disabled"}, status_code=403)
        event_id = capture_message(
            str(payload.get("message") or "ClaimRadar BG Sentry test event"),
            level=str(payload.get("level") or "info"),
            test=True,
            route="/api/sentry/test-event",
            payload_preview=scrub_sensitive(payload),
        )
        _TELEMETRY_STATE["sentry_last_test_event_id"] = event_id
        return JSONResponse({"ok": True, "event_id": event_id, "sentry": telemetry_status()["sentry"]})

    @app.post("/api/sentry/test-error")
    async def api_sentry_test_error(request: Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not can_admin(_extract_admin_key(request, payload)):
            return JSONResponse({"ok": False, "error": "admin_required"}, status_code=403)
        if not SENTRY_TEST_EVENTS_ENABLED:
            return JSONResponse({"ok": False, "error": "sentry_test_events_disabled"}, status_code=403)
        try:
            raise RuntimeError(str(payload.get("message") or "ClaimRadar BG controlled Sentry test error"))
        except RuntimeError as exc:
            event_id = capture_exception(exc, route="/api/sentry/test-error", payload_preview=scrub_sensitive(payload), test=True)
            _TELEMETRY_STATE["sentry_last_test_event_id"] = event_id
            return JSONResponse({"ok": True, "captured": True, "event_id": event_id, "sentry": telemetry_status()["sentry"]})
