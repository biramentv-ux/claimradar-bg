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

Hugging Face-ready Docker приложение за България с Gradio UI, FastAPI, realtime WebSocket, AI verdict, Search API слой, OpenTelemetry tracing, Sentry error tracking, CodeQL scanning, production observability, external queue worker, GPU/dedicated inference option, browser extension, public result pages, expanded OWASP security hardening, moderation console, evidence quality scoring, Markdown/PDF exports, admin dashboard, custom domain support, auth/admin roles, legal/methodology pages, monitoring/logging, automated tests, real load testing, advanced rate limiting, enhanced background jobs и persistent PostgreSQL/Supabase storage.

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
/security/owasp/headers
/api/security/owasp/headers
/.well-known/security.txt
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
/robots.txt
/sitemap.xml
```

## Версия 4.6 — Public Launch Fixes

- **Поправен crash на главната страница**: `gradio==5.9.1` гърми с `TypeError` на `/` и `/gradio_api/info` при `pydantic>=2.11`. `requirements.txt` вече пинва `pydantic==2.10.6`, така че свежите Docker build-ове на Space-а рендерират UI-а.
- **`/robots.txt` и `/sitemap.xml`** за публичния домейн: sitemap-ът изброява публичните страници на `PUBLIC_BASE_URL` (по подразбиране `https://claimradar.dyrakarmy.eu`); robots забранява `/admin`, `/api/` и `/monitoring/logs`.
- **`LOCAL_LLM_MODEL`** вече има приоритет пред профила на model manager-а (преди се игнорираше).
- **Тестовете не зависят от реда**: `tests/conftest.py` задава една тестова среда преди collection; rate-limit тестовете включват limiter-а само за себе си.

### Публично пускане (чеклист)

1. Push в `main` → GitHub Action `Deploy Hugging Face Space` качва кода в `DyrakArmy/claimradar-bg` (нужен е secret `HF_TOKEN` с write достъп).
2. SuperHosting DNS: `CNAME claimradar → hf.space` (TTL 3600). Не се насочва към IP.
3. Space Settings → Custom Domain: `claimradar.dyrakarmy.eu` (изисква HF PRO/Team/Enterprise и public/protected Space; статусът минава от `pending` в `ready`, щом CNAME-ът резолвне към `hf.space`). Без PRO сайтът остава достъпен на `https://dyrakarmy-claimradar-bg.hf.space`.
4. Space Variables: `PUBLIC_BASE_URL=https://claimradar.dyrakarmy.eu`, `CUSTOM_DOMAIN`, `ROOT_DOMAIN`, `HF_SPACE_URL`.
5. Space Secrets: `OWNER_KEY`/`ADMIN_KEY`, `AUTH_TOKEN_SALT`, `RATE_LIMIT_HASH_SALT`, по желание `OPENAI_API_KEY`, `DATABASE_URL`, search API ключове.
6. Проверка: `python scripts/check_custom_domain.py` или workflow-а `Custom Domain Check`.

## Версия 4.5 — Expanded OWASP Security Hardening

Добавено:

- разширен `owasp_hardening.py`;
- `/security/owasp/headers`;
- `/api/security/owasp/headers`;
- `/.well-known/security.txt`;
- CSP `frame-ancestors` за Hugging Face App таба;
- optional `Content-Security-Policy-Report-Only`;
- CRLF/header injection block;
- high-confidence XSS/iframe/event-handler probes block;
- high-confidence SQLi `union select` probe block;
- Log4Shell-style `${jndi:...}` probe block;
- `X-XSS-Protection: 0`;
- `X-Permitted-Cross-Domain-Policies: none`;
- `Cross-Origin-Resource-Policy: same-site`;
- `Origin-Agent-Cluster: ?1`;
- `Set-Cookie` hardening with `Secure`, `HttpOnly`, `SameSite=Lax` when missing;
- extra no-store coverage for sentry/telemetry/observability sensitive endpoints;
- expanded tests in `tests/test_owasp_hardening.py`.

Проверка:

```bash
curl https://claimradar.dyrakarmy.eu/api/security/owasp/status
curl https://claimradar.dyrakarmy.eu/api/security/owasp/headers
curl https://claimradar.dyrakarmy.eu/.well-known/security.txt
pytest tests/test_owasp_hardening.py
```

## Версия 4.3 — OpenTelemetry + Sentry + CodeQL

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
OWASP_HARDENING_ENABLED=1
OWASP_COOKIE_HARDENING_ENABLED=1
JOB_EXECUTION_MODE=external
QUEUE_WORKER_AUTOSTART=1
INFERENCE_MODE=auto
WHISPER_DEVICE=auto
WHISPER_CPU_COMPUTE_TYPE=int8
WHISPER_GPU_COMPUTE_TYPE=float16
```

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
