# ClaimRadar BG Overlay Extension v1.1

Chrome/Edge extension prototype for live Bulgarian public-claim detection with optional tab-audio streaming transcription.

## Какво прави

- добавя футуристичен overlay върху страницата;
- стартира автоматично в YouTube;
- чете видими YouTube captions и transcript сегменти, когато са налични;
- анализира маркиран текст от всяка страница;
- открива вероятно проверими твърдения чрез локални JS heuristics;
- показва бързи линкове за търсене в официални/надеждни източници;
- добавя бутон **Аудио** за tab audio capture;
- изпраща аудио chunks към WebSocket backend;
- показва live transcript и намерени твърдения от streaming backend.

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

7. Отвори YouTube видео с включени captions или transcript.
8. Overlay-ът трябва да се появи долу вдясно.

## Streaming speech-to-text backend

Стартирай backend-а локално:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python streaming_server.py
```

По подразбиране WebSocket адресът е:

```text
ws://127.0.0.1:7861/ws/transcribe
```

В popup-а на extension-а можеш да смениш backend адреса. После отвори YouTube/live страница и натисни **Аудио** в overlay панела.

## Как работи audio режимът

1. Service worker иска tab audio stream чрез `chrome.tabCapture`.
2. Offscreen document стартира `MediaRecorder`.
3. Аудиото се изпраща на chunks към WebSocket backend.
4. Backend-ът транскрибира натрупания `.webm` buffer чрез Faster Whisper.
5. Резултатът се връща към overlay панела като live transcript + claim cards.

## Ограничения

Това е prototype. Транскрипцията е batch-streaming, не истински word-by-word realtime. На CPU може да има забавяне. За стабилен production режим е нужен VPS/GPU или отделна managed speech-to-text услуга.

## Следваща стъпка

- production deployment на streaming backend;
- HTTPS/WSS endpoint;
- оптимизирано chunk decoding;
- diarization/разпознаване на говорители;
- AI оценка с цитати;
- overlay върху live debate stream.
