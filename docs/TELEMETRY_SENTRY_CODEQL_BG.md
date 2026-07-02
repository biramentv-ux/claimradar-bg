# ClaimRadar BG — OpenTelemetry, Sentry и CodeQL

Този слой добавя production tracing, error tracking и code scanning.

## Файлове

```text
telemetry_integrations.py
.github/workflows/codeql.yml
```

## Endpoints

```text
/telemetry/status
/api/telemetry/status
/api/telemetry/test-span
```

## OpenTelemetry tracing

OpenTelemetry е vendor-neutral стандарт за telemetry signals като traces, metrics и logs. В проекта се използва за request tracing и manual spans.

Variables:

```bash
OTEL_ENABLED=1
OTEL_SERVICE_NAME=claimradar-bg
OTEL_SAMPLE_RATE=1.0
OTEL_FASTAPI_INSTRUMENTATION_ENABLED=1
OTEL_REQUESTS_INSTRUMENTATION_ENABLED=1
OTEL_EXPORTER_OTLP_ENDPOINT=https://YOUR-OTEL-COLLECTOR/v1/traces
OTEL_CONSOLE_EXPORTER_ENABLED=0
```

Проверка:

```bash
curl https://claimradar.dyrakarmy.eu/api/telemetry/status
curl -X POST https://claimradar.dyrakarmy.eu/api/telemetry/test-span
```

## Sentry error tracking

Sentry се включва само когато production environment има конфигуриран Sentry project endpoint. Не записвай чувствителни стойности в repository-то.

Variables:

```bash
SENTRY_ENABLED=1
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0
```

## CodeQL security scanning

Добавен е GitHub Actions workflow:

```text
.github/workflows/codeql.yml
```

Той се стартира при:

```text
push към main
pull_request към main
седмичен schedule
manual workflow_dispatch
```

Използва:

```text
github/codeql-action/init@v3
github/codeql-action/autobuild@v3
github/codeql-action/analyze@v3
queries: security-extended,security-and-quality
```

## Production препоръка

- OpenTelemetry traces изпращай към Grafana Tempo, Honeycomb, Jaeger, New Relic, Datadog или OTEL Collector.
- Sentry използвай за traceback-и, crash reports и performance spans.
- CodeQL остави включен за всеки push/PR, за да хваща уязвимости преди deploy.
