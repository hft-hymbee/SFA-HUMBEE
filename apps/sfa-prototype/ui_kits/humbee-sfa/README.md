# Humbee SFA — Sales Person (UI Kit)

Mobile-first (375px) screens for the **Humbee SFA** field-sales app, **Sales Person** point of
view. Built entirely from the Humbee design system + the `packages/humbee-design-system/src/mobile/` kit — no one-off
components, no new tokens.

## What's here
`index.html` renders a **gallery** of every screen (in iPhone-class `PhoneFrame`s) grouped in
daily-loop order, each shown with its mandatory states.

Daily loop: **Login (phone + OTP) → Today → Punch (GPS) → Task type (Sales / Official work) → Route → Outlet visit (Physical / Telephonic) → Order → Status.**

| ID | Screen | States shown |
|---|---|---|
| S-A1 | Splash / launch | branded loading |
| S-A4 | Account deactivated | blocked + contact CTA |
| S-A5 | Session expired | re-auth modal |
| S-A6 | Logout confirm | action sheet |
| S-A2 | Login (phone number only) | default · unregistered-number error |
| S-A3 | OTP verification | timer · error |
| S-HOME | Today hub | locked (not punched) · unlocked (task type live) · loading · offline |
| S-ATT1 | Punch in/out | locating · ready · on-duty (punch out) |
| S-ATT1b | Punch blocked | permission · GPS off · geofence |
| S-ROUTE2 | Choose beat | beat assigned for today · another day's beat = unplanned run |
| S-ROUTE1/3 | Today's route / run | running (planned + unplanned) · locked · empty · loading · error |
| S-ROUTE4 | Outlet visit | Physical · Telephonic · unplanned · no saved location |
| S-VISIT2 | Missed visit audit | end-of-day misses, audit only (no SP action) |
| S-OFF1 | Official work timer | not started · running (independent time tracking) |
| S-OFF2 | Official work history | list · empty |
| S-VISIT1 | Visit outcome | reason-coded bottom sheet |
| S-ORD1b | PO selector (DP → manufacturer) | list · no-open-PO empty |
| S-ORD1–4 | Start order → Products → Cart → Review | Dealer buys from its DP (direct, no approval) · DP buys direct from manufacturer against a PO (ship-to partner + approval); optional extra shipping address on both |
| S-ORD6 | My orders | list · empty |
| S-ORD7 | Order detail | approved-with-edits (diff) · approved + 1-hour creation SLA · PO/DP failed (retry) |
| S-AP3 | My requests | StatusChip per request |
| S-NOTIF | Notifications | approval outcomes |
| S-BEAT1 | My beats | list (tabs) · empty · loading |
| S-BEAT2 | Create beat — select scope | State · District · Location (multi) · Shop category |
| S-BEAT3 | Outlet picker / cluster | multi-select, grouped by location |
| S-BEAT4 | Name & review beat | naming convention · frequency · submit |
| S-BEAT5 | Beat detail | active · inactive (Admin soft delete) |
| S-BEAT6 | Admin beat management | list · edit (SP, frequency, active) · empty |
| S-CVIS1 | Combined visit (tag-along) | beat → outlet → day |
| S-CVIS2 | Combined visit feedback | placeholder form, fired on punch-out |
| S-ROUTE2 | Plan route | date + sequence · no-approved-beats state |
| S-DASH-SP | Sales Person dashboard | overview · loading · offline |
| S-DASH-DRILL | Metric drill-down | orders |
| S-TGT4 | My targets | gauge + SKU-wise MTD + schemes · no-target (optional) |
| S-LV1 | Apply leave | type + dates + reason |
| S-LV2 | Leave status & history | tabs + StatusChip |
| S-ATT2 | Attendance history | daily log · empty |
| S-PROFILE | My profile | role, geography, manager, account |

## Key rules honoured
- **Login is phone + OTP only** — no password, no forgot/change-password surfaces. S-A5 re-auth is OTP-only too.
- **Demo KPI scope** — Manager/Admin dashboards use only attendance, route, visit, order, approval and *optional* target data (team size, present today, route coverage, visits, orders, pending approvals, target achieved). Empty denominators show `—`; a missing target shows **No target**. Advanced KPI analytics (LMTD/YTD, growth, run rate, league tables, product mix) remain future production work.
- **Outlet snapshot (S-ROUTE4)** — compact identity (contact, callable mobile, GST) + visit/order history (last visit, visits & orders this month, order value, last-order status). Informational; it never outranks the visit/order CTAs.
- **Employee snapshot (S-ORG2)** — Today / MTD segmented operational stats. Manager read-only within own tree; Admin org-wide with edit controls.
- **Punch-in gate** — Route & Orders locked (`LockBanner`) until punch-in with GPS. The 9–6 window is *informational for managers*, never enforced.
- **Task types** — Sales and Official Work; official work is time-tracked separately and is not an outlet visit.
- **Every visit is typed** — Physical Visit or Telephonic Call, plus planned/unplanned. Pending planned visits become missed visits (audit only).
- **Orders follow outlet classification (Humbee API)** — Dealer outlet → direct DP order, no approval. Distribution-partner outlet → DP order from a selected PO, parent-manager approval, DP order created within one hour.
- **Approvals are parent-only** — skip-level only when the parent manager is on leave (routes one level up); top-of-hierarchy leave is auto-approved; edits allowed only while pending.
- **Admin owns assignment** — employees, geography (State/District/Location/Shop category), outlets and beats. Managers view, never assign.
- **Targets are optional** — set by Admin/Manager for any employee at any level; achievement is Humbee-calculated and read-only.
- **One primary action per screen**; touch targets ≥ 44px; body ≥ 15px.
- **Never a dead end** — every empty/error/blocked state has a labelled recovery CTA.
- **Status always visible** — `StatusChip` + `ApprovalTimeline`; PO/DP failures surfaced honestly.

