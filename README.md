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

Финална Hugging Face-ready версия за България: Docker Space с Gradio интерфейс, публичен архив, browser extension, word-by-word realtime WebSocket backend, AI verdict engine, Search API слой, публични result pages и продуктова информационна страница.

## Основни публични страници

```text
https://dyrakarmy-claimradar-bg.hf.space
https://dyrakarmy-claimradar-bg.hf.space/product
https://dyrakarmy-claimradar-bg.hf.space/health
https://dyrakarmy-claimradar-bg.hf.space/search/status
https://dyrakarmy-claimradar-bg.hf.space/sources/whitelist
https://dyrakarmy-claimradar-bg.hf.space/check/<share_id>
https://dyrakarmy-claimradar-bg.hf.space/api/check/<share_id>
```

## Рапорт

Подробният технически рапорт е в:

```text
PROJECT_REPORT_BG.md
```

Той описва:

- общата архитектура;
- Gradio UI;
- FastAPI backend;
- Hugging Face Docker deployment;
- GitHub Actions sync;
- AI verdict engine;
- Search API layer;
- публичен архив;
- browser extension;
- admin панел;
- environment variables;
- ограничения;
- препоръчани следващи стъпки за production миграция.

## Версия 2.4 — Product Page + Project Report

Добавено:

- route `/product`;
- публична продуктова страница за крайни потребители;
- технически рапорт `PROJECT_REPORT_BG.md`;
- линк към `/product` от публичните result pages;
- обновен public layer version: `2.4-product-page`.

Продуктовата страница обяснява:

- какво е ClaimRadar BG;
- за кого е предназначен;
- как работи;
- какви режими има;
- какво означават verdict-ите;
- какви източници използва;
- какво е публичен архив;
- какви са ограниченията;
- какви са следващите production стъпки.

## Версия 2.3 — Search API + Public Result Pages

Добавено:

- нов search provider слой в `search_providers.py`;
- поддръжка на:
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
- истинска публична страница `/check/<share_id>`.

## Search API настройки

По подразбиране системата работи с:

```bash
SEARCH_PROVIDER=auto
SEARCH_STRICT_WHITELIST=1
```

`auto` използва наличния API provider според зададените secrets и пада обратно към DuckDuckGo.

Поддържани secrets/variables:

```bash
BRAVE_SEARCH_API_KEY=...
BING_SEARCH_API_KEY=...
TAVILY_API_KEY=...
SERPAPI_API_KEY=...
GOOGLE_SEARCH_API_KEY=...
GOOGLE_CSE_ID=...
```

Можеш да форсираш конкретен provider:

```bash
SEARCH_PROVIDER=brave
SEARCH_PROVIDER=bing
SEARCH_PROVIDER=tavily
SEARCH_PROVIDER=serpapi
SEARCH_PROVIDER=google_cse
SEARCH_PROVIDER=duckduckgo
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
- AI verdict-и:
  - `Вярно`
  - `По-скоро вярно`
  - `Частично вярно`
  - `Подвеждащо`
  - `Невярно`
  - `Непроверимо`
  - `Нужен контекст`
- цитирани evidence линкове с номера `[1]`, `[2]`, `[3]`;
- confidence score;
- missing context поле;
- fallback режим, ако няма `OPENAI_API_KEY`;
- admin индикатор дали AI engine е активен.

## AI настройки

За истински AI verdict добави в Hugging Face → Settings → Variables and secrets:

```bash
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4o-mini
```

Ако `OPENAI_API_KEY` липсва, приложението не пада. Работи в rule-based fallback режим и пак показва evidence/citations.

## Docker Space

Проектът използва **FastAPI + Gradio + WebSocket** в един процес и трябва да е Hugging Face **Docker Space**.

Metadata:

```yaml
sdk: docker
app_port: 7860
```

`Dockerfile` стартира:

```bash
python launch.py
```

на порт `7860`.

## Готово за Hugging Face

След build приложението дава:

- публичен Gradio интерфейс;
- `/product` продуктова страница;
- `/health` endpoint;
- `/search/status` endpoint;
- `/sources/whitelist` endpoint;
- `/check/<share_id>` public result page;
- `/api/check/<share_id>` JSON result;
- `/ws/realtime` WebSocket endpoint;
- AI verdict + цитати;
- по-надежден Search API слой;
- word-by-word realtime transcript за extension-а;
- live claim cards;
- аудио/видео транскрипция;
- `.srt` export;
- текстова проверка;
- онлайн търсене по източници;
- публичен архив със Share ID;
- feedback и animated admin панел.

## Realtime endpoint

```text
wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime
```

## Hugging Face Variables

Препоръчителни стойности за free CPU Space:

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
```

По избор за admin панел:

```bash
ADMIN_KEY=your-secret-admin-key
```

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
