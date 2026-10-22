# Deploy

Container contract for sandbox (`sbx`) and production (`prd`). Run every command from the repo root.

The API image is the same for both environments. `HUMBEE_SFA_PROFILE` selects `apps/api/config/application-{profile}.yml` at start. The image default is `prd`, so a sandbox task must set the profile or it will boot as production.

The web image has no runtime configuration. `NEXT_PUBLIC_SFA_API_BASE_URL` is inlined at build time, so build one web image per environment. Do not pass secrets as `NEXT_PUBLIC_*` build arguments.

Non-secret settings live in YAML. Secrets come from the platform secret store as environment variables and override YAML. Do not bake secrets into an image or commit them.

| | API | Web |
| --- | --- | --- |
| Dockerfile | `apps/api/Dockerfile` | `apps/web/Dockerfile` |
| Build context | `apps/api` | repo root |
| Listen | `8001` | `8080` |
| Liveness | `GET /livez` | `GET /` |
| Readiness | `GET /health` (checks the database) | `GET /` |
| Process user | `uid 10001` | nginx unprivileged |

## Build

```bash
docker build -t humbee-sfa-api apps/api

docker build -f apps/web/Dockerfile \
  --build-arg NEXT_PUBLIC_SFA_API_BASE_URL=https://<sbx-api-host> \
  --build-arg NEXT_PUBLIC_APP_VERSION=<release> \
  -t humbee-sfa-web:sbx .

docker build -f apps/web/Dockerfile \
  --build-arg NEXT_PUBLIC_SFA_API_BASE_URL=https://<prd-api-host> \
  --build-arg NEXT_PUBLIC_APP_VERSION=<release> \
  -t humbee-sfa-web:prd .
```

`NEXT_PUBLIC_APP_VERSION` defaults to `1.0.0` when omitted.

## Run

`<sbx-secrets.env>` and `<prd-secrets.env>` are platform secret files. They are not in this repo.

```bash
docker run --rm \
  --env-file <sbx-secrets.env> \
  -e HUMBEE_SFA_PROFILE=sbx \
  -e HUMBEE_SFA_CORS_WEB_ORIGINS='["https://<sbx-web-host>"]' \
  -e FORWARDED_ALLOW_IPS=<lb-or-vpc-cidr> \
  -p 8001:8001 \
  humbee-sfa-api

docker run --rm \
  --env-file <prd-secrets.env> \
  -e HUMBEE_SFA_PROFILE=prd \
  -e HUMBEE_SFA_DB_HOST=<prd-db-endpoint> \
  -e HUMBEE_SFA_HUMBEE_BASE_URL=https://<prd-humbee-api> \
  -e HUMBEE_SFA_CORS_WEB_ORIGINS='["https://<prd-web-host>"]' \
  -e FORWARDED_ALLOW_IPS=<lb-or-vpc-cidr> \
  -p 8001:8001 \
  humbee-sfa-api

docker run --rm -p 8080:8080 humbee-sfa-web:sbx
docker run --rm -p 8080:8080 humbee-sfa-web:prd
```

`FORWARDED_ALLOW_IPS` is the load balancer or VPC CIDR. Uvicorn trusts `X-Forwarded-For` only from those addresses. Leave it unset and every request looks like it came from the load balancer, so the per-IP OTP rate limit applies to all users at once.

## API environment

| Variable | sbx | prd |
| --- | --- | --- |
| `HUMBEE_SFA_PROFILE` | `sbx` | `prd` |
| `HUMBEE_SFA_JWT_SECRET` | required | required |
| `HUMBEE_SFA_PHONE_HMAC_SECRET` | required | required |
| `HUMBEE_SFA_PHONE_ENC_KEY` | required | required |
| `HUMBEE_SFA_DB_USER` | required | required |
| `HUMBEE_SFA_DB_PASSWORD` | required | required |
| `HUMBEE_API_KEY` | required | required |
| `HUMBEE_SFA_OTP_SMS_USERNAME` | optional | required |
| `HUMBEE_SFA_OTP_SMS_API_KEY` | optional | required |
| `HUMBEE_SFA_DB_HOST` | in `application-sbx.yml` | required |
| `HUMBEE_SFA_HUMBEE_BASE_URL` | `https://api-dev.humbee.in` in YAML | required |
| `HUMBEE_SFA_CORS_WEB_ORIGINS` | required | required |
| `FORWARDED_ALLOW_IPS` | set | set |

`HUMBEE_API_KEY` has no `HUMBEE_SFA_` prefix. The process refuses to start without it, and without an absolute `https` Humbee base URL.

`HUMBEE_SFA_DATABASE_URL` may replace the `DB_*` variables. It must be a full SQLAlchemy URL, and it must carry `options=-csearch_path%3Dsfa%2Cpublic` itself; the `DB_*` form adds that automatically.

`HUMBEE_SFA_CORS_WEB_ORIGINS` is a JSON list of the web app's origins, for example `["https://sfa.example.com"]`. Startup fails in sbx and prd when it is empty. The mobile app origins (`https://localhost` for Android, `capacitor://localhost` for iOS) are already allowed by `application.yml`. A browser on any other origin is refused.

`apps/api/.env.example` lists the variable names for local development.

Generate keys once per environment and keep them stable after data exists:

