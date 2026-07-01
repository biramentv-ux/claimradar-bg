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

Hugging Face-ready Docker приложение за България с Gradio UI, FastAPI, realtime WebSocket, AI verdict, Search API слой, browser extension, public result pages, legal/methodology pages, monitoring/logging, security/rate limiting, background jobs и persistent PostgreSQL/Supabase storage.

## Основни публични страници

```text
/
/product
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
/check/<share_id>
/api/check/<share_id>
```

## Версия 2.9 — Monitoring и Logging

Добавено:

- `monitoring.py`;
- request logging middleware;
- `X-Request-ID` response header;
- `X-ClaimRadar-Monitoring` response header;
- latency metrics;
- status code counters;
- method counters;
- top path counters;
- recent request buffer;
- recent error buffer;
- JSONL event log в `data/system_events.jsonl`;
- `/monitoring/status`;
- `/monitoring/metrics`;
- admin-protected `/monitoring/logs`;
- admin-protected `POST /api/monitoring/event`.

### Monitoring variables

```bash
MONITORING_ENABLED=1
REQUEST_LOG_ENABLED=1
REQUEST_LOG_BODY=0
MONITORING_RECENT_LIMIT=200
MONITORING_SLOW_MS=2500
MONITORING_LOG_FILE=data/system_events.jsonl
```

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

## Версия 2.6 — Security и Background Jobs

Добавено:

- `security_jobs.py`;
- rate limiting middleware;
- security headers;
- request size guard;
- background job store;
- `/security/status`;
- `/api/jobs/*`.

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

## Hugging Face Variables

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
SEARCH_PROVIDER=auto
SEARCH_STRICT_WHITELIST=1
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
MONITORING_ENABLED=1
REQUEST_LOG_ENABLED=1
REQUEST_LOG_BODY=0
MONITORING_RECENT_LIMIT=200
MONITORING_SLOW_MS=2500
MONITORING_LOG_FILE=data/system_events.jsonl
ADMIN_KEY=your-secret-admin-key
DB_ENABLED=1
DB_SSLMODE=require
```

## Рапорт

Подробният технически рапорт е в:

```text
PROJECT_REPORT_BG.md
```

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
