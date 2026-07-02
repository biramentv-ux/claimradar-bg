# ClaimRadar BG — OWASP Security Hardening

Този слой добавя практическо runtime hardening, ориентирано по OWASP API Security Top 10 2023 и OWASP HTTP Security Response Headers Cheat Sheet.

## Файлове

```text
owasp_hardening.py
```

## Endpoints

```text
/security/owasp/status
/api/security/owasp/status
```

## Runtime защити

- блокира `TRACE`, `TRACK`, `CONNECT`;
- блокира подозрителни path/query payload-и:
  - path traversal;
  - null byte;
  - `/etc/passwd`;
  - `/proc/self`;
  - `<script>`;
  - `javascript:`;
- лимитира path/query дължина;
- опционален host allowlist;
- изисква JSON-compatible content type за API write requests;
- добавя security headers:
  - `Content-Security-Policy`;
  - `Strict-Transport-Security`;
  - `X-Content-Type-Options`;
  - `Referrer-Policy`;
  - `Permissions-Policy`;
  - `Cross-Origin-Opener-Policy`;
  - `X-DNS-Prefetch-Control`;
  - `X-Download-Options`;
- `Cache-Control: no-store` за admin/auth/moderation/db sensitive endpoints.

## Environment variables

```bash
OWASP_HARDENING_ENABLED=1
OWASP_BLOCK_SUSPICIOUS_INPUTS=1
OWASP_REQUIRE_JSON_API_POSTS=1
OWASP_CSP_ENABLED=1
OWASP_HSTS_ENABLED=1
OWASP_HSTS_MAX_AGE=31536000
OWASP_MAX_QUERY_LENGTH=4096
OWASP_MAX_PATH_LENGTH=2048
OWASP_ALLOWED_HOSTS=claimradar.dyrakarmy.eu,dyrakarmy-claimradar-bg.hf.space
OWASP_CSP_POLICY="default-src 'self' https: data: blob:; ..."
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
```

Security headers:

```bash
curl -I https://claimradar.dyrakarmy.eu/product
```

Suspicious input block:

```bash
curl "https://claimradar.dyrakarmy.eu/api/security/owasp/status?x=%2e%2e%2fetc%2fpasswd"
```

## Забележка

Това не заменя penetration test, SAST/DAST, secret scanning или dependency scanning. То е runtime hardening слой и security contract за production deployment.
