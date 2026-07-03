# ClaimRadar BG — самостоятелна AI desktop платформа

Този документ описва хибридната desktop композиция:

```text
Electron desktop shell
+ локален Python/FastAPI backend sidecar
+ Ollama local LLM runtime
+ faster-whisper / WhisperX transcription
+ local archive / SQLite-first storage
+ optional Online Evidence Mode
```

## Цел

ClaimRadar BG да може да работи не само като сайт, а и като Windows desktop платформа:

```text
ClaimRadarBG-Setup.exe
ClaimRadarBG Portable
```

Потребителят инсталира приложението и то използва локалните ресурси на машината: CPU, RAM, GPU/VRAM и свободно дисково място.

## Основни файлове

```text
local_ai_runtime.py
local_desktop_launch.py
desktop/electron/package.json
desktop/electron/main.js
desktop/electron/preload.js
desktop/electron/renderer/index.html
scripts/build_desktop_backend.py
scripts/build_windows_portable.py
```

## Runtime routes

```text
/local-ai/status
/api/local-ai/status
```

## Cloud replacement map

| Cloud component | Local replacement |
|---|---|
| OpenAI API | Ollama local model endpoint |
| Hugging Face Space | local FastAPI backend on 127.0.0.1 |
| Supabase/Postgres | SQLite/local files first, optional sync later |
| Search APIs | local archive in Offline Mode; Brave/Tavily/SerpApi only in Online Evidence Mode |
| remote transcription | local faster-whisper / WhisperX |
| exports | local PDF/Markdown generation |

## Hardware режими

### Low mode

```text
CPU only
Ollama small model
faster-whisper base/tiny on CPU INT8
WhisperX off
small media limits
```

### Balanced mode

```text
CPU + optional GPU
Ollama 7B/8B class model
faster-whisper small on auto device
WhisperX optional, diarization off
medium media limits
```

### Power mode

```text
NVIDIA CUDA GPU preferred
Ollama stronger local model
faster-whisper large-v3 on CUDA float16
WhisperX enabled
larger batch/media limits
```

## Двата режима на работа

### Offline Mode

```text
анализира текст
открива твърдения
използва локални модели
сравнява с локална база/архив
генерира доклад
```

### Online Evidence Mode

```text
търси в интернет
ползва Brave/Tavily/SerpApi
проверява актуални източници
генерира доклад с evidence links
```

## Фаза 1 — Portable Windows build

```bash
python scripts/build_desktop_backend.py --clean
python scripts/build_windows_portable.py
```

Резултатът се подготвя в:

```text
dist/desktop-backend
dist/desktop
```

## Фаза 2 — EXE Installer

Electron build config поддържа:

```text
nsis
portable
```

Команда:

```bash
cd desktop/electron
npm install
npm run dist
```

## Фаза 3 — Local AI Runtime

Основни local variables:

```bash
LOCAL_AI_ENABLED=1
LOCAL_AI_MODE=offline
LOCAL_AI_PROFILE=auto
OLLAMA_BASE_URL=http://127.0.0.1:11434
TRANSCRIPTION_ENGINE=faster-whisper
WHISPER_MODEL_POWER=large-v3
WHISPERX_ENABLED=1
```

## Фаза 4 — Model Manager

Следващият слой трябва да добави UI за:

```text
Ollama status
pull local model
list local models
select Low/Balanced/Power model
download/verify Whisper model cache
WhisperX enable/disable
```

## Фаза 5 — Auto hardware detection

`local_ai_runtime.py` вече връща:

```text
CPU cores
RAM GB
NVIDIA GPU summary if nvidia-smi exists
free disk GB
selected profile
selected Whisper/Ollama config
```

Проверка:

```bash
curl http://127.0.0.1:8765/api/local-ai/status
```

## Desktop security baseline

Electron shell-ът е настроен с:

```text
contextIsolation=true
nodeIntegration=false
sandbox=true
preload bridge only
external URL open through shell.openExternal
```

## Важно

Offline Mode може да работи без cloud, но актуална проверка на факти в интернет по дефиниция изисква Online Evidence Mode. Затова системата трябва да бъде local-first, а не online-only.
