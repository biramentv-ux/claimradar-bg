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

Финална Hugging Face-ready версия за България: Docker Space с Gradio интерфейс + публичен архив + browser extension + word-by-word realtime WebSocket backend.

## Важно: Space-ът трябва да е Docker

Проектът вече използва **FastAPI + Gradio + WebSocket** в един процес. Това е най-стабилно като Hugging Face **Docker Space**.

Metadata:

```yaml
sdk: docker
app_port: 7860
```

Добавен е финален `Dockerfile`, който стартира:

```bash
python launch.py
```

на порт `7860`.

## Версия 2.1 — Animated Product Redesign

Добавено в `app.py`:

- нов футуристичен **Animated Control Center** интерфейс;
- animated aurora/grid background;
- glassmorphism cards;
- animated metric cards;
- neon glow hover effects;
- shimmer progress bars;
- reveal animations чрез JS MutationObserver;
- animated counters;
- redesigned claim cards;
- redesigned archive cards;
- redesigned **Admin Control Center**;
- еднакъв визуален стил за потребителския интерфейс и админ панела.

## Готово за Hugging Face

След build приложението дава:

- публичен Gradio интерфейс;
- `/health` endpoint;
- `/ws/realtime` WebSocket endpoint;
- word-by-word realtime transcript за extension-а;
- live claim cards;
- аудио/видео транскрипция;
- `.srt` export;
- текстова проверка;
- онлайн търсене по източници;
- публичен архив със Share ID;
- feedback и animated admin панел.

## Realtime endpoint след качване

```text
wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime
```

Health check:

```text
https://dyrakarmy-claimradar-bg.hf.space/health
```

## Extension

1. Свали repo-то като ZIP или clone.
2. Отвори `chrome://extensions` или `edge://extensions`.
3. Включи Developer mode.
4. Натисни Load unpacked.
5. Избери папката `extension`.
6. В popup-а backend URL трябва да е:

```text
wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime
```

7. Отвори YouTube/live страница.
8. Натисни **Realtime** в overlay панела.

## Hugging Face Variables

Препоръчителни стойности за free CPU Space:

```bash
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
MAX_MEDIA_MB=80
REALTIME_INTERVAL=2.2
ROLLING_WINDOW_MB=12
STREAM_MAX_BUFFER_MB=60
STREAM_LANGUAGE=bg
PUBLIC_BASE_URL=https://dyrakarmy-claimradar-bg.hf.space
```

По избор за admin панел:

```bash
ADMIN_KEY=your-secret-admin-key
```

## Важно за latency

Free CPU Space ще работи, но няма да е broadcast-grade realtime. Първото пускане ще е по-бавно, защото моделът се зарежда. За ниска латентност използвай GPU Space или VPS.

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