```bash
openssl rand -base64 32
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use a distinct JWT secret and a distinct phone HMAC secret per environment. Rotating `HUMBEE_SFA_JWT_SECRET` invalidates issued access tokens. Changing `HUMBEE_SFA_PHONE_HMAC_SECRET` makes existing phone lookups miss. Changing `HUMBEE_SFA_PHONE_ENC_KEY` makes stored phone numbers undecryptable. The Fernet command is the phone encryption key.

## Profile behavior

Sandbox (`apps/api/config/application-sbx.yml`):

- Postgres host, name `humbee_sfa`, SSL `require`, schema `sfa` are in YAML. Credentials stay in the environment.
- `otp_skip_verification` is true: any OTP code is accepted and SMS gateway credentials are optional.
- Humbee base URL is `https://api-dev.humbee.in`.
- API docs are served at `/docs`, `/redoc` and `/openapi.json`.

Production (`apps/api/config/application-prd.yml`):

- `db_host` is the placeholder `<prd-db-endpoint>`. Set `HUMBEE_SFA_DB_HOST`.
- Humbee has not published a production base URL yet. Set `HUMBEE_SFA_HUMBEE_BASE_URL` to that `https` URL when it exists. Startup fails while it is empty.
- OTP verification is on. Set both Telsp variables: `HUMBEE_SFA_OTP_SMS_USERNAME` and `HUMBEE_SFA_OTP_SMS_API_KEY`.
- OTP verification is on. Startup fails when either Telsp variable is missing.
- Do not set `HUMBEE_SFA_OTP_SKIP_VERIFICATION` or `HUMBEE_SFA_LOCAL_OTP_OVERRIDE`. Startup rejects both in prd.
- API docs (`/docs`, `/redoc`, `/openapi.json`) are off.

## Database

Postgres with PostGIS is the only datastore. The schema is managed by Alembic (`apps/api/migrations`), and the API image carries the migrations. Run them as a one-off task with the same image and environment as the API, before starting a new release:

```bash
docker run --rm --env-file <prd-secrets.env> -e HUMBEE_SFA_PROFILE=prd -e HUMBEE_SFA_DB_HOST=<prd-db-endpoint> humbee-sfa-api alembic upgrade head
```

- **New database:** the first `upgrade head` applies the baseline: it installs the `postgis`, `btree_gist`, `ltree` and `pgcrypto` extensions, creates the `sfa` schema and creates every table. Installing `postgis` needs a superuser (`rds_superuser` on RDS); run the first upgrade with such a role, or create the extensions beforehand.
- **Existing UAT database:** it predates Alembic and differs from the baseline in a few indexes and leftover objects. Bring it level once, then record it as current and verify:

  ```bash
  psql "<uat-connection-string>" -f apps/api/scripts/reconcile_uat_to_baseline.sql
  docker run --rm --env-file <sbx-secrets.env> -e HUMBEE_SFA_PROFILE=sbx humbee-sfa-api alembic stamp head
  docker run --rm --env-file <sbx-secrets.env> -e HUMBEE_SFA_PROFILE=sbx humbee-sfa-api alembic check
  ```

  `alembic check` must print `No new upgrade operations detected.` Never run `upgrade` before `stamp` on this database.
- **Later releases:** each release ships its migrations; run `alembic upgrade head` before switching traffic. Keep migrations backward compatible with the previous image so a rollback to it stays possible.
- Take a snapshot before every migration and keep point-in-time recovery on.

## First Admin

A new database has no users. Create the first Admin with the API key, then sign in with that phone number and create everyone else in the app:

```bash
curl -fsS -X POST https://<api-host>/api/v1/org/admins \
  -H "api-key: $HUMBEE_API_KEY" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"employee_code":"ADM-001","full_name":"<name>","phone_e164":"+91<number>"}'
```

Do not run `apps/api/scripts/dev_bootstrap.py` against sbx or prd. It seeds local accounts.

## Runtime

- Run two or more API replicas. The end-of-day sweep and the reporting projector run inside every replica and elect one leader through Postgres advisory locks.
- Advisory locks need session-level connections: connect directly or through session-mode pooling. Transaction-mode PgBouncer breaks the leader election.
- Give each task a stop grace period of at least 60 seconds so the sweep worker can finish.
- Point the load balancer health check at `/health` (readiness). The container `HEALTHCHECK` uses `/livez`, so a short database outage does not restart healthy containers.
- Terminate TLS at the load balancer; the API and web containers speak plain HTTP inside the VPC.

## Mobile

The Android and iOS apps bundle the web export, so the API URL is fixed at build time, as for the web image. Build each environment's app with its own URL:

```bash
NEXT_PUBLIC_SFA_API_BASE_URL=https://<prd-api-host> NEXT_PUBLIC_APP_VERSION=<release> pnpm --dir apps/web build
pnpm --dir apps/mobile sync
```

Then build and sign in Android Studio or Xcode with the client's signing keys. See `apps/mobile/README.md`.

## Check

```bash
curl -fsS http://127.0.0.1:8001/livez
curl -fsS http://127.0.0.1:8001/health
curl -fsS -o /dev/null http://127.0.0.1:8080/
```

`/livez` answers `200` whenever the process is up. `/health` runs `SELECT 1`: `200` and `{"status":"ok","database":"ok"}` means the process and the database are up, and `503` means the database is unreachable.
