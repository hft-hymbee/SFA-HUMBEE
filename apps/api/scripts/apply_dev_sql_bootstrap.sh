#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)
EXTENSIONS_SQL="$REPO_ROOT/apps/api/db/bootstrap/00_extensions.sql"
SCHEMA_SQL="$REPO_ROOT/apps/api/db/bootstrap/01_schema.sql"

test -f "$EXTENSIONS_SQL"
test -f "$SCHEMA_SQL"

if [[ -z "${HUMBEE_SFA_DATABASE_URL:-}" ]]; then
  HUMBEE_SFA_DATABASE_URL=$(
    uv run --project "$REPO_ROOT/apps/api" --extra dev python - <<'PY'
from humbee_sfa.core.settings import get_settings

print(get_settings().database_url)
PY
  )
fi

psql "$HUMBEE_SFA_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$EXTENSIONS_SQL"
psql "$HUMBEE_SFA_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$SCHEMA_SQL"

echo "Dev SQL bootstrap applied."
