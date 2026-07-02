---
title: BG Fact Checker
emoji: 🔎
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# ClaimRadar BG

Hugging Face-ready Docker приложение за България с Gradio UI, FastAPI, realtime WebSocket, AI verdict, Search API слой, OpenTelemetry tracing, Sentry error tracking, CodeQL scanning, production observability, external queue worker, GPU/dedicated inference option, browser extension, public result pages, OWASP security hardening, moderation console, evidence quality scoring, Markdown/PDF exports, admin dashboard, custom domain support, auth/admin roles, legal/methodology pages, monitoring/logging, automated tests, real load testing, advanced rate limiting, enhanced background jobs и persistent PostgreSQL/Supabase storage.

## Основни публични страници и endpoints

```text
/
/product
/admin
/admin/moderation
/api/admin/moderation
/api/admin/status
/api/admin/system
/api/admin/abuse-reports
/api/admin/recent-checks
/api/admin/logs
/sentry/status
/api/sentry/status
/api/sentry/test-event
/api/sentry/test-error
/telemetry/status
/api/telemetry/status
/api/telemetry/test-span
/observability
/observability/status
/api/observability/summary
/api/observability/providers
/api/observability/costs
/api/observability/ai-usage
/metrics
/queue/status
/api/queue/status
/inference/status
/api/inference/status
/api/inference/recommendation
/security/owasp/status
/api/security/owasp/status
/api/moderation/actions
/api/moderation/check/<check_id>/hide
/api/moderation/check/<check_id>/restore
/api/moderation/check/<check_id>/note
/api/moderation/check/<check_id>/notes
/api/moderation/check/<check_id>/status
/api/moderation/abuse/<report_id>/review
/api/moderation/abuse/<report_id>/status
/api/export/check/<check_id>
/export/check/<check_id>.md
/export/check/<check_id>.pdf
/jobs
/custom-domain
/domain
/custom-domain/status
/domain/status
/api/custom-domain/status
/auth/status
/api/auth/status
/api/auth/whoami
/api/auth/roles
/api/auth/check
/about
/methodology
/privacy
/terms
/sources
/contact
/legal-methodology.md
/health
/db/status
/rate-limit/status
/api/rate-limit/status
/api/rate-limit/reset
/monitoring/status
/monitoring/metrics
/monitoring/logs?admin_key=...
/api/monitoring/event
/api/db/status
/api/db/schema
/security/status
/search/status
/sources/whitelist
/social-preview.svg
/api/jobs
/api/jobs/stats
/api/jobs/<job_id>
/api/jobs/<job_id>/cancel
/api/jobs/<job_id>/retry
/api/jobs/cleanup
/check/<share_id>
/api/check/<share_id>
```

## Версия 4.3 — OpenTelemetry + Sentry + CodeQL

Добавено:

- `telemetry_integrations.py`;
- `docs/TELEMETRY_SENTRY_CODEQL_BG.md`;
- `.github/workflows/codeql.yml`;
- `/sentry/status`;
- `/api/sentry/status`;
- protected `POST /api/sentry/test-event`;
- protected `POST /api/sentry/test-error`;
- `/telemetry/status`;
- `/api/telemetry/status`;
- `/api/telemetry/test-span`;
- OpenTelemetry FastAPI instrumentation;
- OpenTelemetry requests instrumentation;
- optional OTLP HTTP exporter;
- Sentry FastAPI integration;
- Sentry message/error capture helpers;
- Sentry event/breadcrumb scrubber за sensitive keys;
- `send_default_pii=False` by default;
- manual `traced_span(...)` helper;
- `capture_exception(...)` helper;
- `capture_message(...)` helper;
- CodeQL workflow with `security-extended` and `security-and-quality` queries;
- tests в `tests/test_telemetry_integrations.py`;
- CI compile check за `telemetry_integrations.py`.

Variables:

```bash
OTEL_ENABLED=1
OTEL_SERVICE_NAME=claimradar-bg
OTEL_SAMPLE_RATE=1.0
OTEL_FASTAPI_INSTRUMENTATION_ENABLED=1
OTEL_REQUESTS_INSTRUMENTATION_ENABLED=1
OTEL_EXPORTER_OTLP_ENDPOINT=https://YOUR-OTEL-COLLECTOR/v1/traces
OTEL_CONSOLE_EXPORTER_ENABLED=0
SENTRY_ENABLED=1
SENTRY_ENVIRONMENT=production
SENTRY_SEND_DEFAULT_PII=0
SENTRY_TEST_EVENTS_ENABLED=1
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0
```

Проверка:

```bash
curl https://claimradar.dyrakarmy.eu/api/sentry/status
curl -X POST https://claimradar.dyrakarmy.eu/api/sentry/test-event
curl -X POST https://claimradar.dyrakarmy.eu/api/telemetry/test-span
```

## Версия 4.2 — Production Observability

- `production_observability.py`;
- `docs/PRODUCTION_OBSERVABILITY_BG.md`;
- `/observability` dashboard;
- `/observability/status` SLO status;
- `/api/observability/summary`;
- `/api/observability/providers`;
- `/api/observability/costs`;
- protected `POST /api/observability/ai-usage`;
- Prometheus-compatible `/metrics`.

## Версия 4.1 — External Queue Worker

- `external_queue.py`;
- `queue_worker.py`;
- `scripts/start_production.sh`;
- `docs/EXTERNAL_QUEUE_WORKER_BG.md`;
- `/queue/status`;
- `/api/queue/status`;
- `JOB_EXECUTION_MODE=external` mode.

## Версия 4.0 — GPU / Dedicated Inference

- `hardware_inference.py`;
- `docs/GPU_DEDICATED_INFERENCE_BG.md`;
- runtime auto избор `cpu` / `cuda`;
- safe fallback от GPU към CPU;
- dedicated transcription endpoint offload;
- `/inference/status`;
- `/api/inference/status`;
- `/api/inference/recommendation`.

## Версия 3.9 — OWASP Security Hardening

- `owasp_hardening.py`;
- `docs/SECURITY_HARDENING_BG.md`;
- `/security/owasp/status`;
- `/api/security/owasp/status`.

## Основни variables

```bash
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/postgres?sslmode=require
DB_ENABLED=1
ADMIN_KEY=...
OWNER_KEY=...
MODERATOR_KEY=...
VIEWER_KEY=...
AUTH_TOKEN_SALT=random-long-string
RATE_LIMIT_HASH_SALT=random-long-string
PUBLIC_BASE_URL=https://claimradar.dyrakarmy.eu
CUSTOM_DOMAIN=claimradar.dyrakarmy.eu
EXPORT_MAX_ITEMS=40
OBSERVABILITY_ENABLED=1
OTEL_ENABLED=1
SENTRY_ENABLED=1
JOB_EXECUTION_MODE=external
QUEUE_WORKER_AUTOSTART=1
INFERENCE_MODE=auto
WHISPER_DEVICE=auto
WHISPER_CPU_COMPUTE_TYPE=int8
WHISPER_GPU_COMPUTE_TYPE=float16
```

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
