---
title: BG Fact Checker
emoji: 🔎
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 5.9.1
app_file: app.py
pinned: false
license: mit
---

# ClaimRadar BG

Финална Hugging Face-ready версия за България: Gradio приложение + публичен архив + browser extension + word-by-word realtime WebSocket backend в един Space.

## Финална версия 2.0 — готова за качване в Hugging Face

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
- feedback и admin панел.

## Какво да качиш в Hugging Face

Качи минимум тези файлове:

```text
app.py
requirements.txt
README.md
```

За browser extension-а качи/запази и папката:

```text
extension/
```

## Realtime endpoint след качване

```text
wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime
```

Health check:

```text
https://dyrakarmy-claimradar-bg.hf.space/health
```

## Extension

След качване на Space-а:

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
