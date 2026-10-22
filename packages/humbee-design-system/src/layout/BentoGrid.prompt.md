# BentoGrid

Dashboard bento layout. `gap` is in 8px units. Use BentoItem `colSpan` for wide cells (grid mode); set `masonry` for a CSS-columns flow.

```jsx
<BentoGrid column={4} gap={2}>
  <BentoItem colSpan={2}><PaperElevation>Chart</PaperElevation></BentoItem>
  <BentoItem><PaperElevation>Metric</PaperElevation></BentoItem>
</BentoGrid>
```
