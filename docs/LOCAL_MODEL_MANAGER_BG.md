# ClaimRadar BG — Local Model Manager

Добавя локален панел за desktop режима.

## Routes

```text
/local-ai/models
/model-manager
/local-ai/model-manager.js
/api/local-ai/model-manager/status
/api/local-ai/model-manager/config
/api/local-ai/ollama/models
/api/local-ai/ollama/download
/api/local-ai/whisper/cache
```

## Какво управлява

```text
Low / Balanced / Power профил
Ollama model mapping
faster-whisper / WhisperX engine
Whisper model mapping
Device: auto / cpu / cuda
Compute type: int8 / int8_float16 / float16 / float32
Offline Mode
Online Evidence Mode
Whisper cache scan
```

## Config файл

```text
data/local_ai/model_manager.json
```

## Проверка

```bash
curl http://127.0.0.1:8765/api/local-ai/model-manager/status
curl http://127.0.0.1:8765/api/local-ai/ollama/models
curl http://127.0.0.1:8765/api/local-ai/whisper/cache
```

## Desktop UI

Отвори:

```text
http://127.0.0.1:8765/local-ai/models
```

или:

```text
http://127.0.0.1:8765/model-manager
```
