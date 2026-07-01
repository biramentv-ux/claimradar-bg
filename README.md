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

Финална Hugging Face-ready версия за България: Docker Space с Gradio интерфейс, публичен архив, browser extension, word-by-word realtime WebSocket backend, AI verdict engine, Search API слой, публични result pages, privacy controls, social metadata и продуктова информационна страница.

## Основни публични страници

```text
https://dyrakarmy-claimradar-bg.hf.space
https://dyrakarmy-claimradar-bg.hf.space/product
https://dyrakarmy-claimradar-bg.hf.space/health
https://dyrakarmy-claimradar-bg.hf.space/search/status
https://dyrakarmy-claimradar-bg.hf.space/sources/whitelist
https://dyrakarmy-claimradar-bg.hf.space/social-preview.svg
https://dyrakarmy-claimradar-bg.hf.space/check/<share_id>
https://dyrakarmy-claimradar-bg.hf.space/api/check/<share_id>
```

## Версия 2.5 — Privacy, Metadata, Social Preview, Abuse Reports

Добавено:

- public/private visibility слой за запазени проверки;
- admin toggle за `public` / `private` от публичната result page;
- private checks вече връщат 403 публично;
- canonical metadata за `/product` и `/check/<share_id>`;
- Open Graph metadata;
- Twitter card metadata;
- dynamic social preview SVG image чрез `/social-preview.svg`;
- бутон **Report abuse** на публичните result pages;
- endpoint `POST /api/report-abuse`;
- abuse reports се записват в `data/abuse_reports.jsonl` и се дублират към feedback stream;
- endpoint `POST /api/check/<share_id>/visibility` за admin visibility промяна.

## Рапорт

Подробният технически рапорт е в:

```text
PROJECT_REPORT_BG.md
```

## Версия 2.4 — Product Page + Project Report

Добавено:

- route `/product`;
- публична продуктова страница за крайни потребители;
- технически рапорт `PROJECT_REPORT_BG.md`;
- линк към `/product` от публичните result pages.

## Версия 2.3 — Search API + Public Result Pages

Добавено:

- search provider слой в `search_providers.py`;
- Brave Search API;
- Bing Search API;
- Tavily;
- SerpAPI;
- Google Programmable Search / CSE;
- DuckDuckGo fallback;
- whitelist филтър за надеждни източници;
- endpoint `/search/status`;
- endpoint `/sources/whitelist`;
- JSON endpoint `/api/check/<share_id>`;
- публична страница `/check/<share_id>`.

## Search API настройки

```bash
SEARCH_PROVIDER=auto
SEARCH_STRICT_WHITELIST=1
```

Поддържани secrets/variables:

```bash
BRAVE_SEARCH_API_KEY=...
BING_SEARCH_API_KEY=...
TAVILY_API_KEY=...
SERPAPI_API_KEY=...
GOOGLE_SEARCH_API_KEY=...
GOOGLE_CSE_ID=...
```

Whitelist източници:

```text
nsi.bg
bnb.bg
nssi.bg
nra.bg
cik.bg
parliament.bg
dv.parliament.bg
minfin.bg
gov.bg
ec.europa.eu
factcheck.bg
bta.bg
bnr.bg
```

## Версия 2.2 — AI Verdict Engine

Добавено:

- tab **🧠 AI verdict**;
- pipeline: `claim → evidence search → AI сравнение → verdict → цитати`;
- evidence search по надеждни/официални домейни;
- verdict-и: `Вярно`, `По-скоро вярно`, `Частично вярно`, `Подвеждащо`, `Невярно`, `Непроверимо`, `Нужен контекст`;
- цитирани evidence линкове;
- confidence score;
- fallback режим, ако няма `OPENAI_API_KEY`.

## AI настройки

```bash
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4o-mini
```

## Docker Space

Проектът използва **FastAPI + Gradio + WebSocket** в един процес и трябва да е Hugging Face **Docker Space**.

```yaml
sdk: docker
app_port: 7860
```

`Dockerfile` стартира:

```bash
python launch.py
```

## Готово за Hugging Face

След build приложението дава:

- публичен Gradio интерфейс;
- `/product` продуктова страница;
- `/social-preview.svg` social preview image;
- `/health` endpoint;
- `/search/status` endpoint;
- `/sources/whitelist` endpoint;
- `/check/<share_id>` public/private result page;
- `/api/check/<share_id>` JSON result;
- `/api/report-abuse` abuse report endpoint;
- `/ws/realtime` WebSocket endpoint;
- AI verdict + цитати;
- Search API слой;
- word-by-word realtime transcript за extension-а;
- audio/video transcription;
- `.srt` export;
- публичен архив със Share ID;
- feedback и animated admin панел.

## Realtime endpoint

```text
wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime
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
ADMIN_KEY=your-secret-admin-key
```

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
