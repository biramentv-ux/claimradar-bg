# ClaimRadar BG — Production Observability

Този слой добавя истински production observability dashboard и Prometheus-compatible metrics endpoint.

## Файлове

```text
production_observability.py
```

## Endpoints

```text
/observability
/observability/status
/api/observability/summary
/api/observability/providers
/api/observability/costs
/api/observability/ai-usage
/metrics
```

## Какво следи

- uptime;
- total requests;
- status codes;
- error rate;
- avg latency;
- p50 / p95 / p99 latency от recent requests;
- recent errors;
- jobs stats;
- queue status;
- DB status;
- custom domain status;
- search provider health;
- AI provider health;
- token usage;
- estimated AI cost;
- recent system events.

## Prometheus metrics

Endpoint:

```bash
curl https://claimradar.dyrakarmy.eu/metrics
```

Примерни metrics:

```text
claimradar_up
claimradar_uptime_seconds
claimradar_requests_total
claimradar_errors_total
claimradar_error_rate
claimradar_latency_avg_ms
claimradar_latency_p95_ms
claimradar_ai_tokens_total
claimradar_ai_cost_usd_total
claimradar_jobs_total
claimradar_jobs_by_status
claimradar_search_provider_configured
claimradar_ai_provider_configured
```

## Dashboard

```bash
https://claimradar.dyrakarmy.eu/observability
```

Показва cards за uptime, requests, error rate, p95 latency, AI cost и jobs, плюс таблици за search/AI providers и recent events.

## AI token/cost tracking

Cost endpoint:

```bash
curl https://claimradar.dyrakarmy.eu/api/observability/costs
```

Manual usage event:

```bash
curl -X POST https://claimradar.dyrakarmy.eu/api/observability/ai-usage \
  -H "Content-Type: application/json" \
  -d '{"admin_key":"YOUR_ADMIN_KEY","provider":"openai","model":"gpt-4o-mini","input_tokens":1000,"output_tokens":500}'
```

Cost variables:

```bash
OPENAI_INPUT_COST_PER_1M=...
OPENAI_OUTPUT_COST_PER_1M=...
```

Ако `cost_usd` бъде подаден в payload-а, той има предимство пред автоматичното изчисление.

## SLO variables

```bash
OBSERVABILITY_ENABLED=1
OBSERVABILITY_PROMETHEUS_ENABLED=1
OBSERVABILITY_LATENCY_SLO_MS=2500
OBSERVABILITY_ERROR_RATE_SLO=0.05
OBSERVABILITY_LOG_FILE=data/observability_events.jsonl
OBSERVABILITY_COST_FILE=data/ai_usage_costs.jsonl
```

## Provider health

Search provider health използва текущия `search_providers.active_search_config()` и показва кои доставчици имат credentials:

```text
brave
bing
tavily
serpapi
google_cse
duckduckgo
```

AI provider health показва:

```text
openai configured/missing_credentials
openai model
dedicated inference status
```

## Production препоръка

За външен мониторинг добави scrape към `/metrics` от Prometheus/Grafana/Better Stack/Uptime Kuma. Вграденият dashboard показва текущия runtime state, но външният монитор е нужен за исторически uptime и alerts, когато самият Space е напълно down.
