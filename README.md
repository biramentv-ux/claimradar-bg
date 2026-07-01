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

Hugging Face-ready Docker приложение за България с Gradio UI, FastAPI, realtime WebSocket, AI verdict, Search API слой, browser extension, public result pages, auth/admin roles, legal/methodology pages, monitoring/logging, automated tests, advanced rate limiting, enhanced background jobs и persistent PostgreSQL/Supabase storage.

## Основни публични страници

```text
/
/product
/jobs
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

## Версия 3.3 — Auth и Admin Roles

Добавено:

- `auth_roles.py`;
- `auth_launch.py`;
- Dockerfile стартира `auth_launch.py`;
- роли: `anonymous`, `viewer`, `moderator`, `admin`, `owner`;
- permission map за роли;
- support за `Authorization: Bearer`, `x-api-key`, `x-admin-key`, `x-claimradar-admin-key` и query token;
- `/auth/status`;
- `/api/auth/status`;
- `/api/auth/whoami`;
- `/api/auth/roles`;
- `POST /api/auth/check`;
- съвместимост със стария `ADMIN_KEY`;
- route shadowing за jobs/rate-limit/db admin actions през новия auth wrapper;
- smoke tests за roles, whoami и auth check.

### Auth variables

```bash
AUTH_ENABLED=1
AUTH_TOKEN_SALT=random-long-string
OWNER_KEY=...
ADMIN_KEY=...
MODERATOR_KEY=...
VIEWER_KEY=...
```

### Advanced auth map

`AUTH_KEYS_JSON` позволява няколко ключа с различни роли:

```json
{
  "main-admin": {"role": "admin", "key": "..."},
  "factcheck-editor": {"role": "moderator", "key": "..."},
  "readonly-user": {"role": "viewer", "key": "..."}
}
```

## Версия 3.2 — Advanced Rate Limiting

Добавено:

- per-scope rate limits;
- hashed client identity;
- `X-RateLimit-Limit`;
- `X-RateLimit-Remaining`;
- `X-RateLimit-Reset`;
- `X-RateLimit-Scope`;
- `Retry-After` при 429;
- temporary ban;
- admin bypass;
- `/rate-limit/status`;
- `/api/rate-limit/status`;
- admin-protected `POST /api/rate-limit/reset`.

## Версия 3.1 — Enhanced Background Jobs

Добавено:

- `jobs_api.py`;
- `/jobs` public jobs dashboard;
- `/api/jobs?status=&type=&limit=` filtered job list;
- `/api/jobs/stats`;
- `/api/jobs/<job_id>`;
- `POST /api/jobs/check`;
- `POST /api/jobs/ai-verdict`;
- `POST /api/jobs/real-check`;
- `POST /api/jobs/<job_id>/cancel`;
- `POST /api/jobs/<job_id>/retry`;
- `POST /api/jobs/cleanup`;
- job lifecycle events;
- `queued`, `running`, `done`, `failed`, `cancelled` statuses.

## Версия 3.0 — Automated Tests

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest
```

## Версия 2.9 — Monitoring и Logging

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

- `/about`;
- `/methodology`;
- `/privacy`;
- `/terms`;
- `/sources`;
- `/contact`;
- `/legal-methodology.md`;
- `LEGAL_METHODOLOGY_BG.md`.

## Версия 2.7 — Supabase/PostgreSQL Persistent Storage

- `supabase/schema.sql`;
- `db_storage.py`;
- `persistent_launch.py`;
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
SECURITY_HEADERS_ENABLED=1
MAX_REQUEST_BYTES=26214400
RATE_LIMIT_ENABLED=1
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_PUBLIC=180
RATE_LIMIT_API=60
RATE_LIMIT_JOBS=20
RATE_LIMIT_WS=20
RATE_LIMIT_SEARCH=45
RATE_LIMIT_ADMIN=30
RATE_LIMIT_ABUSE=6
RATE_LIMIT_STATUS=60
RATE_LIMIT_BAN_THRESHOLD=8
RATE_LIMIT_BAN_SECONDS=300
RATE_LIMIT_ADMIN_BYPASS=1
RATE_LIMIT_HASH_SALT=random-long-string
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
OPENAI_API_KEY=...
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
