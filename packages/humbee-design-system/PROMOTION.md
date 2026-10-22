# Design-system promotion — status and remaining work

> Read this before adding a production screen. It explains why this package currently holds **two
> implementations** of the design system and what has to happen next.

## What just moved (2026-08-15)

`apps/sfa-prototype/components/` → `packages/humbee-design-system/src/`

That folder was the **source** the prototype's runtime bundle was generated from (confirmed by
`archive/claude-drops/_ds_manifest.json`, which records `sourcePath: "components/core/Badge.jsx"` per
component). Moving it here makes this package the single source of truth.

The critical gain: **the SFA mobile kit is now in a production package.** Every finalized screen is
built from these, and until now `apps/web` could not import any of them.

`src/mobile/` — `AppBar` (TopAppBar + BottomNav), `ApprovalTimeline`, `DateField`, `Feedback`
(Skeleton / SkeletonRow / EmptyState / ErrorState / OfflineBanner / LockBanner), `Gauge`, `ListRow`,
`LocationCaptureCard` (+ MapPreview), `OTPInput`, `Overlays` (FAB + BottomSheet), `PhoneFrame`,
`StatCard`.

Tokens moved in the same pass: `apps/sfa-prototype/tokens/` → `packages/design-tokens/src/`.

## The two implementations — this is the thing to resolve

| | `src/` (just promoted) | `humbee-design-system/` (original) |
| --- | --- | --- |
| Style | Framework-free JSX reading **CSS custom properties** | **MUI v5** components reading the MUI theme |
| Origin | Built for the prototype; token-driven | Extracted from the Humbee core app |
| Mobile/SFA kit | ✅ complete | ❌ absent |
| Consumed by | the prototype bundle | `apps/web` via `index.js` |
| `.d.ts` + `.prompt.md` per component | ✅ | ❌ |

`index.js` still exports **only** the MUI implementation. It has deliberately not been repointed,
because doing so would silently change what `apps/web` renders.

### The decision to make

**Which implementation is production?** Three options, in the order I'd consider them:

1. **`src/` (token-driven) becomes production; MUI is retired.** Best fit for the SFA app — it is what
   the finalized screens were designed against, it is lighter, it has the mobile kit, and the
   adherence lint contract already covers it. Cost: `apps/web` loses MUI primitives it is not yet
   using anyway, and `DatePicker`/charts would need replacements.
2. **Keep MUI for dense Manager/Admin surfaces, `src/` for the SFA mobile shell.** Honest about the
   two audiences, but two systems means two maintenance burdens and a real risk of visual drift.
3. **Port the mobile kit onto MUI.** Highest effort, and it would re-derive components that already
   exist and are already approved.

**Decided: option 1** (2026-08-17) — `src/` is production, MUI is retired.

## Remaining work in Phase 1

1. ~~Decide the above~~ **Decided.** Repoint `index.js` at `src/`.
2. **Generate the MUI theme from `@humbee/design-tokens`** rather than hand-maintaining
   `theme/palette.js` etc. — otherwise the duplication returns.
3. **Regenerate the prototype bundle from this package.** The prototype still loads the pre-built
   `archive/claude-drops/_ds_bundle.js`, which is why moving these sources did not break it. The
   generator is not in the repo — it produced a "claude-drop". Either recover it or replace it with a
   small build script. Until then, `archive/` stays load-bearing for the prototype only, and
   **component edits here will not appear in the prototype gallery.**
4. **Port the ~150 per-component prop rules** from `apps/sfa-prototype/_adherence.oxlintrc.json` into
   `@humbee/eslint-config`. They were generated from the `.d.ts` files, so regenerate rather than copy.
5. **Add Storybook** with 375 / 768 / 1024 / 1440 viewport stories, and visual regression against the
   prototype frames.
6. **Resolve the flagged dead dependencies** — `package.json` `notes` calls out `styled-components`,
   `react-icons` and `prop-types` as possibly-unused.

## Until step 3 is done

- **The prototype gallery remains the visual reference and still works** — it renders from the
  pre-built bundle.
- **Editing `src/` will not change the prototype.** If you need a prototype change, that is a signal
  to prioritise step 3.
- The prototype's `styles.css` now imports tokens from `@humbee/design-tokens`, so **token** changes do
  flow through — but only when the prototype is served from the repository root (which it already
  requires, since its HTML reaches into `archive/`).
