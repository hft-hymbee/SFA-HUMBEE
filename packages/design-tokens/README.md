# @humbee/design-tokens

**The single source of truth for Humbee's visual foundations.** Framework-free: CSS custom properties
plus a JSON export. Everything else — the MUI theme, the prototype's stylesheets, Storybook, any
future native shell — is generated from or consumes this.

> **Status: CSS tokens moved in (2026-08-15).** Migrated from `apps/sfa-prototype/tokens/`, which is
> now gone — this package is the single source. `apps/sfa-prototype/styles.css` imports
> `src/index.css` from here, so the prototype consumes these tokens rather than its own copy.

## Current contents

```
src/
  index.css        canonical entry — @imports the five sheets below. Consumers link this one file.
  fonts.css        Lato webfont
  colors.css       brand · semantic · surface · text
  typography.css   the display 40 → 12 scale
  spacing.css      8px base grid
  radius.css       4 / 8 / 16 / 32
  elevation.css    the restrained shadow set
```

## Why this package exists

The same tokens previously existed twice — in the prototype and in
`packages/humbee-design-system/theme/` — with a third copy baked into
`archive/claude-drops/_ds_bundle.js`. A colour change needed three edits, so drift was guaranteed.
Tokens also have to be consumable by non-React
things, which is why they live here rather than inside the component package.

## Still to do

1. **Generate the MUI theme from these tokens.** `packages/humbee-design-system/theme/`
   (`palette.js`, `typography.js`, `spacing.js`, `radius.js`) is still hand-maintained — until it is
   generated from here, the duplication returns. Where the two disagree, **these values win** (the
   prototype is the finalized visual spec); the theme's *structure* is what MUI needs.
2. **Add a `tokens.json` export** so the theme build, docs and lint rules read machine-readable values
   rather than parsing CSS.
3. **Regenerate the prototype's DS bundle** so component changes flow through too — see
   [`../humbee-design-system/PROMOTION.md`](../humbee-design-system/PROMOTION.md).

## Brand invariants these tokens must encode

From the design-system README — do not drift from these:

- **Type:** Lato only. Weights 400 / 600 / 700 (no true 600; browser-synthesised). Labels sit **above** fields. Buttons never uppercase.
- **Colour:** primary `#995A00`, accent `#FFA525`; success `#008000`, error `#CC0000`, warning `#FFBF40`, info `#0081F2`. White/light-grey surfaces, max 1–2 fills per screen.
- **Radius:** 4 / **8 (default)** / 16 (pills, modals) / 32.
- **Spacing:** 8px base grid — 4 / 8 / 16 / 24 / 32 / 48.
- **Border-first:** hairline `#E5E5E5` on cards, minimal shadow, `0.2s` transitions. No gradients, imagery or textures.

## The adherence contract

`apps/sfa-prototype/_adherence.oxlintrc.json` already machine-checks that no raw hex, no raw px and
no non-Lato font reaches the prototype. **Port those rules into
`packages/eslint-config` so `apps/web` is held to the same standard** — this is one of the genuinely
good things already in the repo, and it only works if production inherits it.
