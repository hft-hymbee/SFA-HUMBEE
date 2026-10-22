# Humbee SFA

Sales-force automation for Humbee: a FastAPI backend, a Next.js web client, and a Capacitor shell
that packages the same web client for Android and iOS.

## Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — runtime boundaries, module topology and principal flows.
- [`DEPLOY.md`](DEPLOY.md) — container build, sandbox and production configuration, secrets, database.
- [`apps/api/README.md`](apps/api/README.md) — backend layout, conventions and local development.
- [`apps/mobile/README.md`](apps/mobile/README.md) — native shell build and store notes.

## Repo layout

```text
apps/
  api/                   FastAPI modular monolith (src/humbee_sfa)
  web/                   Next.js production client (static export)
  mobile/                Capacitor native shell around the apps/web export
  sfa-prototype/         Static visual prototype, not production code
packages/
  api-contract/          Generated OpenAPI contract and TypeScript client
  design-tokens/         Framework-free design tokens
  eslint-config/         Shared lint config and adherence rules
  humbee-design-system/  Shared production UI components
tooling/
  ci/                    CI checks (API baseline, contract drift, web)
  scripts/               Contract generation and breaking-change check
```

## Source rules

- Production code lives in `apps/web` and `apps/api`.
- Reusable UI and tokens live in `packages/humbee-design-system` and `packages/design-tokens`.
- `apps/sfa-prototype` is visual reference only; promote approved patterns into the production apps.

## Commands

```bash
pnpm install
pnpm dev:web
pnpm build:web
pnpm lint:web
pnpm ci:api-baseline
pnpm ci:contract-drift
pnpm ci:web
pnpm api:dev
```

Prototype gallery (`pnpm dev:prototype`):
`http://127.0.0.1:4173/apps/sfa-prototype/ui_kits/humbee-sfa/index.html`
