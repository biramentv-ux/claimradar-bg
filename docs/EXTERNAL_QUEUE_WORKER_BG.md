# ClaimRadar BG — External Queue Worker

Този слой изнася тежките jobs извън основния FastAPI/Gradio процес.

FastAPI `BackgroundTasks` са удобни за малки задачи след връщане на response, но при тежки изчисления е по-добре да се използва отделен worker / task queue. External queue режимът прави точно това: API процесът само записва job, а отделен процес `queue_worker.py` го изпълнява.

## Файлове

```text
external_queue.py
queue_backends.py
postgres_queue.py
queue_worker.py
scripts/start_production.sh
```

## Endpoints

```text
/queue/status
/api/queue/status
/jobs
/api/jobs
/api/jobs/stats
/api/jobs/<job_id>
/api/jobs/<job_id>/cancel
/api/jobs/<job_id>/retry
```

## Режими

### Thread режим

```bash
JOB_EXECUTION_MODE=thread
QUEUE_WORKER_AUTOSTART=0
```

Това запазва досегашното поведение — jobs се изпълняват вътре в web app процеса.

### External JSONL режим

```bash
JOB_EXECUTION_MODE=external
QUEUE_BACKEND=jsonl
QUEUE_WORKER_AUTOSTART=1
QUEUE_POLL_SECONDS=2.0
QUEUE_BATCH_SIZE=1
QUEUE_STALE_RUNNING_SECONDS=1800
```

Този режим е подходящ, когато web process и worker process са в един и същ container / shared filesystem.

### External Postgres/Supabase режим — препоръчителен за отделен worker

```bash
JOB_EXECUTION_MODE=external
QUEUE_BACKEND=postgres
QUEUE_WORKER_AUTOSTART=0
DB_ENABLED=1
DATABASE_URL=<postgres-connection-string>
```

В този режим UI процесът записва jobs в `public.claimradar_jobs`, а отделен worker процес/контейнер ги claim-ва и изпълнява. Това е подходящо за разделяне на UI Space и Worker Space, защото общото състояние е в Supabase/Postgres, не в локален файл.

## Стартиране на отделен worker процес

В отделен container/Space/машина за worker сложи:

```bash
APP_ROLE=worker
WORKER_ONLY_MODE=1
JOB_EXECUTION_MODE=external
QUEUE_BACKEND=postgres
QUEUE_POLL_SECONDS=2.0
QUEUE_BATCH_SIZE=1
DB_ENABLED=1
DATABASE_URL=<same-postgres-connection-string>
```

Startup script-ът ще изпълни само:

```bash
python queue_worker.py --poll 2 --batch 1
```

и няма да стартира Gradio/FastAPI UI.

## UI process variables

В основния web app / UI Space:

```bash
APP_ROLE=web
JOB_EXECUTION_MODE=external
QUEUE_BACKEND=postgres
QUEUE_WORKER_AUTOSTART=0
DB_ENABLED=1
DATABASE_URL=<same-postgres-connection-string>
```

Така `/api/jobs/check`, `/api/jobs/ai-verdict` и `/api/jobs/real-check` само enqueue-ват jobs. Тежкото изпълнение е извън UI процеса.

## Проверка

```bash
curl https://claimradar.dyrakarmy.eu/api/queue/status
curl https://claimradar.dyrakarmy.eu/api/jobs/stats
curl https://claimradar.dyrakarmy.eu/api/jobs?status=queued
```

Очаквай:

```json
{
  "queue_backend": "postgres",
  "store_type": "PostgresQueueBackedJobStore",
  "external_store_active": true
}
```

## Защо е по-добре

- HTTP/UI процесът не блокира при тежък AI/transcription/video job;
- worker-ът може да се рестартира отделно;
- може да се добавят повече workers;
- queue state е durable в Supabase/Postgres;
- retry/cancel/status API остава същото;
- worker-only режимът не стартира web app и не заема UI resources.

## Тестове

```bash
pytest tests/test_external_worker_queue.py
```

## Следваща стъпка

За много голям трафик остава възможност за Redis/RabbitMQ + Celery, но `QUEUE_BACKEND=postgres` вече позволява реален отделен worker без да товари основния app процес.
