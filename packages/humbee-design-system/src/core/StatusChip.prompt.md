# StatusChip

Status pill for records (orders, POs, KYC). Colour is driven by `status`; `type` picks outlined / filled / text.

```jsx
<StatusChip status="pending" label="Pending" type="outlined" />
<StatusChip status="completed" label="Completed" type="filled" />
```

16px radius. outlined = 10% tint + coloured border + dark text; filled = solid colour + white text.
