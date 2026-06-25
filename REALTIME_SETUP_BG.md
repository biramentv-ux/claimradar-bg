# ClaimRadar BG — Word-by-word Realtime Setup

Този модул добавя максимално близък до word-by-word realtime режим с браузърен tab audio capture, WebSocket streaming backend и Faster Whisper word timestamps.

## Компоненти

```text
Chrome/Edge tab audio
→ extension/offscreen.js MediaRecorder chunks
→ ws://127.0.0.1:7861/ws/realtime
→ streaming_server.py
→ Faster Whisper word_timestamps=True
→ transcript + new_words + claim cards
→ overlay live word stream
```

## Бърз старт на Windows

```powershell
.\run_realtime_server.bat
```

или:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_realtime_server.ps1 -Model small -Device cpu -ComputeType int8 -Port 7861 -Interval 1.6
```

После в extension popup-а използвай:

```text
ws://127.0.0.1:7861/ws/realtime
```

## Инсталиране на extension-а

1. Отвори `chrome://extensions` или `edge://extensions`.
2. Включи **Developer mode**.
3. Натисни **Load unpacked**.
4. Избери папката `extension`.
5. Отвори YouTube/live страница.
6. Натисни **Realtime** в overlay панела.

## Проверка на backend-а

Отвори:

```text
http://127.0.0.1:7861/health
```

Очаквано:

```json
{"ok": true, "version": "realtime-1.0"}
```

## Docker/VPS старт

```bash
docker compose -f docker-compose.realtime.yml up --build -d
```

Публичен deployment трябва да използва HTTPS/WSS reverse proxy, например Nginx/Caddy/Traefik.

## Настройки

```bash
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
STREAM_PORT=7861
REALTIME_INTERVAL=1.6
STREAM_MAX_BUFFER_MB=80
ROLLING_WINDOW_MB=18
STREAM_LANGUAGE=bg
```

### За CPU

```bash
WHISPER_MODEL_SIZE=base
WHISPER_COMPUTE_TYPE=int8
REALTIME_INTERVAL=2.5
```

### За GPU/VPS

```bash
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
REALTIME_INTERVAL=0.8
```

## Какво значи “word-by-word realtime” тук

Faster Whisper не е истински token streaming engine. Този проект използва rolling audio buffer + `word_timestamps=True`, изчислява разлика между вече изпратени и новоразпознати думи и праща `new_words` към overlay-а. Практически потребителят вижда думите да се появяват постепенно, но с latency според хардуера.

## Production препоръка

За стабилен публичен продукт:

- GPU VPS;
- WSS endpoint;
- persistent logs/database;
- user/session IDs;
- rate limiting;
- better audio decoding pipeline;
- speaker diarization;
- AI fact-check evaluator with citations.
