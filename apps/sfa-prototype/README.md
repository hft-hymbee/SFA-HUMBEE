# Humbee Design System

A React + MUI (v5) component library extracted from the **Humbee** application — a
B2B commerce / distribution-management platform (purchase orders, dispatch planning,
inventory, invoicing, buyer onboarding, rewards; pricing in Indian Rupees ₹). This
project re-implements Humbee's visual foundations and UI primitives as framework-free,
token-driven React components so design agents can build on-brand Humbee interfaces.

## Sources

- **Codebase (ground truth):** `Humbee/` mounted folder — a MUI component bundle.
  - `Humbee/theme/` — `palette.js`, `typography.js`, `spacing.js`, `radius.js`, `index.js` (the MUI theme).
  - `Humbee/humbee-design-system/` — one folder per component (Button, TextField, chips, Badge, Modal, SnackBar, Tooltip, Stepper, Bento, Tab, Menu, Select, Checkbox, Radio, ToggleSwitch, QuantityHandler, InlineEditField, IconReusable, Illustrration, Chart, …) plus `ComponentShowcase.js` and `index.js` (barrel).
- **No logo / brand mark** ships in the source. Wherever a mark is needed we set the
  name "Humbee" in Lato Black; see the Brand cards. **Do not fabricate a logo** — replace
  the wordmark placeholder when the official asset is supplied.
- Original stack: React 19, `@mui/material` 5.18, `@mui/x-date-pickers`, `@emotion`,
  `@amcharts/amcharts5` (charts only), `dayjs`, `lottie-react`.

## CONTENT FUNDAMENTALS

How Humbee's product copy reads (drawn from `ComponentShowcase.js`, component labels and READMEs):

- **Voice:** plain, functional, operational B2B SaaS. Describes what a control does, not
  how it feels. E.g. *"Standard text input for inline edit operations. Click the pencil to
  edit, then confirm with the check or discard with the cross."*
- **Person:** neutral/imperative for actions ("Create PO", "Show Success", "Open Modal");
  occasional first-person-plural reassurance in helper text (*"We'll never share your email"*).
- **Casing:** Title Case or sentence case for labels and buttons; **no ALL-CAPS** except the
  tiny `overline` type role (uppercase, 0.5px tracking). Buttons never uppercase
  (`textTransform: none`). Statuses are Title Case ("Pending", "Partially Completed").
- **Domain nouns:** PO / Purchase Order, Dispatch Plan, Inventory, Invoice, Buyer, Beneficiary,
  TDS, Rewards, Secondary Order. Money is ₹ (Indian Rupee, `CurrencyRupee` icon).
- **Tone words:** short, direct, verb-first ("Confirm", "Cancel", "View Details", "Download").
- **Emoji:** not used in product UI. (A few unicode glyphs appear only as *fallback* status
  icons inside StatusBadge, e.g. ✓ ✕ ⚠ — prefer the real SVG icon set instead.)
- **Vibe:** trustworthy, efficient, back-office. Dense data screens, clear states, minimal flourish.

## VISUAL FOUNDATIONS

- **Colour:** a warm amber-brown primary (`#995A00`) is the signature — used for primary
  buttons, active tabs, selected chips/menu items, links. A brighter **amber `#FFA525`** is
  the secondary/accent (secondary buttons, steppers, illustrations). A deep green `#01522B`
  exists in the palette as a secondary brand colour but is used sparingly. Semantic set:
  success `#008000`, error `#CC0000`, warning `#FFBF40`, info `#0081F2`. Backgrounds are
  overwhelmingly white with grey surfaces (`#F5F5F5`, `#F7F7F7`). Max one or two fills per screen.
- **Type:** **Lato** everywhere (the only typeface). Weights 400 / 600 / 700 (Lato lacks a true
  600 — see Caveats). Scale runs display 40 → title 32 → h1 24 → h2 20 → h3 16 → body 16 → 13 → 12.
  Headings 600–700; body 400; labels 700 at 13px sitting **above** fields (not floating).
- **Spacing:** 8px base grid — 4 / 8 / 16 / 24 / 32 / 48.
- **Radius:** 4 / **8 (default)** / 16 / 32. Buttons, inputs, cards, and standard chips are 8px;
  status pills and modals are 16px; switch tracks are fully rounded.
- **Backgrounds:** flat white / light-grey surfaces. **No gradients, no imagery, no textures,
  no patterns.** Illustrations (empty-states) are flat amber line-art SVGs — warm, friendly,
  2-colour (amber + a little black), never photographic.
- **Borders vs shadow:** Humbee is a **border-first** system. Cards use a 1px hairline
  (`#E5E5E5`) with a barely-there shadow; inputs/selects use a 1px `#8C8C8C` border going to
  `#666` on focus. Real shadow appears only on menus (soft `0 2px 8px /.10`), the snackbar,
  and MUI modals. No neumorphism, no glow.
- **Corners / cards:** white, 8px radius, hairline border, optional soft shadow. Not heavily rounded.
- **Animation:** restrained. `all 0.2s ease-in-out` transitions on buttons/chips/steppers;
  switch track `0.3s`; modal slide-up on mobile. No bounces, no spring, no parallax.
- **Hover states:** filled buttons darken (`#995A00`→`#BF7000`); outlined/text buttons gain a
  faint tinted background (5–12% of the colour); icon buttons lighten the icon; menu rows get a
  `#F5F5F5` wash. **Press/active:** buttons darken further (`#663C00`); no scale/shrink.
