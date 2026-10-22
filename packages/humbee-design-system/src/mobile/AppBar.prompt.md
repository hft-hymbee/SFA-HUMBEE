# AppBar

Mobile app shell — `TopAppBar` (title + optional back + notifications bell with badge) and `BottomNav` (5-tab spine). Reuse on every SFA screen for a consistent product feel.

```jsx
<TopAppBar title="Today" onBell={openNotifs} bellCount={3} />
<BottomNav active="today" onNav={go} />   {/* SP_TABS: Today · Beats · Route · Orders · More */}
```
