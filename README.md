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

Hugging Face-ready Docker приложение за България с Gradio UI, FastAPI, realtime WebSocket, AI verdict, Search API слой, browser extension, public result pages, moderation console, evidence quality scoring, Markdown/PDF exports, admin dashboard, custom domain support, auth/admin roles, legal/methodology pages, monitoring/logging, automated tests, real load testing, advanced rate limiting, enhanced background jobs и persistent PostgreSQL/Supabase storage.

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

## Версия 3.8 — Moderation Actions

Добавено:

- `moderation_actions.py`;
- `moderation_console.py`;
- `/admin/moderation` — protected moderation console;
- `/api/admin/moderation` — moderation JSON bundle;
- `POST /api/moderation/check/<check_id>/hide`;
- `POST /api/moderation/check/<check_id>/restore`;
- `POST /api/moderation/check/<check_id>/note`;
- `GET /api/moderation/check/<check_id>/notes`;
- `GET /api/moderation/check/<check_id>/status`;
- `POST /api/moderation/abuse/<report_id>/review`;
- `GET /api/moderation/abuse/<report_id>/status`;
- `GET /api/moderation/actions`;
- JSONL audit trail в `data/moderation_actions.jsonl`;
- moderator notes в `data/moderator_notes.jsonl`;
- report status events в `data/abuse_status.jsonl`;
- tests за hide/restore, notes, report review, moderator key и console access.

Moderation workflow:

```text
reported → under_review → reviewed / dismissed / action_taken
public check → hide/private → restore/public
check → moderator notes → export PDF/Markdown
```

Достъп:

```text
/admin/moderation?admin_key=YOUR_ADMIN_KEY
```

Примери:

```bash
curl -X POST https://claimradar.dyrakarmy.eu/api/moderation/check/<check_id>/hide \
  -H "Content-Type: application/json" \
  -d '{"admin_key":"YOUR_ADMIN_KEY","reason":"privacy review"}'

curl -X POST https://claimradar.dyrakarmy.eu/api/moderation/abuse/<report_id>/review \
  -H "Content-Type: application/json" \
  -d '{"admin_key":"YOUR_ADMIN_KEY","status":"reviewed","note":"checked"}'
```

## Версия 3.7 — Evidence Quality Scoring + Exports

Добавено:

- `evidence_export.py`;
- evidence quality scoring за всеки evidence/source;
- JSON evidence bundle: `/api/export/check/<check_id>`;
- Markdown export: `/export/check/<check_id>.md`;
- PDF export: `/export/check/<check_id>.pdf`;
- privacy protection за private checks — export изисква admin/owner ключ;
- `reportlab==4.2.5` за PDF export;
- `fonts-dejavu-core` в Dockerfile за кирилица в PDF.

## Версия 3.6 — Admin Dashboard

- `admin_dashboard.py`;
- `/admin`;
- `/api/admin/status`;
- `/api/admin/system`;
- `/api/admin/abuse-reports`;
- `/api/admin/recent-checks`;
- `/api/admin/logs`.

## Версия 3.5 — Custom Domain Support

```text
claimradar.dyrakarmy.eu CNAME hf.space
```

## Версия 3.4 — Real Load Testing

- `scripts/load_test.py`;
- `.github/workflows/load-test.yml`;
- `docs/LOAD_TESTING_BG.md`.

## Версия 3.3 — Auth и Admin Roles

- роли: `anonymous`, `viewer`, `moderator`, `admin`, `owner`;
- `/auth/status`, `/api/auth/whoami`, `/api/auth/roles`, `/api/auth/check`.

## Версия 3.2 — Advanced Rate Limiting

- per-scope rate limits;
- temporary ban;
- admin bypass;
- `/rate-limit/status`, `/api/rate-limit/status`, `/api/rate-limit/reset`.

## Версия 3.1 — Enhanced Background Jobs

- `/jobs` dashboard;
- `/api/jobs`, `/api/jobs/stats`, `/api/jobs/<job_id>`;
- check / ai-verdict / real-check jobs;
- cancel/retry/cleanup.

## Версия 3.0 — Automated Tests

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest
```

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
```

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
