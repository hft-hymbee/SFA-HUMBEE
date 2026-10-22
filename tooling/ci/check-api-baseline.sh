#!/usr/bin/env bash
set -euo pipefail

test -f "apps/api/pyproject.toml"
test -d "apps/api/src/humbee_sfa"
test -d "apps/api/db/bootstrap"
test -d "apps/api/archive/alembic-pre-freeze-2026-08-22/alembic"
test -d "apps/api/tests"

VENV_DIR="${HUMBEE_API_VENV:-.venv-api}"
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip >/dev/null
"${VENV_DIR}/bin/python" -m pip install -e "apps/api[dev]" >/dev/null

"${VENV_DIR}/bin/python" -m compileall "apps/api/src/humbee_sfa" >/dev/null
"${VENV_DIR}/bin/python" -m pytest "apps/api/tests"
"${VENV_DIR}/bin/lint-imports" --config "apps/api/pyproject.toml"

echo "API baseline checks passed."
