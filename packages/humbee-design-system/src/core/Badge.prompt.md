# Badge

Absolutely-positioned corner badge for product cards / list rows ("New", "Sale"). The parent must be `position:relative`.

```jsx
<div style={{position:"relative"}}>
  <Badge badgeText="New" badgeType="card" badgePosition={{top:8,right:8}} />
  ...card content...
</div>
```
