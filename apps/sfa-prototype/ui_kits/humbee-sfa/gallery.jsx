/* Humbee SFA — Sales Person screen gallery. Lays every screen (with its states) in phone frames. (mount: #sfa-root) */
const HG = window.HumbeeDesignSystem_c38d59;
const { useState: useStateG, useRef: useRefG, useEffect: useEffectG } = React;

/* Error boundary so a transient/undefined screen can never unmount the whole gallery. */
class FrameBoundary extends React.Component {
  constructor(p) { super(p); this.state = { err: null }; }
  static getDerivedStateFromError(err) { return { err }; }
  render() {
    if (this.state.err) {
      return <div style={{ width: 375, height: 812, borderRadius: 34, background: "#FFF6E5", border: "1px solid #FFD98A", display: "flex", alignItems: "center", justifyContent: "center", padding: 24, textAlign: "center", color: "#8A6D3B", fontSize: 13 }}>Screen failed to render.</div>;
    }
    return this.props.children;
  }
}

/* Lazy mount: only render a frame's screen once it scrolls near the viewport.
   Keeps the initial paint cheap so ~35 device frames don't block the main thread. */
function LazyFrame({ id, title, sub, statusColor, children }) {
  const ref = useRefG(null);
  const [show, setShow] = useStateG(false);
  useEffectG(() => {
    if (show || !ref.current) return;
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { setShow(true); io.disconnect(); }
    }, { rootMargin: "600px 0px" });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [show]);
  const PhoneFrame = window.HumbeeDesignSystem_c38d59.PhoneFrame;
  return (
    <div ref={ref}>
      {show ? (
        <PhoneFrame label={`${id} · ${title}`} sublabel={sub} statusColor={statusColor}><FrameBoundary>{children}</FrameBoundary></PhoneFrame>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ paddingLeft: 4 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#333" }}>{id} · {title}</div>
            {sub && <div style={{ fontSize: 12, color: "#8C8C8C" }}>{sub}</div>}
          </div>
          <div style={{ width: 375, height: 812, borderRadius: 44, background: "#DEDEDE", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <span style={{ fontSize: 13, color: "#999" }}>Scroll to load…</span>
          </div>
        </div>
      )}
    </div>
  );
}

/* Render the screen only when its frame is live (children are passed as a render fn). */
function Frame({ id, title, sub, statusColor, children }) {
  return <LazyFrame id={id} title={title} sub={sub} statusColor={statusColor}>{children}</LazyFrame>;
}

function Section({ n, title, desc, children }) {
  return (
    <section style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, margin: "8px 4px 20px", flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, fontWeight: 900, color: "#fff", background: "#995A00", borderRadius: 8, padding: "4px 10px" }}>{n}</span>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: "#333" }}>{title}</h2>
        <span style={{ fontSize: 14, color: "#666" }}>{desc}</span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 40 }}>{children}</div>
    </section>
  );
}

