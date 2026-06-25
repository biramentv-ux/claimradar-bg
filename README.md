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

Публична тестова версия за България: Gradio приложение за проверка на твърдения, публичен архив, browser extension и streaming speech-to-text backend prototype.

## Версия 1.1 — Browser Audio Capture + Streaming STT

Добавено:

- `streaming_server.py` — FastAPI WebSocket backend за speech-to-text;
- extension tab audio capture чрез `chrome.tabCapture`;
- offscreen document + `MediaRecorder` за запис на tab аудио;
- изпращане на audio chunks към WebSocket backend;
- live transcript в overlay панела;
- live claim cards от backend-а;
- popup настройки за backend адрес и chunk interval;
- обновени зависимости: FastAPI + Uvicorn.

### Streaming backend старт

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python streaming_server.py
```

WebSocket endpoint:

```text
ws://127.0.0.1:7861/ws/transcribe
```

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
7. Натисни бутона **Аудио** в overlay панела.

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
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
MAX_MEDIA_MB=80
SEARCH_TIMEOUT=8
PUBLIC_BASE_URL=https://dyrakarmy-claimradar-bg.hf.space
STREAM_PORT=7861
STREAM_MIN_SECONDS=8
STREAM_MAX_BUFFER_MB=50
```

По избор за админ панел:

```bash
ADMIN_KEY=your-secret-admin-key
```

## Важно

Streaming режимът е batch-streaming prototype. На CPU може да има забавяне. За production са нужни VPS/GPU, HTTPS/WSS endpoint и по-стабилен audio decoding pipeline.

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
