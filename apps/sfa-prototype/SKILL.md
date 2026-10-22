---
name: humbee-design
description: Use this skill to generate well-branded interfaces and assets for Humbee, either for production or throwaway prototypes/mocks/etc. Humbee is a B2B order & distribution-management platform (purchase orders, dispatch, inventory, invoicing; ₹ pricing). Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.
If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.
If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

## Quick reference
- **Type:** Lato (400/600/700). Labels sit above fields; buttons are never uppercase.
- **Colour:** primary amber-brown `#995A00`; amber accent `#FFA525`; success `#008000`, error `#CC0000`, warning `#FFBF40`, info `#0081F2`. White + light-grey (`#F5F5F5`/`#F7F7F7`) surfaces.
- **Radius:** 8px default (buttons/inputs/cards), 16px pills & modals.
- **Feel:** border-first (hairline `#E5E5E5`), minimal shadow, restrained `0.2s` transitions, dense B2B dashboards. Money in ₹.
- **Icons:** the built-in `Icon` component (registry of Humbee glyphs). No emoji in product UI.

## Files
- `readme.md` — full design guide (content, visual foundations, iconography).
- `styles.css` — link this one file to get all tokens + the Lato webfont.
- Tokens: `packages/design-tokens/src/` — CSS custom properties.
- Components: `packages/humbee-design-system/src/` — React primitives (+ `.prompt.md` each).
- `guidelines/` — foundation specimen cards. `ui_kits/humbee-app/` — full product recreation.
