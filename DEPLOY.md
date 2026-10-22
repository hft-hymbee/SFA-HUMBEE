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
| Health | `GET /health` | `GET /` |
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
  -e FORWARDED_ALLOW_IPS=<lb-or-vpc-cidr> \
  -p 8001:8001 \
  humbee-sfa-api

docker run --rm \
  --env-file <prd-secrets.env> \
  -e HUMBEE_SFA_PROFILE=prd \
  -e HUMBEE_SFA_DB_HOST=<prd-db-endpoint> \
  -e HUMBEE_SFA_HUMBEE_BASE_URL=https://<prd-humbee-api> \
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
| `FORWARDED_ALLOW_IPS` | set | set |

`HUMBEE_API_KEY` has no `HUMBEE_SFA_` prefix. The process refuses to start without it, and without an absolute `https` Humbee base URL.

`HUMBEE_SFA_DATABASE_URL` may replace the `DB_*` variables. It must be a full SQLAlchemy URL.

Generate keys once per environment and keep them stable after data exists:

```bash
openssl rand -base64 32
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use a distinct JWT secret and a distinct phone HMAC secret per environment. Rotating `HUMBEE_SFA_JWT_SECRET` invalidates issued access tokens. Changing `HUMBEE_SFA_PHONE_HMAC_SECRET` makes existing phone lookups miss. Changing `HUMBEE_SFA_PHONE_ENC_KEY` makes stored phone numbers undecryptable. The Fernet command is the phone encryption key.

## Profile behavior

Sandbox (`apps/api/config/application-sbx.yml`):

- Postgres host, name `humbee_sfa`, SSL `require`, schema `sfa` are in YAML. Credentials stay in the environment.
- `otp_skip_verification` is true, so SMS gateway credentials are optional.
- Humbee base URL is `https://api-dev.humbee.in`.

Production (`apps/api/config/application-prd.yml`):

- `db_host` is the placeholder `<prd-db-endpoint>`. Set `HUMBEE_SFA_DB_HOST`.
- Humbee has not published a production base URL yet. Set `HUMBEE_SFA_HUMBEE_BASE_URL` to that `https` URL when it exists. Startup fails while it is empty.
- OTP verification is on. Set both Telsp variables: `HUMBEE_SFA_OTP_SMS_USERNAME` and `HUMBEE_SFA_OTP_SMS_API_KEY`.
- Do not set `HUMBEE_SFA_OTP_SKIP_VERIFICATION` or `HUMBEE_SFA_LOCAL_OTP_OVERRIDE`. Startup rejects both outside sbx and test.

## Database

A new database needs `apps/api/db/bootstrap/00_extensions.sql`, then `apps/api/db/bootstrap/01_schema.sql`, applied with that environment's credentials. Postgres is the only datastore.

Do not run `apps/api/scripts/dev_bootstrap.py` against sbx or prd. That script seeds local identity rows.

## Check

```bash
curl -fsS http://127.0.0.1:8001/health
curl -fsS -o /dev/null http://127.0.0.1:8080/
```

API `/health` runs `SELECT 1`. `200` and `{"status":"ok","database":"ok"}` means the process and the database are up. `503` means the database is unreachable.
