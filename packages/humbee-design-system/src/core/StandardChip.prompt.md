# StandardChip

Selectable/toggle chip for filters and multi-select. Active state = brown outline + brown text; optional delete cross when active.

```jsx
<StandardChip label="Health Insurance" selected={on} onChange={setOn} showDelete />
```

8px radius (not fully rounded). Controlled via `selected` or uncontrolled via `defaultSelected`.
