# ClaimRadar BG — Local Offline Engines

Добавени са първите реални локални engine слоеве за desktop/offline режим.

## Файлове

```text
local_llm_engine.py
local_transcription.py
local_storage_sqlite.py
local_archive.py
.github/workflows/desktop-windows-build.yml
```

## Local LLM Engine

Routes:

```text
/api/local-ai/llm/status
/api/local-ai/llm/generate
/api/local-ai/claims/extract
/api/local-ai/verdict
```

Използва локален Ollama HTTP API на:

```text
http://127.0.0.1:11434
```

## Local Transcription

Routes:

```text
/api/local-ai/transcribe/status
/api/local-ai/transcribe
```

Поддържани engine режими:

```text
faster-whisper
whisperx
```

Power профилът използва `large-v3`, CUDA/float16 когато е налично.

## Local SQLite Storage

Routes:

```text
/api/local-db/status
/api/local-db/checks
```

Локална база:

```text
data/local_ai/claimradar_local.db
```

## Local Archive

Routes:

```text
/api/local-ai/archive/status
/api/local-ai/archive/sources
/api/local-ai/archive/import-text
/api/local-ai/archive/import-file
/api/local-ai/archive/search
```

Offline Evidence Mode използва локални chunks от импортнати документи.

## Windows Desktop Build

Workflow:

```text
.github/workflows/desktop-windows-build.yml
```

Създава backend с PyInstaller и desktop package с Electron builder.

## Проверка локално

```bash
curl http://127.0.0.1:8765/api/local-ai/llm/status
curl http://127.0.0.1:8765/api/local-ai/transcribe/status
curl http://127.0.0.1:8765/api/local-db/status
curl http://127.0.0.1:8765/api/local-ai/archive/status
```
