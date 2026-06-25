# ClaimRadar BG Overlay Extension v2.2

Chrome/Edge extension prototype за live Bulgarian public-claim detection с polished overlay, captions/audio режими, local history и Hugging Face realtime backend.

## Какво прави

- добавя футуристичен overlay върху страницата;
- има toggle за включване/изключване от popup;
- има избор на режим: **Captions / Audio / Selection**;
- има **Floating mini mode**;
- стартира автоматично в YouTube, ако е позволено;
- опитва автоматично да отвори YouTube transcript panel;
- чете видими YouTube captions и transcript сегменти;
- анализира маркиран текст от всяка страница;
- открива вероятно проверими твърдения чрез локални JS heuristics;
- показва бързи линкове за търсене в официални/надеждни източници;
- има **Copy claim** и **Copy all**;
- има **Send to app** за отваряне на ClaimRadar BG с избраното твърдение;
- има **Report** бутон, който копира report payload и го пази в local history;
- пази local history в browser storage;
- поддържа tab audio capture към WebSocket backend;
- показва live word stream и live claim cards от streaming backend.

## Инсталация локално

1. Свали repo-то като ZIP или clone:

```bash
git clone https://github.com/biramentv-ux/claimradar-bg.git
```

2. Отвори Chrome или Edge.
3. Отвори:

```text
chrome://extensions
```

или:

```text
edge://extensions
```

4. Включи **Developer mode**.
5. Натисни **Load unpacked**.
6. Избери папката:

```text
claimradar-bg/extension
```

7. След всяка промяна в extension файловете натисни **Reload** на extension-а в `chrome://extensions`.
8. Отвори YouTube видео с captions/transcript или маркирай текст на произволна страница.

## Popup настройки

В popup-а можеш да управляваш:

- Overlay включен / изключен;
- Floating mini mode;
- Auto-open YouTube transcript;
- Auto-start в YouTube;
- режим на анализ:
  - `captions`;
  - `audio`;
  - `selection`;
- WebSocket backend URL;
- audio chunk milliseconds;
- local history.

По подразбиране production backend е:

```text
wss://dyrakarmy-claimradar-bg.hf.space/ws/realtime
```

## Audio режим

1. Избери `Audio realtime` в popup-а или натисни **Realtime** в overlay-а.
2. Extension-ът иска tab audio stream чрез `chrome.tabCapture`.
3. Offscreen document стартира `MediaRecorder`.
4. Аудиото се изпраща на chunks към WebSocket backend.
5. Backend-ът транскрибира `.webm` buffer чрез Faster Whisper.
6. Overlay-ът показва live word stream + claim cards.

## Local history

Extension-ът пази последните анализи/report-и в `chrome.storage.local`.
От popup-а можеш да видиш последните записи и да ги изчистиш.

## Ограничения

Това е prototype. На free CPU Hugging Face Space realtime audio може да има забавяне. За стабилен production режим е нужен GPU Space, VPS или отделна managed speech-to-text услуга.
