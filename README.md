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

Hugging Face-ready Docker приложение за България с Gradio UI, FastAPI, realtime WebSocket, AI verdict, Search API слой, browser extension, public result pages, OWASP security hardening, moderation console, evidence quality scoring, Markdown/PDF exports, admin dashboard, custom domain support, auth/admin roles, legal/methodology pages, monitoring/logging, automated tests, real load testing, advanced rate limiting, enhanced background jobs и persistent PostgreSQL/Supabase storage.

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

## Версия 3.9 — OWASP Security Hardening

Добавено:

- `owasp_hardening.py`;
- `docs/SECURITY_HARDENING_BG.md`;
- `OWASPHardeningMiddleware` в `auth_launch.py`;
- `/security/owasp/status`;
- `/api/security/owasp/status`;
- tests в `tests/test_owasp_hardening.py`;
- CI compile check за `owasp_hardening.py`.

Runtime защити:

```text
блокира TRACE / TRACK / CONNECT
блокира path traversal, null byte, /etc/passwd, /proc/self, <script>, javascript:
лимитира path/query дължина
опционален host allowlist
изисква JSON-compatible Content-Type за API write requests
добавя CSP, HSTS, no-sniff, Referrer-Policy, Permissions-Policy, COOP, X-DNS-Prefetch-Control
no-store cache policy за admin/auth/moderation/db sensitive endpoints
```

OWASP mapping:

```text
API1 BOLA → private checks/exports require admin/owner
API2 Auth → role-aware keys and Bearer token support
API3 BOPLA → shaped export bundles and protected private objects
API4 Resource Consumption → rate limits, size guards, job caps, path/query caps
API5 BFLA → admin/moderator function-level authorization
API6 Business Flows → jobs/moderation/abuse actions are limited and audited
API7 SSRF → suspicious URI payload block + search source whitelist
API8 Misconfiguration → security headers and method/content-type hardening
API9 Inventory → documented route inventory and status endpoints
API10 Unsafe API Consumption → evidence scoring and fallback behavior
```

Variables:

```bash
OWASP_HARDENING_ENABLED=1
OWASP_BLOCK_SUSPICIOUS_INPUTS=1
OWASP_REQUIRE_JSON_API_POSTS=1
OWASP_CSP_ENABLED=1
OWASP_HSTS_ENABLED=1
OWASP_HSTS_MAX_AGE=31536000
OWASP_MAX_QUERY_LENGTH=4096
OWASP_MAX_PATH_LENGTH=2048
OWASP_ALLOWED_HOSTS=claimradar.dyrakarmy.eu,dyrakarmy-claimradar-bg.hf.space
```

Проверка:

```bash
curl https://claimradar.dyrakarmy.eu/api/security/owasp/status
curl -I https://claimradar.dyrakarmy.eu/product
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
- `GET /api/moderation/actions`.

## Версия 3.7 — Evidence Quality Scoring + Exports

- `evidence_export.py`;
- evidence quality scoring;
- `/api/export/check/<check_id>`;
- `/export/check/<check_id>.md`;
- `/export/check/<check_id>.pdf`.

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