## Files
- `index.html` — entry (loads React + DS bundle + the three screen files + gallery).
- `screens-auth-home.jsx` — Login, OTP, Today (+ shared `Screen`/`Card` scaffold).
- `screens-attendance-route.jsx` — Punch, Punch blocked, Route.
- `screens-order-status.jsx` — Outlet visit, order flow, visit outcome, orders, detail, requests, notifications.
- `screens-session.jsx` — Splash, account deactivated, re-auth, logout confirm.
- `screens-beats-plan.jsx` — My beats, create beat (scope → outlets → name/review), beat detail, plan route.
- `screens-more.jsx` — Profile, attendance history (calendar), apply leave, leave status, my targets, SP dashboard + drill-down.
- `screens-mgmt-core.jsx` — **Manager/Admin** shell + role tabs, dashboards (S-DASH-MGR/ADM), approval inbox/detail (S-AP1/2).
- `screens-mgmt-org.jsx` — Org & workforce (S-ORG1–6), role-scoped (Manager own tree read-only / Admin org-wide editable).
- `screens-tasks-visits.jsx` — Official work (S-OFF1/2), missed-visit audit (S-VISIT2), PO selector (S-ORD1b, DP → manufacturer), combined visits (S-CVIS1/2), Admin beat management (S-BEAT6).
- `screens-mgmt-ops.jsx` — Team coverage (S-ROUTE5), attendance (S-ATT3/4 + export), order detail scope (S-ORD7), team leave (S-LV3), targets (S-TGT1/3), schemes (S-TGT2), management More.
- `gallery.jsx` — lays the frames out (SP, then Manager, then Admin).

Components resolve from `window.HumbeeDesignSystem_<hash>`. Data is faked; GPS/order APIs are mocked.

## Pending inputs (placeholder shells in place)
- Official Work form fields, combined-visit feedback form fields, and final KPI/target definitions — shells are built and labelled as pending.

## Not yet built (next batches)
All **Sales Person**, **Manager**, and **Admin** screens are now covered
(role-aware, reusing one design contract). Remaining: **future** customer onboarding, and
production porting of these prototypes into `apps/web` (Next.js + MUI), tracked separately.

### Role scoping
- **Manager** — own reporting tree only; org screens are read-only; nav = Dashboard · Team · Approvals · Reports · More.
- **Admin** — org-wide data + controls (add/edit employee, move hierarchy, geography & outlet assignment, beat management, outlet verification, export); nav = Dashboard · Org · Approvals · Reports · More.
- Approvals (beats/orders/leave) and the Notifications center are shared surfaces, scoped by role.

## Round 4 changes (Aug 2026)
1. **Geography = cluster model.** One shared `GeoScopePicker` (`screens-geo.jsx`) drives all three places geography is defined — Admin → assign SP (S-ORG6), beat creation (S-BEAT2), beat edit (S-BEAT7 / S-BEAT6). Parameters, all multi-select and cascading: **Zone cluster · State cluster · District cluster · Shop category**. Collapsible levels with live summaries, cascading cleanup when a parent is dropped, and an "N outlets in scope" roll-up.
2. **Outlet insights web view.** S-ROUTE4 keeps the outlet snapshot and adds **Open full outlet insights** → S-OUT2, an external web view rendered by the insights API (loading / error states included).
3. **New outlet onboarding** — S-OUT1 (`screens-capture.jsx`): shop, address + GPS, proof/GST, photos; submits to Admin for verification (S-OUT1 submitted state). Field list flagged as pending the onboarding API schema.
4. **SP can edit beats** — S-BEAT7: edit name, cluster scope, frequency and outlets, then **Send for approval**; approved version stays live while the edit is pending (pending state shows the requested diff + timeline).
5. **Manager team flow** (`screens-mgmt-team.jsx`): S-TEAM1 team overview (per-SP card with duty state, visits, orders, target, coverage bar) → S-TEAM2 **per-SP day view** — date scope (Today / Yesterday / any date), day KPI grid, and an animated activity timeline (typed nodes, travel legs, live pulse, duration/value chips, time-split roll-up, Replay).
6. **Targets = three types** (schemes page removed): **Sales** (amount or volume, per manufacturer from the API), **New outlets onboarded** (MTD), **Manufacturer leads captured** (MTD or weekly, with S-LEAD1 capture form + list). S-TGT1 sets each type; S-TGT3 tabs by type; S-TGT4 shows the SP's three targets.
