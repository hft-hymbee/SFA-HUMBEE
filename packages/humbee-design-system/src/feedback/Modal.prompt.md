# Modal

Centred modal dialog with a scrim, 16px radius, sticky header (title + close) and optional subtitle.

```jsx
<Modal open={open} onClose={close} title="Confirm dispatch" subtitle="This can't be undone">
  <p>Body…</p>
  <Button label="Confirm" onClick={close} />
</Modal>
```
