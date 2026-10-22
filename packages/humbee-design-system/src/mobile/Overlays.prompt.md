# Overlays

`FAB` (floating primary action, sits above BottomNav; optional extended label) and `BottomSheet` (bottom-anchored modal with grabber). Place inside a positioned screen container.

```jsx
<FAB iconName="Add" label="New order" onClick={start} />
<BottomSheet open={open} onClose={close} title="Log visit outcome">…</BottomSheet>
```
