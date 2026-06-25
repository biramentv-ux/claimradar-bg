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

Финална Hugging Face-ready версия за България: Docker Space с Gradio интерфейс, публичен архив, browser extension, word-by-word realtime WebSocket backend и AI verdict engine.

## Версия 2.2 — AI Verdict Engine

Добавено:

- нов tab **🧠 AI verdict**;
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
- `/health` endpoint;
- `/ws/realtime` WebSocket endpoint;
- AI verdict + цитати;
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

Health check:

```text
https://dyrakarmy-claimradar-bg.hf.space/health
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
```

По избор за admin панел:

```bash
ADMIN_KEY=your-secret-admin-key
```

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
