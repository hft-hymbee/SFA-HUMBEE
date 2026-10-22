#!/usr/bin/env bash
set -euo pipefail

test -f "apps/api/pyproject.toml"
test -d "apps/api/src/humbee_sfa"
test -f "packages/api-contract/package.json"

VENV_DIR="${HUMBEE_API_VENV:-.venv-api}"
VENV_PATH="$(pwd)/${VENV_DIR}"
python3 -m venv "${VENV_PATH}"
"${VENV_PATH}/bin/python" -m pip install --upgrade pip >/dev/null
"${VENV_PATH}/bin/python" -m pip install -e "apps/api[dev]" >/dev/null

HUMBEE_API_PYTHON="${VENV_PATH}/bin/python" pnpm --filter @humbee/api-contract run generate

git diff --exit-code -- \
  packages/api-contract/openapi.json \
  packages/api-contract/src/generated

pnpm --filter @humbee/api-contract run check:breaking
pnpm --filter web typecheck

echo "Contract drift checks passed."
