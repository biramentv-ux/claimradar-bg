from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from fastapi import FastAPI
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
    "last_manual_span": None,
    "init_ts": None,
}


def _resource_attributes() -> Dict[str, str]:
    return {
        "service.name": SERVICE_NAME,
        "service.version": SERVICE_VERSION,
        "deployment.environment": DEPLOYMENT_ENVIRONMENT,
    }


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
            integrations=[FastApiIntegration(), StarletteIntegration()],
            send_default_pii=False,
        )
        sentry_sdk.set_tag("service.name", SERVICE_NAME)
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
            "dsn_configured": bool(SENTRY_DSN),
            "environment": DEPLOYMENT_ENVIRONMENT,
            "traces_sample_rate": SENTRY_TRACES_SAMPLE_RATE,
            "profiles_sample_rate": SENTRY_PROFILES_SAMPLE_RATE,
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
            for key, value in context.items():
                scope.set_extra(str(key), value)
            captured = sentry_sdk.capture_exception(exc)
            event_id = str(captured or "")
    except Exception as sentry_exc:
        _TELEMETRY_STATE["sentry_error"] = str(sentry_exc)[:500]
    return event_id


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
