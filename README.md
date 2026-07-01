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

Hugging Face-ready Docker приложение за България с Gradio UI, FastAPI, realtime WebSocket, AI verdict, Search API слой, browser extension, public result pages, legal/methodology pages, monitoring/logging, automated tests, security/rate limiting, enhanced background jobs и persistent PostgreSQL/Supabase storage.

## Основни публични страници

```text
/
/product
/jobs
/about
/methodology
/privacy
/terms
/sources
/contact
/legal-methodology.md
/health
/db/status
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

## Версия 3.1 — Enhanced Background Jobs

Добавено:

- `jobs_api.py` — reusable FastAPI job routes;
- `/jobs` — public jobs dashboard;
- `/api/jobs?status=&type=&limit=` — filtered job list;
- `/api/jobs/stats` — status/type counters, duration metrics и worker info;
- `/api/jobs/<job_id>` — детайлен job status;
- `POST /api/jobs/check`;
- `POST /api/jobs/ai-verdict`;
- `POST /api/jobs/real-check`;
- `POST /api/jobs/<job_id>/cancel` — admin-protected cancel request;
- `POST /api/jobs/<job_id>/retry` — admin-protected retry;
- `POST /api/jobs/cleanup` — admin-protected cleanup на стари terminal jobs;
- job lifecycle events;
- `queued`, `running`, `done`, `failed`, `cancelled` statuses;
- `started_at`, `finished_at`, `duration_seconds`, `attempt`, `parent_id`;
- result trimming чрез `JOB_RESULT_MAX_CHARS`;
- tests за job dashboard, stats, create/get/cancel/retry/cleanup.

### Job examples

```bash
curl -X POST https://dyrakarmy-claimradar-bg.hf.space/api/jobs/check \
  -H "Content-Type: application/json" \
  -d '{"text":"Инфлацията в България е 10 процента през 2024 година."}'
```

```bash
curl https://dyrakarmy-claimradar-bg.hf.space/api/jobs/<job_id>
```

```bash
curl -X POST https://dyrakarmy-claimradar-bg.hf.space/api/jobs/<job_id>/cancel \
  -H "Content-Type: application/json" \
  -d '{"admin_key":"YOUR_ADMIN_KEY","reason":"manual cancel"}'
```

```bash
curl -X POST https://dyrakarmy-claimradar-bg.hf.space/api/jobs/<job_id>/retry \
  -H "Content-Type: application/json" \
  -d '{"admin_key":"YOUR_ADMIN_KEY"}'
```

## Версия 3.0 — Automated Tests

Добавено:

- `requirements-dev.txt`;
- `pytest.ini`;
- `tests/test_static_contracts.py`;
- `tests/test_packaging.py`;
- `tests/test_storage_and_monitoring.py`;
- `tests/test_public_endpoints.py`;
- `.github/workflows/tests.yml`.

Локално:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest
```

## Версия 2.9 — Monitoring и Logging

Добавено:

- `monitoring.py`;
- request logging middleware;
- `X-Request-ID` response header;
- latency/status metrics;
- JSONL event log в `data/system_events.jsonl`;
- `/monitoring/status`;
- `/monitoring/metrics`;
- admin-protected `/monitoring/logs`;
- admin-protected `POST /api/monitoring/event`.

## Версия 2.8 — Legal и Methodology Pages

Добавено:

- `/about`;
- `/methodology`;
- `/privacy`;
- `/terms`;
- `/sources`;
- `/contact`;
- `/legal-methodology.md`;
- `LEGAL_METHODOLOGY_BG.md`.

## Версия 2.7 — Supabase/PostgreSQL Persistent Storage

Добавено:

- `supabase/schema.sql`;
- `db_storage.py`;
- `persistent_launch.py`;
- Dockerfile стартира `persistent_launch.py`;
- `psycopg[binary]`;
- `/db/status` и `/api/db/status`;
- `/api/db/schema`;
- `POST /api/db/migrate-jsonl`;
- JSONL остава backup/fallback, ако базата не е конфигурирана.

## Database variables

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/postgres?sslmode=require
SUPABASE_DB_URL=...
POSTGRES_URL=...
DB_ENABLED=1
DB_SSLMODE=require
```

## Security / Jobs / Monitoring Variables

```bash
RATE_LIMIT_ENABLED=1
SECURITY_HEADERS_ENABLED=1
MAX_REQUEST_BYTES=26214400
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_DEFAULT=120
RATE_LIMIT_API=60
RATE_LIMIT_HEAVY=12
RATE_LIMIT_ABUSE=6
JOB_WORKERS=2
JOB_MAX_TEXT_CHARS=12000
JOB_RETENTION=500
JOB_RESULT_MAX_CHARS=50000
MONITORING_ENABLED=1
REQUEST_LOG_ENABLED=1
REQUEST_LOG_BODY=0
MONITORING_RECENT_LIMIT=200
MONITORING_SLOW_MS=2500
MONITORING_LOG_FILE=data/system_events.jsonl
ADMIN_KEY=your-secret-admin-key
```

## Search API настройки

```bash
SEARCH_PROVIDER=auto
SEARCH_STRICT_WHITELIST=1
BRAVE_SEARCH_API_KEY=...
BING_SEARCH_API_KEY=...
TAVILY_API_KEY=...
SERPAPI_API_KEY=...
GOOGLE_SEARCH_API_KEY=...
GOOGLE_CSE_ID=...
```

## AI настройки

```bash
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4o-mini
```

## Hugging Face базови Variables

```bash
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
MAX_MEDIA_MB=80
REALTIME_INTERVAL=2.5
ROLLING_WINDOW_MB=12
STREAM_MAX_BUFFER_MB=60
STREAM_LANGUAGE=bg
PUBLIC_BASE_URL=https://dyrakarmy-claimradar-bg.hf.space
```

## Рапорт

Подробният технически рапорт е в:

```text
PROJECT_REPORT_BG.md
```

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
