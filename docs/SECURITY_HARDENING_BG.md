# ClaimRadar BG — OWASP Security Hardening

Този слой добавя практическо runtime hardening, ориентирано по OWASP API Security Top 10 2023 и OWASP HTTP Security Response Headers Cheat Sheet.

## Файлове

```text
owasp_hardening.py
tests/test_owasp_hardening.py
```

## Endpoints

```text
/security/owasp/status
/api/security/owasp/status
/security/owasp/headers
/api/security/owasp/headers
/.well-known/security.txt
```

## Runtime защити

- блокира `TRACE`, `TRACK`, `CONNECT`;
- блокира подозрителни path/query payload-и:
  - path traversal;
  - null byte;
  - CRLF/header injection;
  - `/etc/passwd`;
  - `/proc/self`;
  - `<script>`;
  - `<iframe>`;
  - `javascript:`;
  - `data:text/html`;
  - inline handler probes като `onerror=` / `onload=`;
  - high-confidence `union select` probes;
  - Log4Shell-style `${jndi:...}` probes;
- лимитира path/query дължина;
- опционален host allowlist;
- изисква JSON-compatible content type за API write requests;
- добавя security headers:
  - `Content-Security-Policy`;
  - optional `Content-Security-Policy-Report-Only`;
  - `Strict-Transport-Security`;
  - `X-Content-Type-Options`;
  - `Referrer-Policy`;
  - `Permissions-Policy`;
  - `Cross-Origin-Opener-Policy`;
  - `Cross-Origin-Resource-Policy`;
  - `Origin-Agent-Cluster`;
  - `X-DNS-Prefetch-Control`;
  - `X-Download-Options`;
  - `X-Permitted-Cross-Domain-Policies`;
  - `X-XSS-Protection: 0`;
- harden-ва `Set-Cookie` с `Secure`, `HttpOnly`, `SameSite=Lax`, когато липсват;
- `Cache-Control: no-store` за admin/auth/moderation/db/sentry/telemetry/observability sensitive endpoints;
- публикува basic vulnerability disclosure файл в `/.well-known/security.txt`.

## Environment variables

```bash
OWASP_HARDENING_ENABLED=1
OWASP_BLOCK_SUSPICIOUS_INPUTS=1
OWASP_REQUIRE_JSON_API_POSTS=1
OWASP_CSP_ENABLED=1
OWASP_CSP_REPORT_ONLY_ENABLED=0
OWASP_HSTS_ENABLED=1
OWASP_HSTS_PRELOAD=0
OWASP_HSTS_MAX_AGE=31536000
OWASP_MAX_QUERY_LENGTH=4096
OWASP_MAX_PATH_LENGTH=2048
OWASP_ALLOWED_HOSTS=claimradar.dyrakarmy.eu,dyrakarmy-claimradar-bg.hf.space
OWASP_FRAME_ANCESTORS='self' https://huggingface.co https://*.huggingface.co
OWASP_CSP_POLICY="default-src 'self' https: data: blob:; ..."
OWASP_CSP_REPORT_ONLY_POLICY="default-src 'self' https: data: blob:; ..."
OWASP_COOKIE_HARDENING_ENABLED=1
OWASP_SECURITY_TXT_ENABLED=1
OWASP_SECURITY_CONTACT=https://dyrakarmy-claimradar-bg.hf.space/contact
OWASP_SECURITY_POLICY=https://dyrakarmy-claimradar-bg.hf.space/privacy
OWASP_SECURITY_EXPIRES=2027-07-02T00:00:00Z
```

## OWASP API Top 10 2023 mapping

```text
API1 Broken Object Level Authorization
- private checks/exports require admin/owner access

API2 Broken Authentication
- role-aware API keys, Bearer token support, no hardcoded secrets

API3 Broken Object Property Level Authorization
- export bundles are shaped and private objects are protected

API4 Unrestricted Resource Consumption
- request size guard, rate limits, job caps, path/query caps

API5 Broken Function Level Authorization
- admin/moderator routes require role checks

API6 Unrestricted Access to Sensitive Business Flows
- jobs/moderation/abuse actions are rate-limited and audited

API7 SSRF
- search layer uses source whitelist; this middleware blocks suspicious URI payloads

API8 Security Misconfiguration
- CSP, HSTS, no-store, no-sniff, disallowed methods, header hardening

API9 Improper Inventory Management
- public status endpoints and README endpoint inventory

API10 Unsafe Consumption of APIs
- search/evidence outputs are scored and treated as untrusted evidence
```

## Проверка

```bash
curl https://claimradar.dyrakarmy.eu/api/security/owasp/status
curl https://claimradar.dyrakarmy.eu/api/security/owasp/headers
curl https://claimradar.dyrakarmy.eu/.well-known/security.txt
```

Security headers:

```bash
curl -I https://claimradar.dyrakarmy.eu/product
```

Suspicious input block:

```bash
curl "https://claimradar.dyrakarmy.eu/api/security/owasp/status?x=%2e%2e%2fetc%2fpasswd"
curl "https://claimradar.dyrakarmy.eu/api/security/owasp/status?x=%0d%0aX-Test:yes"
```

Tests:

```bash
pytest tests/test_owasp_hardening.py
```

## Забележка

Това не заменя penetration test, SAST/DAST, secret scanning или dependency scanning. То е runtime hardening слой и security contract за production deployment.
