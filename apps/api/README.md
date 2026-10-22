# apps/api — Humbee SFA backend

FastAPI **modular monolith**: one deployable, twelve bounded contexts with boundaries enforced in CI.

- Architecture: [`../../docs/architecture/target-architecture.md`](../../docs/architecture/target-architecture.md) §3
- Decisions: [`../../docs/architecture/target-architecture.md` §7](../../docs/architecture/target-architecture.md#7-owner-decision-register-v1) (owner-managed v1 decision register)
- Functional specs: [`../../docs/features/`](../../docs/features/) — one doc per module

> **Status: active dev bootstrap mode.** During high-change development, database provisioning is
> SQL-first (`db/bootstrap/*.sql`). The previous Alembic chain is preserved under
> `archive/alembic-pre-freeze-2026-08-22/` and will be replaced by a clean baseline when schema
> freeze starts.

## Layout

```
src/humbee_sfa/
  main.py              app factory + router registration
  core/                config · db · security · deps · errors · pagination
                       · idempotency · clock · business_date
  platform/            events · outbox · jobs · audit · cache · telemetry
  modules/             one folder per bounded context (see table below)
  integration/humbee/  the anti-corruption layer — the ONLY Humbee-aware package
    client/ mappers/ resilience/ sync/
tests/                 pytest + testcontainers + a fake Humbee
db/bootstrap/          executable SQL bootstrap (extensions + schema)
archive/alembic-*/     archived migration history (not active in dev mode)
```

### Bounded contexts

Each owns its tables. Cross-module access goes through the owning module's **service** interface —
never by importing another module's `repository` or `models`.

| Module | Modules covered | Spec |
| --- | --- | --- |
| `identity` | M2 — phone+OTP, sessions, devices | [M02](../../docs/features/M02-identity-and-session.md) |
| `org` | M3/M4 — employees, hierarchy, geography assignment, **ScopeResolver** | [M03](../../docs/features/M03-org-workforce-and-geography.md) |
| `approvals` | M6 — the generic polymorphic engine | [M06](../../docs/features/M06-approvals-and-notifications.md) |
| `beats` | M7 | [M07](../../docs/features/M07-beats.md) |
| `routes` | M8 — route plans, visits, outcomes, missed-visit audit | [M08](../../docs/features/M08-routes-and-visits.md) |
| `attendance` | M9 — punch, GPS fixes, official work | [M09](../../docs/features/M09-attendance-and-official-work.md) |
| `orders` | M10 — drafts, submission, outbox to Humbee, DP SLA | [M10](../../docs/features/M10-orders.md) |
| `leave` | M12 | [M12](../../docs/features/M12-leave.md) |
| `targets` | M13 — target setting, leads | [M13](../../docs/features/M13-targets-and-leads.md) |
| `outlets` | M14 — onboarding, verification, outlet projection | [M14](../../docs/features/M14-outlet-onboarding-and-insights.md) |
| `reporting` | M11 — rollups, KPI read models | [M11](../../docs/features/M11-reporting-and-dashboards.md) |
| `notifications` | S-NOTIF — **in-app only, no push** | [M06](../../docs/features/M06-approvals-and-notifications.md) |

### File shape per module

Uniform across all twelve, so a new engineer or agent can navigate any of them:

| File | Holds |
| --- | --- |
| `router.py` | FastAPI routes. Request/response only — no business logic |
| `schemas.py` | Pydantic DTOs (the OpenAPI surface) |
| `service.py` | Use cases, transactions, event emission — **the only place rules live** |
| `repository.py` | Data access. **All scope filtering applied here** |
| `models.py` | SQLAlchemy ORM |
| `policies.py` | Authorisation predicates for this context |
| `events.py` | Domain events this context publishes |

## Conventions

- **No `__init__.py` files** — this repo uses implicit namespace packages (PEP 420). `setuptools`
  discovers packages via `[tool.setuptools.packages.find] where = ["src"]`.
- **Postgres is the only datastore.** No Redis, no broker — OTP, rate limits, idempotency, the Humbee
  cache, the outbox and the job queue are all Postgres tables ([decision D-003](../../docs/architecture/target-architecture.md#71-decided)).
- **No `datetime.now()`** anywhere. Inject `core.clock` so the 9–6 window, the 1-hour DP SLA and the
  end-of-day sweep are testable.
- **Business date is IST**, derived via `core.business_date` — never a UTC calendar day.
- **Money is integer paise.** Field names state the basis: `net_value_paise` vs `gross_value_paise`.
- **Nothing is hard-deleted.** Soft delete plus an append-only audit row on every transition.

## Boundary enforcement

`pyproject.toml` declares three `import-linter` contracts:

1. Modules must not import another module's `repository` or `models`
2. Only the ACL imports the Humbee client
3. Within a module, layering is `router → service → repository → models`

CI runs `lint-imports`. A violation fails the build — this is what makes "modular monolith" real
rather than aspirational.

## Run Identity Slice Locally

This slice is Postgres-only for local development.

### 1) Start Postgres in Docker

```bash
docker run --name humbee-sfa-postgis \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=humbee_sfa \
  -p 5432:5432 \
  -d postgis/postgis:16-3.4-alpine
```

### 2) Configure local secrets and non-secret profile config

Copy the secrets template and fill real local secrets:

```bash
cp apps/api/.env.example apps/api/.env
```

Required secret values:

- `HUMBEE_SFA_JWT_SECRET`
- `HUMBEE_SFA_PHONE_HMAC_SECRET`
- `HUMBEE_SFA_PHONE_ENC_KEY`
- `HUMBEE_SFA_DB_USER` and `HUMBEE_SFA_DB_PASSWORD` (when using split DB config instead of full `database_url`)

Non-secret config lives in:

- `apps/api/config/application.yml` — shared defaults
- `apps/api/config/application-local.yml` — local overlay
- `apps/api/config/application-sbx.yml` — sandbox overlay
- `apps/api/config/application-prd.yml` — production overlay

`database_url` can still be provided directly, but profile YAML may now carry non-secret DB
parts (`db_host`, `db_port`, `db_name`, `db_sslmode`, `db_schema`) while `.env` carries
`HUMBEE_SFA_DB_USER` and `HUMBEE_SFA_DB_PASSWORD`. The app composes `database_url`
automatically when the full URL is omitted.
`application-local.yml` defaults to the `sfa` schema via `search_path=sfa,public`.
Set `HUMBEE_SFA_PROFILE=sbx` or `HUMBEE_SFA_PROFILE=prd` to select another overlay.

Generate a Fernet key for `HUMBEE_SFA_PHONE_ENC_KEY`:

```bash
uv run --project apps/api --extra dev python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

$env:HUMBEE_SFA_PROFILE="sbx"; uv run --project apps/api --extra dev humbee-sfa-api
```

### 3) Bootstrap schema and seed data

```bash
uv run --project apps/api --extra dev python apps/api/scripts/export_dev_schema_sql.py
apps/api/scripts/apply_dev_sql_bootstrap.sh
uv run --project apps/api --extra dev python apps/api/scripts/dev_bootstrap.py
uv run --project apps/api --extra dev humbee-sfa-api
```

### 4) Run tests without bypasses

Tests load non-secret config from YAML and secrets from `apps/api/.env` or real
`HUMBEE_SFA_*` environment variables. Run:

```bash
uv run --project apps/api --extra dev pytest -q
```

The bootstrap script seeds:
- admin: `+919845003300`
- active sales person: `+919845003210`
- inactive sales person: `+919845003211`
- manager contact: `+919845003299`
- Manager of Maya Manager: '9876543211'
- Manager of Maya Manager: '9876543212'
- Iron Man: '9876543219'
- Avengers: '9876543218'
- Spider Man: '9876543210'

With the server running on `:8000`, exercise the identity/session slice:

```bash
curl :8000/api/v1/auth/config
curl -X POST :8000/api/v1/auth/otp/request -H 'Idempotency-Key: r1' -H 'Content-Type: application/json' \
  -d '{"phone_e164":"+919845003210","purpose":"login","client_device_id":"dev-device-1"}'
# copy OTP from [dev-sms] stdout line
curl -X POST :8000/api/v1/auth/otp/verify -H 'Idempotency-Key: v1' -H 'Content-Type: application/json' \
  -d '{"challenge_id":"<challenge_id>","code":"<otp>","purpose":"login","client_device_id":"dev-device-1","platform":"web_pwa","app_version":"dev"}'
# copy access_token / refresh_token
curl :8000/api/v1/me -H 'Authorization: Bearer <access_token>'
curl :8000/api/v1/auth/session -H 'Authorization: Bearer <access_token>'
curl -X POST :8000/api/v1/auth/token/refresh -H 'Idempotency-Key: rf1' -H 'Content-Type: application/json' \
  -d '{"refresh_token":"<refresh_token>","client_device_id":"dev-device-1"}'
curl -X POST :8000/api/v1/auth/logout -H 'Idempotency-Key: lo1' -H 'Content-Type: application/json' \
  -d '{"refresh_token":"<refresh_token>"}'
```

Deactivated flow:
- request OTP using `+919845003211`
- verify returns `403 account_deactivated`
- fetch manager contact with:
  `curl ':8000/api/v1/auth/manager-contact?challenge_id=<challenge_id>'`


$env:HUMBEE_SFA_PROFILE="sbx"; uv run --project apps/api --extra dev humbee-sfa-api

netstat -ano | findstr :8000
taskkill /PID <PID> /F
## Deployment secrets (Docker: prd / sbx)

Images: `apps/api/Dockerfile` (build context `apps/api`) and `apps/web/Dockerfile` (build context
repo root). Non-secret settings come from `config/application-{profile}.yml`; everything below is
supplied by the platform's secret store as environment variables. Environment variables override
YAML. Never bake them into the image or commit them.

### API container — runtime environment

| Variable | prd | sbx | Notes |
| --- | --- | --- | --- |
| `HUMBEE_SFA_PROFILE` | `prd` | `sbx` | Not secret. Selects `application-{profile}.yml`. Image default is `prd`. |
| `HUMBEE_SFA_JWT_SECRET` | required | required | Random ≥ 32 bytes, different per env. Rotating invalidates issued access tokens. |
| `HUMBEE_SFA_PHONE_HMAC_SECRET` | required | required | Phone lookup hash key. Different per env; do **not** change once data exists (existing phone lookups stop matching). |
| `HUMBEE_SFA_PHONE_ENC_KEY` | required | required | Fernet key (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`). Do **not** change once data exists (stored phones become undecryptable). |
| `HUMBEE_SFA_DB_USER` | required | required | Postgres user. |
| `HUMBEE_SFA_DB_PASSWORD` | required | required | Postgres password. |
| `HUMBEE_API_KEY` | required | required | Humbee core API key. Note: **no** `HUMBEE_SFA_` prefix. App refuses to start without it. |
| `HUMBEE_SFA_OTP_SMS_USERNAME` | required | optional | Telsp SMS gateway. sbx skips OTP delivery (`otp_skip_verification: true`). |
| `HUMBEE_SFA_OTP_SMS_API_KEY` | required | optional | Telsp SMS gateway. |
| `HUMBEE_SFA_DB_HOST` | **required** | — | `application-prd.yml` only has the `<prd-db-endpoint>` placeholder. sbx host is in YAML. |
| `HUMBEE_SFA_HUMBEE_BASE_URL` | **required** | — | Missing from `application-prd.yml` (blocked on B6); app refuses to start without an `https` URL. sbx uses `https://api-dev.humbee.in` from YAML. |
| `FORWARDED_ALLOW_IPS` | set | set | Not secret. Uvicorn only trusts `X-Forwarded-For` from these IPs; set it to the load balancer / VPC CIDR, otherwise every request appears to come from the LB and the per-IP OTP rate limit blocks all users. |

Alternatively set `HUMBEE_SFA_DATABASE_URL` (full SQLAlchemy URL) instead of the `DB_*` variables.

Never set in prd: `HUMBEE_SFA_OTP_SKIP_VERIFICATION`, `HUMBEE_SFA_LOCAL_OTP_OVERRIDE` (startup
validation rejects both outside sbx/test).

### Web image — build arguments

| Build arg | prd | sbx | Notes |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_SFA_API_BASE_URL` | prd API URL | sbx API URL | **Public, not a secret** — inlined into the static bundle at build time, so build one image per env. |
| `NEXT_PUBLIC_APP_VERSION` | optional | optional | Defaults to `1.0.0`. |

The web image contains no secrets; do not pass any secret as a `NEXT_PUBLIC_*` build arg.
