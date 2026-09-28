# SECURITY — TRILOK TRACE

TRILOK TRACE is a defensive prototype; its own security posture matters as much as the
intelligence domain rules. No credentials live in source code — everything comes from
environment variables (see `.env.example`).

## 1. Authentication

- **JWT access tokens** (HS256, configurable expiry, default 30 min) via `PyJWT` with strict claim
  validation (issuer check: `trilok-trace`). No refresh tokens — session expires and user must
  re-authenticate.
- Passwords: **PBKDF2-SHA256** (260,000 iterations, 16-byte salt) using the Python stdlib
  `hashlib` module. No external password-hashing dependency required. Bootstrap demo accounts
  get hashed secrets at seed time; `must_change_password` flag available.
- Login events written to `audit_events` (`auth.*`).

## 2. Authorization (RBAC)

| Capability | analyst | senior_analyst | admin |
|------------|:-------:|:--------------:|:-----:|
| Read intelligence, graph, timeline, reports | ✅ | ✅ | ✅ |
| Create investigations, notes, targets | ✅ | ✅ | ✅ |
| **Review relationships** (accept/reject/uncertain) | – | ✅ | ✅ |
| Create actors/evidence manually | – | ✅ | ✅ |
| Trigger scans / RUN INVESTIGATION | – | ✅ | ✅ |
| Manage analysts, audit log, global weights, resync | – | – | ✅ |

Enforced server-side via FastAPI dependency (`require_role`). UI hides unauthorized actions.

## 3. Input validation & injection defense

- Pydantic v2 schemas validate **every** request body/query — strict types, enum checks.
- All SQL via SQLAlchemy **parameterized statements**; all Cypher via the driver's
  **parameter dictionary** (no f-string interpolation into queries, ever).
- Files (reports uploads) restricted by extension/type/size; downloads served via
  authenticated endpoint with `Content-Disposition`.
- Rate limiting: in-memory per-IP sliding window (120 requests/minute, configurable via
  `RATE_LIMIT_PER_MINUTE`). Returns HTTP 429 with error detail when exceeded. Suitable for
  single-process local mode; production multi-worker deployments should use Redis-backed
  rate limiting.

## 4. Secure headers & transport

- Middleware sets: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, CSP for the SPA.
- HSTS only in `prod`/`demo` behind TLS; dev allows HTTP on localhost.
- CORS restricted to `CORS_ORIGINS` env list (defaults to local dev origins).

## 5. Secrets & configuration

- `.env` gitignored (`.gitignore` present); `docker-compose` reads `${VAR:?}` so missing
  secrets fail fast.
- In local mode, `SECRET_KEY` is auto-generated per process (ephemeral, tokens don't survive
  restarts). Production requires explicit `SECRET_KEY` environment variable.
- No secrets in logs by default; password/token fields are never logged.

## 6. Audit logging

- Append-only `audit_events` (no UPDATE/DELETE at the app layer; DB role has no grant).
- Captured: actor (or `is_system`), action (`auth.login`, `rel.accept`, `investigation.create`,
  `scan.tick`, `report.generate`, `alert.acknowledge`, …), resource, before/after JSON,
  IP, user-agent, note. Analysts must provide a note on relationship review.

## 7. Team access & safe error handling

- API errors never leak stack traces: `request_id` returned, trace to server log only
  (safe-error middleware).
- Data-access checks: analysts only see intelligence their role permits; investigation
  participants list enforced for private notes.
- Demo accounts: `ami` (admin), `amra` (senior_analyst), `tumi` (analyst).

## 8. Container hardening

- Backend runs as non-root; minimal base images (python:3.12-slim; frontend served by
  nginx:alpine). Read-only root FS where practical; separate network for services.
- Neo4j/Postgres ports are **not** published in the demo profile (internal network only);
  developer profile publishes to localhost.

## 9. Threat model summary (for the design review)

| Threat | Mitigation |
|--------|-----------|
| Unauthorized API access | JWT + RBAC dependency on every protected route |
| Credential theft | PBKDF2-SHA256, rate limit, audit |
| Injection (SQL/Cypher/NoSQL) | Parameterized queries everywhere |
| Data exfiltration via reports | RBAC read, download authN, storage_key validation |
| Secret exposure | .env-gitignore, fail-fast env, no secrets in logs |
| Compromised worker | workers hold no admin powers; tasks validate inputs |
| Insider misuse of correlation | relationship review requires senior analyst; audit trail; no real data in demo |

## 10. Verification

Security properties verified: login flow, RBAC matrix (role × endpoint), parameterized
SQLAlchemy queries (no raw SQL), rate limiting (429 on excess), security headers
(X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, HSTS in
production), audit event creation on critical actions, safe error responses (no stack
traces in production mode), `.env` gitignored, non-root Docker user, and dependency
vulnerability scanning (pip-audit + npm audit).
