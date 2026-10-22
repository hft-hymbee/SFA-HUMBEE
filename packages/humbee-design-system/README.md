# Humbee Design System

A React + MUI (v5) component library. This bundle was extracted from the Humbee
application so it can be used standalone. All UI primitives (inputs, buttons,
chips, modals, charts, icons, illustrations) live under `humbee-design-system/`.

## What's in this bundle

```
humbee-design-system/     # The component library
  index.js                # Barrel export — import everything from here
  ComponentShowcase.js    # Live usage examples for every component
  _internal/Capitalize/   # Bundled helper (was an app-level util)
  ...                     # One folder per component group
theme/                    # MUI theme (palette, typography, spacing, radius)
package.json              # Required npm dependencies
README.md                 # This file
```

## Install

```bash
npm install
# (installs react, react-dom, MUI, Emotion, dayjs, amCharts, etc. — see package.json)
```

> The `@amcharts/amcharts5` dependency is only needed if you use the `Chart/`
> components. `styled-components`, `react-icons`, and `prop-types` are each used
> by only a file or two and may be removable — see the `notes` in `package.json`.

## Usage

Components read colors, radius, and typography from the MUI theme at runtime, so
you **must** render them inside a MUI `ThemeProvider` using the bundled theme.

```jsx
import { ThemeProvider, CssBaseline } from '@mui/material';
import theme from './theme'; // the bundled theme/index.js
import { CustomButton, TextField, StatusChip } from './humbee-design-system';

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <CustomButton>Click me</CustomButton>
      <TextField label="Name" />
      <StatusChip status="pending" label="Pending" type="outlined" />
    </ThemeProvider>
  );
}
```

**Import gotcha:** the text-input component is exported as `TextField`
(not `CustomTextField`). Prefer importing from the barrel (`./humbee-design-system`).

## Where to look for examples

- `humbee-design-system/ComponentShowcase.js` — renders every component with props.
- Per-component docs: `Autocomplete/README.md`, `DatePicker/README.md`,
  `TextField/README.md`, `Badge/StatusBadge.README.md`.

## Notes

- Chart components (`humbee-design-system/Chart/*`) are client-only
  (`'use client'`) and depend on amCharts 5.
- `DatePicker` must be wrapped with `LocalizationProvider` +
  `AdapterDayjs` from `@mui/x-date-pickers` at the usage site.
- This is a JavaScript (not TypeScript) library; PropTypes are used in a few places.
