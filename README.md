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

Hugging Face-ready Docker приложение за България с Gradio UI, FastAPI, realtime WebSocket, AI verdict, Search API слой, GPU/dedicated inference option, browser extension, public result pages, OWASP security hardening, moderation console, evidence quality scoring, Markdown/PDF exports, admin dashboard, custom domain support, auth/admin roles, legal/methodology pages, monitoring/logging, automated tests, real load testing, advanced rate limiting, enhanced background jobs и persistent PostgreSQL/Supabase storage.

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

## Версия 4.0 — GPU / Dedicated Inference

Добавено:

- `hardware_inference.py`;
- `docs/GPU_DEDICATED_INFERENCE_BG.md`;
- runtime auto избор `cpu` / `cuda`;
- safe fallback от GPU към CPU;
- dedicated transcription endpoint offload;
- `/inference/status`;
- `/api/inference/status`;
- `/api/inference/recommendation`;
- tests в `tests/test_hardware_inference.py`;
- CI compile check за `hardware_inference.py`.

Препоръчителни variables:

```bash
INFERENCE_MODE=auto
INFERENCE_AUTO_GPU=1
WHISPER_DEVICE=auto
WHISPER_MODEL_SIZE=base
WHISPER_CPU_COMPUTE_TYPE=int8
WHISPER_GPU_COMPUTE_TYPE=float16
WHISPER_GPU_FALLBACK_CPU=1
```

Dedicated endpoint:

```bash
INFERENCE_MODE=dedicated
DEDICATED_INFERENCE_ENABLED=1
DEDICATED_TRANSCRIBE_URL=https://YOUR-ENDPOINT/transcribe
DEDICATED_INFERENCE_TOKEN=...
DEDICATED_TRANSCRIBE_TIMEOUT=180
DEDICATED_FALLBACK_LOCAL=1
```

Проверка:

```bash
curl https://claimradar.dyrakarmy.eu/api/inference/status
curl https://claimradar.dyrakarmy.eu/api/inference/recommendation
```

## Версия 3.9 — OWASP Security Hardening

- `owasp_hardening.py`;
- `docs/SECURITY_HARDENING_BG.md`;
- `/security/owasp/status`;
- `/api/security/owasp/status`.

## Версия 3.8 — Moderation Actions

- `moderation_actions.py`;
- `moderation_console.py`;
- `/admin/moderation`;
- `/api/admin/moderation`;
- hide/restore checks;
- moderator notes;
- abuse report review.

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
INFERENCE_MODE=auto
WHISPER_DEVICE=auto
WHISPER_CPU_COMPUTE_TYPE=int8
WHISPER_GPU_COMPUTE_TYPE=float16
```

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
