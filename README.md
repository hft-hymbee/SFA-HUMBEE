# Humbee

SFA-first monorepo for Humbee product development.

## Canonical docs

- Architecture source of truth: [`docs/architecture/target-architecture.md`](docs/architecture/target-architecture.md)
- SFA screen-flow and product planning: [`docs/plans/HUMBEE-SFA-Screen-Flow-Plan.md`](docs/plans/HUMBEE-SFA-Screen-Flow-Plan.md)

## Repo layout

```text
apps/
  api/              FastAPI modular-monolith lane (src/humbee_sfa)
  mobile/           Capacitor native shell (wraps apps/web static export)
  sfa-prototype/    Visual spec/prototype lane
  web/              Next.js production frontend
packages/
  api-contract/     Generated OpenAPI contract + TS client artifacts
  design-tokens/    Framework-free design tokens
  eslint-config/    Shared lint config and adherence rules
  humbee-design-system/  Shared production UI components
docs/
  architecture/     Canonical architecture and decision register
  features/         Domain/module-level functional specs
  plans/            Product and screen-flow planning docs
  rpi/              Research/plan/implement artifacts
tooling/
  ci/               CI helper scripts
  scripts/          Repo automation scripts
```

## Source-of-truth rules

- Build production product code in `apps/web` and `apps/api`.
- Build reusable UI and tokens in `packages/humbee-design-system` and `packages/design-tokens`.
- Treat `apps/sfa-prototype` as spec/prototype input only; promote approved patterns into production lanes.

Sandbox and production images: [`DEPLOY.md`](DEPLOY.md).

## Commands

```bash
pnpm install
pnpm dev:web
pnpm build:web
pnpm lint:web
pnpm dev:prototype
python3 apps/api/main.py
```

Prototype gallery:
`http://127.0.0.1:4173/apps/sfa-prototype/ui_kits/humbee-sfa/index.html`
