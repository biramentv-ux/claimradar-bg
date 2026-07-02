# ClaimRadar BG — реален load test

Този проект има production-safe load test, който се изпълнява срещу реалния Hugging Face Space.

## Workflow

```text
.github/workflows/load-test.yml
```

Workflow-ът може да се стартира:

- автоматично при промяна в `scripts/load_test.py`, `docs/LOAD_TESTING_BG.md` или workflow файла;
- ръчно от GitHub → Actions → **Real Load Test** → **Run workflow**.

## Script

```text
scripts/load_test.py
```

Скриптът използва само Python standard library и не изисква допълнителни зависимости.

## Default target

```text
https://dyrakarmy-claimradar-bg.hf.space
```

## Default endpoints

```text
/health
/product
/auth/status
/db/status
/rate-limit/status
/monitoring/status
/api/jobs/stats
```

Тези endpoints са избрани, защото са сравнително леки и не стартират тежка транскрипция или AI проверка.

## Default profile

```text
requests: 70
concurrency: 5
timeout: 25 seconds
max_error_rate: 0.20
max_p95_ms: 15000
```

Това е gentle live profile. Целта е да провери дали deployment-ът е жив, стабилен и с приемлива латентност, без да натоварва агресивно Hugging Face Space.

## Manual run locally

```bash
python scripts/load_test.py \
  --base-url https://dyrakarmy-claimradar-bg.hf.space \
  --requests 70 \
  --concurrency 5
```

## More aggressive manual test

Използвай само ако си сигурен, че deployment-ът може да го понесе:

```bash
python scripts/load_test.py \
  --base-url https://dyrakarmy-claimradar-bg.hf.space \
  --requests 200 \
  --concurrency 10 \
  --max-error-rate 0.10 \
  --max-p95-ms 12000
```

## GitHub Actions inputs

При ръчно стартиране можеш да зададеш:

```text
base_url
requests
concurrency
max_error_rate
max_p95_ms
```

## Output artifacts

Workflow-ът качва artifact:

```text
claimradar-bg-load-test-report
```

В него има:

```text
load-test-report.json
load-test-report.md
```

## Как да четеш резултата

Основните стойности са:

- `ok` — успешни заявки;
- `failed` — неуспешни заявки;
- `error_rate` — процент грешки;
- `latency_ms.p50 / p95 / p99`;
- `requests_per_second`;
- `status_counts`;
- `endpoint_counts`;
- `passed`.

## Важно

Този тест не е DDoS, stress test или benchmark на максимален капацитет. Той е production-safe smoke/load test за реална публична достъпност и стабилност.
