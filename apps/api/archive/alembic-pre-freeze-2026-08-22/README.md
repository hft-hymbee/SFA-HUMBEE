# Archived Alembic Chain (Pre-freeze)

This directory preserves the Alembic history that was active before the development-phase pivot to
SQL bootstrap files.

## Why archived

- The schema is still changing quickly.
- Disposable development databases are reset often.
- Maintaining forward/backward migration history during this phase adds churn without practical
  value.

## Active workflow now

- Source of truth for executable schema: `apps/api/db/bootstrap/00_extensions.sql` and
  `apps/api/db/bootstrap/01_schema.sql`.
- Regenerate schema SQL from ORM metadata with:

  ```bash
  uv run --project apps/api python apps/api/scripts/export_dev_schema_sql.py
  ```

- Apply bootstrap SQL to a development database with:

  ```bash
  apps/api/scripts/apply_dev_sql_bootstrap.sh
  ```

## Re-introducing migrations later

When schema freeze begins:

1. Generate a clean baseline migration from the stabilized schema.
2. Re-enable Alembic as the primary change mechanism.
3. Keep this archive for historical reference only.
