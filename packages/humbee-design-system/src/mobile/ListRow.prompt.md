# ListRow

The workhorse tappable list row (outlets, orders, requests, menu). Leading icon/avatar · title + subtitle · trailing chip/chevron. ≥56px tall for touch.

```jsx
<ListRow leading={<Icon name="LocationMarker" size={24} color="#995A00" />}
  title="Sunrise Traders" subtitle="MG Road · 2.1 km"
  trailing={<StatusChip status="pending" label="Not visited" />} showChevron onClick={open} />
```
