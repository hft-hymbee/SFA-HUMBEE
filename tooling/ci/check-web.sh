#!/usr/bin/env bash
set -euo pipefail

test -f "apps/web/package.json"

pnpm --filter web lint
pnpm --filter web typecheck
NEXT_PUBLIC_SFA_API_BASE_URL="${NEXT_PUBLIC_SFA_API_BASE_URL:-https://api.example.invalid}" pnpm --filter web build

echo "Web checks passed."