function Gallery() {
  const W = window;
  return (
    <div style={{ minHeight: "100vh", background: "#ECECEC", fontFamily: "var(--font-family-base)", padding: "32px 32px 80px" }}>
      <header style={{ maxWidth: 1100, margin: "0 auto 40px" }}>
        <div style={{ fontSize: 34, fontWeight: 900, color: "#995A00", letterSpacing: "-1px" }}>Humbee SFA</div>
        <div style={{ fontSize: 17, color: "#333", fontWeight: 700, marginTop: 4 }}>Sales Person — mobile screens (375px)</div>
        <p style={{ fontSize: 14, color: "#666", maxWidth: 720, lineHeight: 1.5 }}>
          The field sales daily loop, built entirely from the Humbee design system + the new mobile kit
          (TopAppBar, BottomNav, ListRow, StatusChip, ApprovalTimeline, LockBanner, states). Login is
          phone&nbsp;+&nbsp;OTP only. Punch-in gates Route &amp; Orders; the 9–6 window is informational for
          managers, never enforced. Every visit is tagged Physical or Telephonic, and every data screen ships
          loading / empty / error / offline / permission states.
        </p>
      </header>

      <div style={{ display: "flex", flexDirection: "column", gap: 48 }}>
        <Section n="0" title="Launch & session" desc="S-A1 · S-A4 · S-A5 · S-A6">
          <Frame id="S-A1" title="Splash / launch" sub="Checking session" statusColor="#995A00"><W.SplashScreen /></Frame>
          <Frame id="S-A4" title="Account deactivated" sub="Login disabled"><W.AccountDeactivatedScreen /></Frame>
          <Frame id="S-A5" title="Session expired" sub="Re-auth modal"><W.ReauthScreen /></Frame>
          <Frame id="S-A6" title="Logout confirm" sub="Action sheet"><W.LogoutConfirmScreen /></Frame>
        </Section>

        <Section n="1–2" title="Sign in" desc="S-A2 Login (phone) · S-A3 OTP">
          <Frame id="S-A2" title="Login" sub="Phone number only" statusColor="#995A00"><W.LoginScreen /></Frame>
          <Frame id="S-A2" title="Login — error" sub="Number not registered" statusColor="#995A00"><W.LoginScreen error /></Frame>
          <Frame id="S-A3" title="OTP verify" sub="6-digit + resend timer"><W.OtpScreen /></Frame>
          <Frame id="S-A3" title="OTP — error" sub="Wrong code"><W.OtpScreen error /></Frame>
        </Section>

        <Section n="3" title="Today home hub" desc="S-HOME · punch-in gate + task type">
          <Frame id="S-HOME" title="Locked (not punched in)" sub="Task type locked too"><W.TodayScreen variant="locked" /></Frame>
          <Frame id="S-HOME" title="Unlocked (on duty)" sub="Sales / Official work"><W.TodayScreen variant="unlocked" /></Frame>
          <Frame id="S-HOME" title="Loading" sub="Skeleton"><W.TodayScreen variant="loading" /></Frame>
          <Frame id="S-HOME" title="Offline" sub="Connectivity banner"><W.TodayScreen variant="offline" /></Frame>
        </Section>

        <Section n="4–5" title="Attendance (GPS)" desc="S-ATT1 Punch · S-ATT1b Blocked">
          <Frame id="S-ATT1" title="Punch in — locating" sub="Capturing GPS"><W.PunchScreen variant="locating" /></Frame>
          <Frame id="S-ATT1" title="Punch in — ready" sub="Location captured"><W.PunchScreen variant="in" /></Frame>
          <Frame id="S-ATT1" title="Punch out" sub="On duty"><W.PunchScreen variant="out" /></Frame>
          <Frame id="S-ATT1b" title="Blocked — permission" sub="Location denied"><W.PunchBlockedScreen reason="permission" /></Frame>
          <Frame id="S-ATT1b" title="Blocked — GPS off" sub="Turn on GPS"><W.PunchBlockedScreen reason="gpsoff" /></Frame>
          <Frame id="S-ATT1b" title="Blocked — geofence" sub="Outside allowed area"><W.PunchBlockedScreen reason="geofence" /></Frame>
        </Section>

        <Section n="6" title="Today's route / run" desc="S-ROUTE2 beat choice · S-ROUTE1 + S-ROUTE3 · planned & unplanned">
          <Frame id="S-ROUTE2" title="Choose beat" sub="Assigned for today"><W.BeatChooserScreen variant="today" /></Frame>
          <Frame id="S-ROUTE2" title="Choose beat — other day" sub="Unplanned beat"><W.BeatChooserScreen variant="other" /></Frame>
          <Frame id="S-ROUTE3" title="Running" sub="3/6 visited"><W.RouteScreen variant="running" /></Frame>
          <Frame id="S-ROUTE3" title="Locked" sub="Before punch-in"><W.RouteScreen variant="locked" /></Frame>
          <Frame id="S-ROUTE1" title="Empty" sub="No route planned"><W.RouteScreen variant="empty" /></Frame>
          <Frame id="S-ROUTE1" title="Loading" sub="Skeleton"><W.RouteScreen variant="loading" /></Frame>
          <Frame id="S-ROUTE1" title="Error" sub="Retry"><W.RouteScreen variant="error" /></Frame>
        </Section>

        <Section n="7" title="Outlet visit & visit type" desc="S-ROUTE4 · Physical / Telephonic · S-VISIT1/2">
          <Frame id="S-ROUTE4" title="Physical visit — Dealer" sub="Outlet snapshot · order via its DP"><W.OutletVisitScreen level="dealer" /></Frame>
          <Frame id="S-ROUTE4" title="Physical visit — DP outlet" sub="Outlet snapshot · manufacturer order"><W.OutletVisitScreen level="dp" /></Frame>
          <Frame id="S-ROUTE4" title="Telephonic call" sub="Call-based visit record"><W.OutletVisitScreen level="dealer" visitType="telephonic" /></Frame>
          <Frame id="S-ROUTE4" title="Unplanned visit" sub="Outside the planned route"><W.OutletVisitScreen level="dp" planned={false} hasDirections={false} /></Frame>
          <Frame id="S-VISIT1" title="Log visit outcome" sub="Reason tiles"><W.VisitOutcomeScreen /></Frame>
          <Frame id="S-VISIT2" title="Missed visit audit" sub="No action · audit only"><W.MissedVisitAuditScreen role="sp" /></Frame>
        </Section>

        <Section n="7c" title="Outlet onboarding & insights" desc="S-OUT1 new outlet · S-OUT2 external insight web view">
          <Frame id="S-OUT1" title="Onboard new outlet" sub="Field capture form"><W.OutletOnboardingScreen /></Frame>
          <Frame id="S-OUT1" title="Outlet submitted" sub="Pending Admin verification"><W.OutletOnboardingScreen variant="submitted" /></Frame>
          <Frame id="S-OUT2" title="Outlet insights" sub="Rendered by external API"><W.OutletInsightWebviewScreen /></Frame>
          <Frame id="S-OUT2" title="Insights — loading" sub="Web view fetching"><W.OutletInsightWebviewScreen variant="loading" /></Frame>
          <Frame id="S-OUT2" title="Insights — unavailable" sub="Service error, visit unaffected"><W.OutletInsightWebviewScreen variant="error" /></Frame>
        </Section>

        <Section n="7b" title="Task type: Official work" desc="S-OFF1 timer · S-OFF2 history">
          <Frame id="S-OFF1" title="Official work — start" sub="Type + purpose"><W.OfficialWorkScreen variant="start" /></Frame>
          <Frame id="S-OFF1" title="Official work — running" sub="Independent time tracking"><W.OfficialWorkScreen variant="running" /></Frame>
          <Frame id="S-OFF2" title="Official work history" sub="Durations per task"><W.OfficialWorkHistoryScreen variant="list" /></Frame>
          <Frame id="S-OFF2" title="History — empty" sub="Recovery CTA"><W.OfficialWorkHistoryScreen variant="empty" /></Frame>
        </Section>

        <Section n="8" title="Order flow" desc="S-ORD1b PO (DP → manufacturer) · S-ORD1→4">
          <Frame id="S-ORD1b" title="PO selector" sub="DP → manufacturer PO"><W.PoSelectorScreen variant="list" /></Frame>
          <Frame id="S-ORD1b" title="PO selector — empty" sub="No open PO"><W.PoSelectorScreen variant="empty" /></Frame>
          <Frame id="S-ORD1" title="Start order — Dealer" sub="From its DP · direct, no approval"><W.StartOrderScreen level="dealer" /></Frame>
          <Frame id="S-ORD1" title="Start order — DP outlet" sub="From manufacturer PO · ship-to + approval"><W.StartOrderScreen level="dp" /></Frame>
          <Frame id="S-ORD2" title="Product picker" sub="Add / stepper"><W.ProductPickerScreen /></Frame>
          <Frame id="S-ORD3" title="Cart" sub="Lines + scheme + total"><W.CartScreen /></Frame>
          <Frame id="S-ORD4" title="Review — Dealer" sub="Submit DP order directly"><W.OrderReviewScreen level="dealer" /></Frame>
          <Frame id="S-ORD4" title="Review — DP outlet" sub="Submit for approval"><W.OrderReviewScreen level="dp" /></Frame>
        </Section>

        <Section n="9–10" title="Order status & tracking" desc="S-ORD6 My orders · S-ORD7 detail">
          <Frame id="S-ORD6" title="My orders" sub="All statuses"><W.MyOrdersScreen variant="list" /></Frame>
          <Frame id="S-ORD6" title="My orders — empty" sub="Recovery CTA"><W.MyOrdersScreen variant="empty" /></Frame>
          <Frame id="S-ORD7" title="Approved with edits" sub="Diff + timeline"><W.OrderDetailScreen variant="edited" /></Frame>
          <Frame id="S-ORD7" title="Approved — 1h creation SLA" sub="DP order being created"><W.OrderDetailScreen variant="sla" /></Frame>
          <Frame id="S-ORD7" title="PO/DP failed" sub="Honest error + retry"><W.OrderDetailScreen variant="failed" /></Frame>
        </Section>

        <Section n="11" title="Requests & notifications" desc="S-AP3 · S-NOTIF">
          <Frame id="S-AP3" title="My requests" sub="StatusChip per request"><W.MyRequestsScreen /></Frame>
          <Frame id="S-NOTIF" title="Notifications" sub="Approval outcomes"><W.NotificationsScreen /></Frame>
        </Section>

        <Section n="12" title="Beats (plan-time)" desc="S-BEAT1–5 · S-BEAT7 SP edit · Zone/State/District clusters + category">
          <Frame id="S-BEAT1" title="My beats" sub="Approved / edit pending / draft"><W.MyBeatsScreen variant="list" /></Frame>
          <Frame id="S-BEAT1" title="My beats — empty" sub="Recovery CTA"><W.MyBeatsScreen variant="empty" /></Frame>
          <Frame id="S-BEAT2" title="Create beat — scope" sub="Cluster picker · multi-select"><W.CreateBeatScopeScreen /></Frame>
          <Frame id="S-BEAT3" title="Outlet picker" sub="Grouped by location"><W.OutletPickerScreen /></Frame>
          <Frame id="S-BEAT4" title="Name & review" sub="Submit for approval"><W.NameBeatScreen /></Frame>
          <Frame id="S-BEAT5" title="Beat detail" sub="Scope + timeline + edit"><W.BeatDetailScreen variant="active" /></Frame>
          <Frame id="S-BEAT5" title="Beat detail — inactive" sub="Soft-deleted by Admin"><W.BeatDetailScreen variant="inactive" /></Frame>
          <Frame id="S-BEAT7" title="Edit beat (SP)" sub="Send changes for approval"><W.EditBeatScreen /></Frame>
          <Frame id="S-BEAT7" title="Edit pending approval" sub="Approved version stays live"><W.EditBeatScreen variant="pending" /></Frame>
        </Section>

        <Section n="13" title="Plan route" desc="S-ROUTE2 · from approved beats">
          <Frame id="S-ROUTE2" title="Plan route" sub="Date + sequence"><W.PlanRouteScreen variant="default" /></Frame>
          <Frame id="S-ROUTE2" title="Plan route — no beats" sub="Blocked, recovery CTA"><W.PlanRouteScreen variant="nobeats" /></Frame>
        </Section>

        <Section n="14" title="Dashboard & targets" desc="S-DASH-SP · S-DASH-DRILL · S-TGT4 · S-LEAD1">
          <Frame id="S-DASH-SP" title="SP dashboard" sub="Self overview"><W.DashboardScreen variant="default" /></Frame>
          <Frame id="S-DASH-SP" title="Dashboard — loading" sub="Skeleton"><W.DashboardScreen variant="loading" /></Frame>
          <Frame id="S-DASH-DRILL" title="Metric drill-down" sub="Orders"><W.DashDrillScreen /></Frame>
          <Frame id="S-TGT4" title="My targets" sub="Sales · outlets · leads"><W.MyTargetsScreen /></Frame>
          <Frame id="S-TGT4" title="My targets — no target" sub="Targets are optional"><W.MyTargetsScreen variant="notarget" /></Frame>
          <Frame id="S-LEAD1" title="Capture lead" sub="Feeds the lead target"><W.LeadCaptureScreen /></Frame>
          <Frame id="S-LEAD1" title="My leads" sub="MTD pace"><W.LeadCaptureScreen variant="list" /></Frame>
        </Section>

        <Section n="15" title="Leave & attendance" desc="S-LV1 · S-LV2 · S-ATT2">
          <Frame id="S-LV1" title="Apply leave" sub="Type + dates"><W.ApplyLeaveScreen /></Frame>
          <Frame id="S-LV2" title="Leave status" sub="History + chips"><W.LeaveStatusScreen /></Frame>
          <Frame id="S-ATT2" title="Attendance history" sub="Daily log"><W.AttendanceHistoryScreen variant="list" /></Frame>
          <Frame id="S-ATT2" title="Attendance — empty" sub="No records"><W.AttendanceHistoryScreen variant="empty" /></Frame>
        </Section>

        <Section n="16" title="Profile" desc="S-PROFILE · role, geography, account">
          <Frame id="S-PROFILE" title="My profile" sub="Role + assignment"><W.ProfileScreen /></Frame>
        </Section>

        <div style={{ height: 2, background: "#995A00", borderRadius: 2, margin: "16px 4px 8px" }} />
        <div style={{ margin: "0 4px 8px", fontSize: 26, fontWeight: 900, color: "#995A00", letterSpacing: "-0.5px" }}>Manager</div>
        <div style={{ margin: "0 4px 24px", fontSize: 14, color: "#666", maxWidth: 720 }}>Own reporting tree. Nav: Dashboard · Team · Approvals · Reports · More. Same shell, tokens and status patterns as SP — density tuned for oversight, approvals and exception handling.</div>

        <Section n="M1" title="Manager dashboard" desc="S-DASH-MGR · actionable signals first">
          <Frame id="S-DASH-MGR" title="Dashboard" sub="Tree overview"><W.MgmtDashboardScreen role="mgr" /></Frame>
          <Frame id="S-DASH-MGR" title="Loading" sub="Skeleton"><W.MgmtDashboardScreen role="mgr" variant="loading" /></Frame>
          <Frame id="S-DASH-MGR" title="Offline" sub="Banner"><W.MgmtDashboardScreen role="mgr" variant="offline" /></Frame>
          <Frame id="S-DASH-DRILL" title="Metric drill-down" sub="Behind a card"><W.DashDrillScreen /></Frame>
        </Section>

        <Section n="M2" title="Approvals (unified)" desc="S-AP1 inbox · S-AP2 detail · parent-only">
          <Frame id="S-AP1" title="Approval inbox" sub="Beat/order/leave"><W.ApprovalInboxScreen role="mgr" /></Frame>
          <Frame id="S-AP1" title="Inbox — empty" sub="All caught up"><W.ApprovalInboxScreen role="mgr" variant="empty" /></Frame>
          <Frame id="S-AP2" title="Approval detail" sub="Parent approver · edit while pending"><W.ApprovalDetailScreen role="mgr" /></Frame>
          <Frame id="S-AP2" title="Routed up (manager on leave)" sub="Next higher manager"><W.ApprovalDetailScreen role="mgr" variant="escalated" /></Frame>
        </Section>

        <Section n="M2b" title="Combined visit (tag-along)" desc="S-CVIS1 schedule · S-CVIS2 feedback">
          <Frame id="S-CVIS1" title="Schedule combined visit" sub="Beat → outlet → day"><W.CombinedVisitScreen role="mgr" /></Frame>
          <Frame id="S-CVIS2" title="Post-visit feedback" sub="Triggered on punch-out"><W.CombinedVisitFeedbackScreen role="mgr" /></Frame>
        </Section>

        <Section n="M3" title="Team & per-SP day view" desc="S-TEAM1 overview · S-TEAM2 day timeline · S-ORG2/4">
          <Frame id="S-TEAM1" title="Team overview" sub="Today at a glance per SP"><W.TeamOverviewScreen role="mgr" /></Frame>
          <Frame id="S-TEAM2" title="SP day — today" sub="Live activity timeline + day KPIs"><W.SpDayScreen role="mgr" scope="today" /></Frame>
          <Frame id="S-TEAM2" title="SP day — yesterday" sub="Closed day, full run"><W.SpDayScreen role="mgr" scope="yesterday" /></Frame>
          <Frame id="S-TEAM2" title="SP day — chosen date" sub="Any past date"><W.SpDayScreen role="mgr" scope="pick" /></Frame>
          <Frame id="S-ORG1" title="My team (list)" sub="Search + filter"><W.EmployeeListScreen role="mgr" /></Frame>
          <Frame id="S-ORG2" title="Employee detail" sub="Read-only + day timeline entry"><W.EmployeeDetailScreen role="mgr" /></Frame>
          <Frame id="S-ORG4" title="Org tree" sub="Own subtree"><W.OrgTreeScreen role="mgr" /></Frame>
        </Section>

        <Section n="M4" title="Oversight ops" desc="S-ROUTE5 · S-ATT3 · S-ORD7 · S-LV3">
          <Frame id="S-ROUTE5" title="Team coverage" sub="Live positions"><W.TeamRouteScreen role="mgr" /></Frame>
          <Frame id="S-ATT3" title="Team attendance" sub="9–6 informational only"><W.TeamAttendanceScreen role="mgr" /></Frame>
          <Frame id="S-ORD7" title="Order detail (scope)" sub="Tree order"><W.OrderDetailMgmtScreen role="mgr" /></Frame>
          <Frame id="S-LV3" title="Team leave" sub="Auto-approve + routing"><W.TeamLeaveScreen role="mgr" /></Frame>
        </Section>

        <Section n="M5" title="Targets & more" desc="S-TGT1 three types · S-TGT3 · S-NOTIF · More">
          <Frame id="S-TGT1" title="Set target — sales" sub="Amount/volume per manufacturer"><W.SetTargetScreen role="mgr" type="sales" /></Frame>
          <Frame id="S-TGT1" title="Set target — new outlets" sub="MTD onboarding count"><W.SetTargetScreen role="mgr" type="outlets" /></Frame>
          <Frame id="S-TGT1" title="Set target — leads" sub="MTD or weekly"><W.SetTargetScreen role="mgr" type="leads" /></Frame>
          <Frame id="S-TGT3" title="Team targets" sub="Tabs per target type"><W.TeamTargetsScreen role="mgr" /></Frame>
          <Frame id="S-NOTIF" title="Notifications" sub="Shared center"><W.NotificationsScreen /></Frame>
          <Frame id="More" title="Manager more" sub="Profile + logout"><W.MgmtMoreScreen role="mgr" /></Frame>
        </Section>

        <div style={{ height: 2, background: "#663C00", borderRadius: 2, margin: "16px 4px 8px" }} />
        <div style={{ margin: "0 4px 8px", fontSize: 26, fontWeight: 900, color: "#663C00", letterSpacing: "-0.5px" }}>Admin</div>
        <div style={{ margin: "0 4px 24px", fontSize: 14, color: "#666", maxWidth: 720 }}>Org-wide data & controls. Nav: Dashboard · Org · Approvals · Reports · More. Optimized for clarity, hierarchy and configurability at high information density.</div>

        <Section n="A1" title="Admin dashboard" desc="S-DASH-ADM · org-wide + regions">
          <Frame id="S-DASH-ADM" title="Dashboard" sub="Org-wide"><W.MgmtDashboardScreen role="adm" /></Frame>
          <Frame id="S-DASH-ADM" title="Error" sub="Retry"><W.MgmtDashboardScreen role="adm" variant="error" /></Frame>
          <Frame id="S-DASH-DRILL" title="Metric drill-down" sub="Behind a card"><W.DashDrillScreen /></Frame>
        </Section>

        <Section n="A2" title="Org & workforce" desc="S-ORG1/2/3/4/5/6 · Admin owns assignment">
          <Frame id="S-ORG1" title="Employees" sub="Org-wide"><W.EmployeeListScreen role="adm" /></Frame>
          <Frame id="S-ORG2" title="Employee detail" sub="Editable"><W.EmployeeDetailScreen role="adm" /></Frame>
          <Frame id="S-ORG3" title="Add employee" sub="Phone = login"><W.AddEmployeeScreen /></Frame>
          <Frame id="S-ORG4" title="Org tree" sub="Full hierarchy"><W.OrgTreeScreen role="adm" /></Frame>
          <Frame id="S-ORG5" title="Move in hierarchy" sub="Reassign manager"><W.AssignHierarchyScreen /></Frame>
          <Frame id="S-ORG6" title="Assign geography" sub="Zone / State / District clusters + category"><W.AssignGeographyScreen role="adm" /></Frame>
        </Section>

        <Section n="A2b" title="Beat management (Admin)" desc="S-BEAT6 · assign, frequency, soft delete">
          <Frame id="S-BEAT6" title="Beats" sub="Active / inactive"><W.AdminBeatMgmtScreen variant="list" /></Frame>
          <Frame id="S-BEAT6" title="Edit beat" sub="SP + frequency + active"><W.AdminBeatMgmtScreen variant="edit" /></Frame>
          <Frame id="S-BEAT6" title="Beats — empty" sub="Create first beat"><W.AdminBeatMgmtScreen variant="empty" /></Frame>
        </Section>

        <Section n="A3" title="Approvals & oversight" desc="S-AP1/2 · S-ROUTE5 · S-ATT4 · S-ORD7">
          <Frame id="S-AP1" title="Approval inbox" sub="Org-wide"><W.ApprovalInboxScreen role="adm" /></Frame>
          <Frame id="S-AP2" title="Approval detail" sub="Approve/edit/reject"><W.ApprovalDetailScreen role="adm" /></Frame>
          <Frame id="S-ROUTE5" title="Org coverage" sub="Live positions"><W.TeamRouteScreen role="adm" /></Frame>
          <Frame id="S-ATT4" title="All attendance" sub="+ Export"><W.TeamAttendanceScreen role="adm" /></Frame>
          <Frame id="S-ORD7" title="Order detail (scope)" sub="Org + override"><W.OrderDetailMgmtScreen role="adm" /></Frame>
        </Section>

        <Section n="A4" title="Targets & more" desc="S-TGT1/3 · S-LV3 · More">
          <Frame id="S-TGT1" title="Set target" sub="Any SP · three types"><W.SetTargetScreen role="adm" /></Frame>
          <Frame id="S-TGT3" title="Org targets" sub="Sales / outlets / leads"><W.TeamTargetsScreen role="adm" type="outlets" /></Frame>
          <Frame id="S-LV3" title="Team leave" sub="Auto-approved + routed"><W.TeamLeaveScreen role="adm" /></Frame>
          <Frame id="More" title="Admin more" sub="Profile + logout"><W.MgmtMoreScreen role="adm" /></Frame>
        </Section>
      </div>
    </div>
  );
}

