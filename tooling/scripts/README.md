# tooling/scripts

Place local repo automation scripts here.

Keep scripts small, deterministic, and callable from package scripts or CI workflows.

## Contract scripts

- `generate-openapi.py` — emits `packages/api-contract/openapi.json` from `humbee_sfa.main:create_app`.
- `generate-api-contract-types.mjs` — generates `packages/api-contract/src/generated-types.d.ts` from the committed OpenAPI spec.
- `check-contract-breaking.mjs` — compares the current OpenAPI contract with the base-branch version and fails if paths/required fields/enum values are removed without a `BREAKING CHANGE:` changelog note.
