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

Публична тестова версия за България: Gradio приложение за проверка на твърдения, публичен архив, browser extension и word-by-word realtime speech-to-text backend prototype.

## Версия 1.2 — Word-by-word Realtime

Добавено:

- `/ws/realtime` WebSocket endpoint;
- rolling audio buffer;
- Faster Whisper `word_timestamps=True`;
- diff алгоритъм за `new_words`;
- live word stream в overlay панела;
- по-къси audio chunks, default `1200 ms`;
- extension default backend: `ws://127.0.0.1:7861/ws/realtime`;
- Windows runners: `run_realtime_server.bat` и `run_realtime_server.ps1`;
- Docker/VPS файлове: `Dockerfile.realtime` и `docker-compose.realtime.yml`;
- пълно ръководство: `REALTIME_SETUP_BG.md`.

## Бърз старт

```powershell
.\run_realtime_server.bat
```

Провери:

```text
http://127.0.0.1:7861/health
```

В extension popup-а backend URL трябва да е:

```text
ws://127.0.0.1:7861/ws/realtime
```

После отвори YouTube/live страница и натисни **Realtime** в overlay панела.

## Browser extension

Файлове:

```text
extension/manifest.json
extension/content.js
extension/audio_controls.js
extension/service_worker.js
extension/offscreen.html
extension/offscreen.js
extension/popup.html
extension/popup.js
extension/README.md
```

Инсталация:

1. Свали repo-то като ZIP или clone.
2. Отвори `chrome://extensions` или `edge://extensions`.
3. Включи Developer mode.
4. Натисни Load unpacked.
5. Избери папката `extension`.
6. Отвори YouTube/live страница.
7. Натисни **Realtime** в overlay панела.

## Gradio app

- приема текст или `.txt` файл;
- приема аудио/видео файл;
- транскрибира чрез Faster Whisper;
- открива вероятно проверими твърдения;
- категоризира ги по теми;
- предлага надеждни български и европейски източници;
- опитва онлайн търсене по релевантни домейни;
- генерира `.srt` субтитри;
- запазва публични проверки в локален JSONL архив;
- позволява търсене по Share ID.

## Настройки

```bash
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
MAX_MEDIA_MB=80
SEARCH_TIMEOUT=8
PUBLIC_BASE_URL=https://dyrakarmy-claimradar-bg.hf.space
STREAM_PORT=7861
REALTIME_INTERVAL=1.6
STREAM_MAX_BUFFER_MB=80
ROLLING_WINDOW_MB=18
STREAM_LANGUAGE=bg
```

По избор за админ панел:

```bash
ADMIN_KEY=your-secret-admin-key
```

## Production

За реално публично live използване препоръчително: GPU VPS, HTTPS/WSS reverse proxy, persistent database, rate limiting, user/session IDs, diarization и AI evaluator с цитати.

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
