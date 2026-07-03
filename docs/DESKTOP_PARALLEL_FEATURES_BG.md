# ClaimRadar BG — Desktop parallel features

Добавени са паралелно следните desktop/local слоеве.

## 5) Online Evidence Mode switch

```text
local_evidence_router.py
```

Routes:

```text
/api/local-ai/evidence/status
/api/local-ai/evidence/search
```

Режими:

```text
Offline Mode -> само local archive
Online Evidence Mode -> Brave/Tavily/SerpApi/DuckDuckGo + local archive
Hybrid -> първо local archive, после web evidence
```

## 6) Desktop UI integration

```text
local_desktop_ui.py
/desktop
/local-ai
```

Electron вече отваря `/desktop` по подразбиране.

## 7) Реален EXE build pipeline

```text
.github/workflows/desktop-windows-build.yml
```

Workflow-ът build-ва PyInstaller backend и Electron desktop installer/portable package.

## 8) Installer polish + code signing

```text
desktop/electron/package.json
```

Добавени са Windows installer настройки, publisher metadata, execution level, NSIS polish и optional signing през CI environment secrets.

## 9) Реален model download progress

```text
local_model_downloads.py
```

Routes:

```text
/api/local-ai/ollama/download/start
/api/local-ai/ollama/downloads
/api/local-ai/ollama/downloads/{download_id}
```

Използва streaming `POST /api/pull` от Ollama и пази текущ progress/status в паметта на процеса.

## 10) Hardware benchmark

```text
local_hardware_benchmark.py
```

Routes:

```text
/api/local-ai/benchmark/status
/api/local-ai/benchmark/run
```

Връща CPU score, optional Ollama token/sec test и препоръчан профил: low/balanced/power.

## Бърза локална проверка

```bash
curl http://127.0.0.1:8765/api/local-ai/evidence/status
curl http://127.0.0.1:8765/api/local-ai/benchmark/status
curl http://127.0.0.1:8765/api/local-ai/ollama/downloads
```
