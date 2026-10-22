# Dev SQL Bootstrap

This directory is the active database provisioning mechanism during rapid development.

## Files

- `00_extensions.sql` — required PostgreSQL extensions.
- `01_schema.sql` — generated schema snapshot from current ORM metadata.

## Regenerate schema SQL

```bash
uv run --project apps/api --extra dev python apps/api/scripts/export_dev_schema_sql.py
```

## Apply to a database

```bash
apps/api/scripts/apply_dev_sql_bootstrap.sh
```

The script reads `database_url` from the active API profile config. Set
`HUMBEE_SFA_DATABASE_URL` only when you need to override that value for a one-off target.
