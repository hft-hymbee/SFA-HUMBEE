# @humbee/api-contract

The API contract shared by `apps/api` and `apps/web`. **Generated, never hand-written.**

## Contract-first workflow

1. Update FastAPI schemas/routes in `apps/api`.
2. Regenerate contract artifacts:
   ```bash
   pnpm --filter @humbee/api-contract run generate
   ```
3. Review changes in:
   - `packages/api-contract/openapi.json`
   - `packages/api-contract/src/generated-types.d.ts`
4. If any path/required field/enum is removed, add a `BREAKING CHANGE:` note under `## Unreleased` in `CHANGELOG.md`.
5. Commit the API and contract changes together.

## Commands

From repo root:

```bash
pnpm --filter @humbee/api-contract run generate
pnpm --filter @humbee/api-contract run build
pnpm --filter @humbee/api-contract run check
pnpm --filter @humbee/api-contract run check:breaking
```

## CI gates

- `tooling/ci/check-contract-drift.sh` regenerates contract artifacts and fails on drift.
- `check:breaking` compares current vs base-branch contract and enforces a changelog entry for breaking changes.

## Ownership rules

1. Do not hand-edit generated contract artifacts.
2. `apps/web` consumes types/client from this package as a workspace dependency.
3. Breaking contract changes require both consumer migration notes and a changelog entry.
