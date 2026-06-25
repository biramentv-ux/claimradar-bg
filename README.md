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

Публична тестова версия за България: Gradio приложение за проверка на твърдения плюс browser extension prototype.

## Версия 1.0 — Browser Extension Prototype

Добавено в папка `extension/`:

- Chrome/Edge extension с Manifest V3;
- overlay панел върху YouTube и web страници;
- автоматичен старт в YouTube;
- четене на видими captions/transcript сегменти;
- анализ на маркиран текст от страницата;
- локален Bulgarian claim detector в браузъра;
- source search линкове по домейни;
- бутон към публичното ClaimRadar BG приложение;
- футуристичен cyber/neon дизайн.

### Файлове

```text
extension/manifest.json
extension/content.js
extension/popup.html
extension/popup.js
extension/README.md
```

### Инсталация

1. Свали repo-то като ZIP или clone.
2. Отвори `chrome://extensions` или `edge://extensions`.
3. Включи Developer mode.
4. Натисни Load unpacked.
5. Избери папката `extension`.
6. Отвори YouTube видео с captions или transcript.

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
```

По избор за админ панел:

```bash
ADMIN_KEY=your-secret-admin-key
```

## Дисклеймър

Това е тестов инструмент. Не е окончателна правна, политическа или журналистическа оценка. Всички резултати трябва да се проверяват по посочените източници.
