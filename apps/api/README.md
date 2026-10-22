# apps/api — Humbee SFA backend

FastAPI **modular monolith**: one deployable, thirteen domain modules, with module boundaries
enforced by `import-linter`.

- Architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
- Sandbox and production deployment: [`../../DEPLOY.md`](../../DEPLOY.md)

The schema is managed by Alembic (`migrations/`). The first revision is the baseline schema of the
first production release; every later schema change ships as a new revision.

## Layout

```
src/humbee_sfa/
  main.py              app factory, router registration, lifespan workers
  core/                settings · db · security · deps · clock · business_date · errors
  platform/            audit · domain events · idempotency · rate limits · scheduler · SMS
                       · feature flags · runtime config · telemetry
  modules/             one folder per domain module (see table below)
  integration/humbee/  Humbee client and adapters — the only Humbee-aware package
tests/                 pytest + testcontainers + an in-memory Humbee fake
migrations/            Alembic environment, baseline SQL and revisions
scripts/               local seed and maintenance scripts
```

### Domain modules

Each module owns its tables. Cross-module access goes through the owning module's **service**
interface — never by importing another module's `repository` or `models`.

| Module | Responsibility |
| --- | --- |
| `identity` | Phone + OTP login, sessions, devices |
| `org` | Employees, hierarchy, geography assignment, scope resolution |
| `approvals` | Generic approval engine with per-subject adapters |
| `notifications` | In-app notification feed (no push) |
| `beats` | Beat master, versions, edit requests |
| `routes` | Daily route plans, visits, outcomes, missed-visit audit |
| `attendance` | Punches, GPS fixes, official work |
| `orders` | Carts, submission to Humbee, approval edits, DP SLA |
| `leave` | Leave requests and balances |
| `targets` | Target setting and leads |
| `outlets` | Outlet projection, onboarding and verification |
| `home` | Today composition read |
| `reporting` | Event-derived facts and KPI read models |

### Typical file shape

| File | Holds |
| --- | --- |
| `router.py` | FastAPI routes. Request/response only — no business logic |
| `schemas.py` | Pydantic DTOs (the OpenAPI surface) |
| `service.py` | Use cases, transactions, event emission |
| `repository.py` | Data access, with scope filtering applied here |
| `models/` | SQLAlchemy ORM |
| `policies.py` | Authorisation predicates for the module |
| `events.py` | Domain events the module publishes |

## Conventions

- **No `__init__.py` files** — implicit namespace packages (PEP 420). `setuptools` discovers
  packages via `[tool.setuptools.packages.find] where = ["src"]`.
- **Postgres is the only datastore.** No Redis, no broker — OTP, rate limits, idempotency, domain
  events and scheduler claims are all Postgres tables.
- **No `datetime.now()` in domain logic.** Inject `core.clock` so time windows, the DP SLA and the
  end-of-day sweep are testable.
- **Business date is IST**, derived via `core.business_date` — never a UTC calendar day.
- **Money is integer paise.** Field names state the basis: `*_net_paise` vs `*_gross_paise`.
- **Nothing is hard-deleted.** Soft delete plus an append-only audit row on every transition.

## Boundary enforcement

`pyproject.toml` declares three `import-linter` contracts:

1. Modules must not import another module's `repository` or `models`
2. Only the integration package imports the Humbee client
3. Within a module, layering is `router → service → repository → models`

`lint-imports` fails on any violation.

## Local development

### 1. Start Postgres

```bash
docker run --name humbee-sfa-postgis \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=humbee_sfa \
  -p 5432:5432 \
  -d postgis/postgis:16-3.4-alpine
```

### 2. Configure

Non-secret settings live in YAML; `HUMBEE_SFA_PROFILE` selects the overlay (`local` by default):

- `config/application.yml` — shared defaults
- `config/application-local.yml` — local overlay
- `config/application-sbx.yml` — sandbox overlay
- `config/application-prd.yml` — production overlay

Secrets come from environment variables or `apps/api/.env` (never committed; start from
`apps/api/.env.example`):

- `HUMBEE_SFA_JWT_SECRET`
- `HUMBEE_SFA_PHONE_HMAC_SECRET`
- `HUMBEE_SFA_PHONE_ENC_KEY` (a Fernet key)
- `HUMBEE_SFA_DB_USER` and `HUMBEE_SFA_DB_PASSWORD`, or a full `HUMBEE_SFA_DATABASE_URL`
- `HUMBEE_API_KEY` (no `HUMBEE_SFA_` prefix)

Profile YAML carries the non-secret DB parts (`db_host`, `db_port`, `db_name`, `db_sslmode`,
`db_schema`); the app composes `database_url` when the full URL is omitted.
`application-local.yml` uses the `sfa` schema via `search_path=sfa,public`.

Generate a Fernet key:

```bash
uv run --project apps/api --extra dev python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Migrate and run

```bash
cd apps/api
uv run --extra dev alembic upgrade head
uv run --extra dev python scripts/dev_bootstrap.py
uv run --extra dev humbee-sfa-api
```

After changing a model, add a revision and review it before committing:

```bash
uv run --extra dev alembic revision --autogenerate -m "<change>"
```

`tests/test_migrations.py` fails when the migrations and the models disagree.

`scripts/reconcile_uat_to_baseline.sql` is a one-off for the existing UAT database, which was
created before Alembic. It brings that schema to the baseline so it can be stamped; run it once,
then `alembic stamp head` and `alembic check`, as described in
[`../../DEPLOY.md`](../../DEPLOY.md#database). New databases never need it.

`dev_bootstrap.py` seeds local Admin accounts only; never run it against sandbox or production.
The API listens on port `8001` (`config/application.yml`). The local profile accepts the
`local_otp_override` code from `application-local.yml`.

### 4. Test

```bash
uv run --project apps/api --extra dev pytest -q
uv run --project apps/api --extra dev ruff check src tests
uv run --project apps/api --extra dev lint-imports
```

Tests need Docker (testcontainers starts PostGIS) and use the `test` profile with their own
throwaway secrets; no `.env` is required.

## Deployment

Images, environment variables per profile, secret generation and database setup are in
[`../../DEPLOY.md`](../../DEPLOY.md).
