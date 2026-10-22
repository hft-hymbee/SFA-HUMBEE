# Feedback

The mandatory mobile state set: `Skeleton` / `SkeletonRow` (loading), `EmptyState`, `ErrorState` (retry), `OfflineBanner`, and `LockBanner` (the attendance hard-gate). Every empty/error/blocked state carries a labelled recovery CTA — never a dead end.

```jsx
<LockBanner onAction={goPunch} />
<ErrorState onRetry={reload} />
<EmptyState icon="ShoppingCartOutlined" title="No orders yet" actionLabel="Start an order" onAction={start} />
```
