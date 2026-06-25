---
title: BG Fact Checker
emoji: 🔎
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 5.9.1
app_file: launch.py
pinned: false
license: mit
---

# ClaimRadar BG

Финална Hugging Face-ready версия за България: Gradio приложение + публичен архив + browser extension + word-by-word realtime WebSocket backend в един Space.

## Hotfix — Hugging Face launcher

Добавен е `launch.py`, който стартира приложението стабилно на стандартния Hugging Face порт `7860` и избягва грешката:

```text
[Errno 98] address already in use: 0.0.0.0:7861
```

В README metadata вече е зададено:

```yaml
app_file: launch.py
```

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

След качване в Space `DyrakArmy/claimradar-bg` приложението дава:

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

## Локален fallback

Ако искаш локален backend:

```powershell
.\run_realtime_server.bat
```

и в extension popup-а смени backend на:

```text
ws://127.0.0.1:7861/ws/realtime
```

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
