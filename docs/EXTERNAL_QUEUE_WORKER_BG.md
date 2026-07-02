# ClaimRadar BG — External Queue Worker

Този слой изнася тежките jobs извън основния FastAPI/Gradio процес.

FastAPI `BackgroundTasks` са удобни за задачи след връщане на response, но при тежки изчисления е по-добре да се използва отделен worker / task queue. External queue режимът прави точно това: API процесът само записва job, а отделен процес `queue_worker.py` го изпълнява.

## Файлове

```text
external_queue.py
queue_worker.py
scripts/start_production.sh
```

## Endpoints

```text
/queue/status
/api/queue/status
```

## Режими

### Стандартен режим — thread executor

```bash
JOB_EXECUTION_MODE=thread
QUEUE_WORKER_AUTOSTART=0
```

Това запазва досегашното поведение — jobs се изпълняват вътре в web app процеса чрез `ThreadPoolExecutor`.

### External queue режим

```bash
JOB_EXECUTION_MODE=external
QUEUE_WORKER_AUTOSTART=1
QUEUE_POLL_SECONDS=2.0
QUEUE_BATCH_SIZE=1
QUEUE_STALE_RUNNING_SECONDS=1800
```

В този режим:

- `/api/jobs/check`, `/api/jobs/ai-verdict`, `/api/jobs/real-check` само enqueue-ват job;
- job payload-ите се записват в `data/job_payloads.jsonl`;
- job state се записва в `data/jobs.jsonl`;
- worker heartbeat се записва в `data/queue_worker_heartbeats.jsonl`;
- отделният процес `python queue_worker.py` claim-ва и изпълнява job-овете.

## Стартиране в Docker / Hugging Face Space

Dockerfile вече стартира:

```bash
/bin/sh /app/scripts/start_production.sh
```

Ако `QUEUE_WORKER_AUTOSTART=1` или `JOB_EXECUTION_MODE=external`, script-ът стартира worker в background и после web app процеса.

Пример Hugging Face Variables:

```bash
JOB_EXECUTION_MODE=external
QUEUE_WORKER_AUTOSTART=1
QUEUE_POLL_SECONDS=2.0
QUEUE_BATCH_SIZE=1
QUEUE_STALE_RUNNING_SECONDS=1800
```

## Стартиране само на worker

За отделен контейнер/машина:

```bash
python queue_worker.py --poll 2 --batch 1
```

За тестово изпълнение на един job:

```bash
python queue_worker.py --once
```

## Проверка

```bash
curl https://claimradar.dyrakarmy.eu/api/queue/status
curl https://claimradar.dyrakarmy.eu/api/jobs/stats
curl https://claimradar.dyrakarmy.eu/api/jobs?status=queued
```

## Защо е по-добре

- HTTP процесът не блокира при тежък AI/transcription job;
- worker-ът може да се рестартира отделно;
- може да се добавят повече workers по-късно;
- queue state е durable през JSONL fallback и DB mirror слоя;
- retry/cancel/status API остава същото.

## Следваща стъпка

Този JSONL queue слой е production-safe за малък/среден трафик. При по-голям трафик следващата стъпка е Redis/RabbitMQ + Celery/RQ/Arq worker deployment.
