# ClaimRadar BG — GPU / Dedicated Inference

Този слой добавя безопасен runtime избор между CPU, GPU и dedicated transcription endpoint.

## Файлове

```text
hardware_inference.py
```

## Endpoints

```text
/inference/status
/api/inference/status
/api/inference/recommendation
```

## Как работи

При стартиране `auth_launch.py` извиква:

```python
configure_app_module(app_module)
```

Това конфигурира `app.py` без да чупи CPU fallback:

- `WHISPER_DEVICE=auto` избира `cuda`, ако GPU е наличен;
- ако CUDA model load се провали, fallback към `cpu/int8`, освен ако `WHISPER_GPU_FALLBACK_CPU=0`;
- ако има `DEDICATED_TRANSCRIBE_URL`, transcription може да се offload-ва към външен/dedicated endpoint;
- ако dedicated endpoint падне, local fallback остава активен чрез `DEDICATED_FALLBACK_LOCAL=1`.

## Препоръчани Hugging Face Space variables

### CPU-safe default

```bash
INFERENCE_MODE=auto
INFERENCE_AUTO_GPU=1
WHISPER_DEVICE=auto
WHISPER_MODEL_SIZE=base
WHISPER_CPU_COMPUTE_TYPE=int8
WHISPER_GPU_COMPUTE_TYPE=float16
WHISPER_GPU_FALLBACK_CPU=1
```

### GPU Space

След upgrade на Space hardware към GPU:

```bash
INFERENCE_MODE=auto
INFERENCE_AUTO_GPU=1
WHISPER_DEVICE=auto
WHISPER_MODEL_SIZE=medium
WHISPER_CPU_COMPUTE_TYPE=int8
WHISPER_GPU_COMPUTE_TYPE=float16
WHISPER_GPU_FALLBACK_CPU=1
```

Алтернатива за по-ниска VRAM употреба:

```bash
WHISPER_GPU_COMPUTE_TYPE=int8_float16
```

### Dedicated transcription endpoint

```bash
INFERENCE_MODE=dedicated
DEDICATED_INFERENCE_ENABLED=1
DEDICATED_TRANSCRIBE_URL=https://YOUR-ENDPOINT/transcribe
DEDICATED_INFERENCE_TOKEN=...
DEDICATED_TRANSCRIBE_TIMEOUT=180
DEDICATED_FALLBACK_LOCAL=1
```

Очакван response от dedicated endpoint:

```json
{
  "transcript": "...",
  "segments": [
    {"start": 0.0, "end": 2.4, "text": "..."}
  ],
  "srt": "optional SRT text"
}
```

## Проверка

```bash
curl https://claimradar.dyrakarmy.eu/api/inference/status
curl https://claimradar.dyrakarmy.eu/api/inference/recommendation
```

## Hugging Face GPU hardware

Hugging Face Spaces позволяват upgrade към GPU през Settings → Hardware. След GPU upgrade приложението ще избере `cuda`, когато `WHISPER_DEVICE=auto` и GPU е видим в runtime-а.

## Важни бележки

- CPU режимът остава безопасният fallback.
- Dedicated endpoint не е задължителен.
- Не записвай `DEDICATED_INFERENCE_TOKEN` в кода — само в Hugging Face Secrets/Variables.
- При CUDA грешка приложението автоматично пада към CPU, ако `WHISPER_GPU_FALLBACK_CPU=1`.
- За публичен production endpoint препоръчителен минимум е GPU T4/L4 или dedicated endpoint за дълги файлове.