- **Transparency & blur:** used sparingly — status pills use 10–12% colour tints; the modal
  scrim is `rgba(0,0,0,.5)`; one empty-state illustration uses a backdrop-blur lens. No frosted-glass chrome broadly.
- **Focus:** border-colour shift (to `#666`), not a glowing ring.
- **Layout rules:** dense dashboards via a Bento grid; sticky modal headers; toasts anchored
  top-right. Fixed sidebar + top bar in product shells.

## ICONOGRAPHY

- Humbee ships its **own SVG icon set** (`IconReusable/icons/*`, ~100 glyphs) — Material-Symbols-derived
  line icons on a 24px grid, single-path, `fill` driven (a couple use non-24 viewBoxes: FilterList 18×12, Sort 16×20).
- Rendered via a name-based wrapper (`<IconReusable name="Dashboard" />`). We reproduce this as
  the **`Icon`** component (`packages/humbee-design-system/src/core/Icon.jsx`) with a registry of the ~33 most-used
  glyphs lifted verbatim from source. Read `ICON_NAMES` for the list. This is an **intentional
  addition** (an Icon wrapper over the source glyphs) — see below.
- **Emoji:** not used as product iconography. A handful of unicode symbols (✓ ✕ ⚠ 🎁) appear only
  as StatusBadge fallback icons; prefer real SVG glyphs.
- Domain-specific glyphs are a hallmark: PoOutlined, CreatePoOutlined, DispatchPlanOutlined,
  InvoiceOutlined, PaymentOutlined, InventoryOutlined, RewardsOutlined, CurrencyRupee.
- Flat amber **illustrations** (empty cart, no data, no inventory, delivery truck, approved,
  etc.) live in the source `Illustrration/` folder for empty/success states.

### Intentional additions
- **`Icon`** — a registry-backed glyph renderer mirroring the source `IconReusable`. Needed so
  HTML/React consumers can use Humbee icons without importing ~100 individual React files.

## Components

Grouped React primitives (see each component's `.prompt.md` for usage). Namespace at runtime:
`window.HumbeeDesignSystem_<hash>`.

- **Core:** `Button`, `IconButton`, `Icon`, `StatusChip`, `StandardChip`, `StatusBadge`, `Badge`
- **Forms:** `TextField`, `Select`, `Checkbox`, `Radio` (+ `RadioGroup`), `ToggleSwitch`, `QuantityHandler`, `InlineEditField`
- **Navigation:** `Tabs`, `Menu`
- **Feedback:** `Modal`, `Snackbar`, `Tooltip`, `Stepper`
- **Layout:** `BentoGrid` (+ `BentoItem`), `PaperElevation`
- **Mobile (SFA app shell & field):** `TopAppBar` + `BottomNav` (`AppBar`), `ListRow`, `Skeleton` / `SkeletonRow` / `EmptyState` / `ErrorState` / `OfflineBanner` / `LockBanner` (`Feedback`), `FAB` + `BottomSheet` (`Overlays`), `ApprovalTimeline`, `OTPInput`, `LocationCaptureCard` + `MapPreview`, `Gauge`, `PhoneFrame`, `StatCard`, `DateField`

## Mobile / SFA notes

The **Humbee SFA** (Sales Force Automation) mobile app reuses this system at a 375px viewport.
Field-first components live in `packages/humbee-design-system/src/mobile/`. Rules that keep the SFA screens on-brand:
touch targets ≥ 44px, body text ≥ 15px, one primary action per screen, every empty/error/blocked
state carries a labelled recovery CTA, and status is always visible via `StatusChip` +
`ApprovalTimeline`. The attendance **hard gate** (`LockBanner`) keeps Route & Orders locked until
the SP punches in with GPS. See `ui_kits/humbee-sfa/`.

## Index / manifest

- `styles.css` — global entry (imports every token + font sheet). **Consumers link this one file.**
- Tokens now live in `packages/design-tokens/src/` (`fonts.css`, `colors.css`, `typography.css`, `spacing.css`, `radius.css`, `elevation.css`). `styles.css` re-exports them.
- Components now live in `packages/humbee-design-system/src/{core,forms,navigation,feedback,layout,mobile}/` — `Name.jsx` + `Name.d.ts` + `Name.prompt.md`, one `*.card.html` per folder.
- `guidelines/` — foundation specimen cards (Colors, Type, Spacing, Brand).
- `ui_kits/humbee-app/` — full-screen interactive recreation of the Humbee order-management product.
- `thumbnail.html` — design-system homepage tile.
- `SKILL.md` — Agent-Skills-compatible entry point.

## Caveats

- **Fonts:** the source ships no font binaries. We load **Lato** from Google Fonts. Lato has no
  true 600 weight, so "semibold" (600) is browser-synthesised (renders close to 700). Provide
  `.woff2` files to self-host and to add a real 600.
- **No logo:** brand mark is a Lato wordmark placeholder.
- **Not yet rebuilt from source** (documented, lower-priority families): `DatePicker`,
  `Autocomplete`, `CardCarousel`, `BoxInput`, `Avatar` (source impl is fully commented out),
  and the amCharts-based `Chart` family (`LineTrend`, `StackedColumn`, `ClusteredColumn`,
  `HorizontalBar`). These exist in `Humbee/humbee-design-system/` if needed.
