# ApprovalTimeline

Vertical status thread for the approval engine (requested → approved / edited / rejected). Pair with StatusChip so the SP never wonders "did it go through?".

```jsx
<ApprovalTimeline steps={[
  {label:"Submitted", time:"10:24 AM", state:"done"},
  {label:"Approved with edits", detail:"Qty reduced on 1 line", time:"11:02 AM", state:"edited"},
  {label:"Sent to PO/DP", state:"current"},
]} />
```