const __sfaNeeded = [
  "LoginScreen","OtpScreen","TodayScreen",
  "PunchScreen","PunchBlockedScreen","RouteScreen","BeatChooserScreen",
  "OutletVisitScreen","StartOrderScreen","ProductPickerScreen","CartScreen","OrderReviewScreen","VisitOutcomeScreen","MyOrdersScreen","OrderDetailScreen","MyRequestsScreen","NotificationsScreen",
  "SplashScreen","AccountDeactivatedScreen","ReauthScreen","LogoutConfirmScreen",
  "MyBeatsScreen","CreateBeatScopeScreen","OutletPickerScreen","NameBeatScreen","BeatDetailScreen","EditBeatScreen","PlanRouteScreen",
  "ProfileScreen","AttendanceHistoryScreen","ApplyLeaveScreen","LeaveStatusScreen","MyTargetsScreen","DashboardScreen","DashDrillScreen",
  "MgmtDashboardScreen","ApprovalInboxScreen","ApprovalDetailScreen",
  "EmployeeListScreen","EmployeeDetailScreen","AddEmployeeScreen","OrgTreeScreen","AssignHierarchyScreen","AssignGeographyScreen",
  "TeamRouteScreen","TeamAttendanceScreen","OrderDetailMgmtScreen","TeamLeaveScreen","SetTargetScreen","TeamTargetsScreen","MgmtMoreScreen",
  "OutletOnboardingScreen","OutletInsightWebviewScreen","LeadCaptureScreen","SpDayScreen","TeamOverviewScreen",
  "OfficialWorkScreen","OfficialWorkHistoryScreen","MissedVisitAuditScreen","PoSelectorScreen","CombinedVisitScreen","CombinedVisitFeedbackScreen","AdminBeatMgmtScreen",
];
function __sfaMount(tries) {
  const n = tries || 0;
  if (window.__sfaMounted) return;
  const el = document.getElementById("sfa-root");
  if (!el) return; // not the SFA page (e.g. a card/other page that also loads the bundle)
  const ns = window.HumbeeDesignSystem_c38d59;
  const missing = __sfaNeeded.filter((name) => typeof window[name] !== "function");
  if (!(ns && ns.PhoneFrame) || missing.length) {
    /* Bounded retry: never spin forever — report what never arrived instead. */
    if (n > 240) { console.error("SFA mount gave up. Missing:", missing.join(", ") || "design system bundle"); return; }
    return requestAnimationFrame(() => __sfaMount(n + 1));
  }
  try {
    const root = window.__sfaRoot || (window.__sfaRoot = ReactDOM.createRoot(el));
    root.render(<FrameBoundary><Gallery /></FrameBoundary>);
    window.__sfaMounted = true; // latch only after a successful render
  } catch (e) { console.error("SFA mount failed", e); }
}
window.__sfaMount = __sfaMount; // triggered once from an inline script in index.html (never self-invoked, so the bundled copy can't double-mount)
