/* Humbee SFA — Manager & Admin screens, part A: shell, dashboards, approvals, org.
   Role-aware: role="mgr" (own tree) | "adm" (org-wide). Reuses the SP design contract 1:1. */
const HM1 = window.HumbeeDesignSystem_c38d59;
const { useState: useStateMg } = React;

/* Role bottom-nav tabs (BottomNav supports a custom `tabs` prop). */
const MGR_TABS = [
  { id: "dashboard", label: "Dashboard", icon: "Dashboard", activeIcon: "Dashboard" },
  { id: "team", label: "Team", icon: "PersonRounded", activeIcon: "PersonRounded" },
  { id: "approvals", label: "Approvals", icon: "CheckCircle", activeIcon: "CheckCircle" },
  { id: "reports", label: "Reports", icon: "InvoiceOutlined", activeIcon: "InvoiceOutlined" },
  { id: "more", label: "More", icon: "Menu", activeIcon: "Menu" },
];
const ADM_TABS = [
  { id: "dashboard", label: "Dashboard", icon: "Dashboard", activeIcon: "Dashboard" },
  { id: "org", label: "Org", icon: "PersonRounded", activeIcon: "PersonRounded" },
  { id: "approvals", label: "Approvals", icon: "CheckCircle", activeIcon: "CheckCircle" },
  { id: "reports", label: "Reports", icon: "InvoiceOutlined", activeIcon: "InvoiceOutlined" },
  { id: "more", label: "More", icon: "Menu", activeIcon: "Menu" },
];

/* Shared management scaffold (mirrors SP Screen, swaps nav tabs by role). */
function MScreen({ role = "mgr", title, back, bell, bellCount, tab, offline, children, noNav, bodyBg = "#F5F5F5" }) {
  const tabs = role === "adm" ? ADM_TABS : MGR_TABS;
  return (
    <React.Fragment>
      <HM1.TopAppBar title={title} onBack={back ? () => {} : undefined} onBell={bell ? () => {} : undefined} bellCount={bellCount} />
      {offline && <HM1.OfflineBanner />}
      <div style={{ flex: 1, overflowY: "auto", background: bodyBg }}>{children}</div>
      {!noNav && <HM1.BottomNav active={tab} tabs={tabs} onNav={() => {}} />}
    </React.Fragment>
  );
}
const CardMg = ({ children, style }) => <div style={{ background: "#fff", border: "1px solid #E5E5E5", borderRadius: 12, ...style }}>{children}</div>;
const secMg = { fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C", margin: "0 0 8px" };
const FooterMg = ({ children }) => <div style={{ position: "sticky", bottom: 0, background: "#fff", borderTop: "1px solid #E5E5E5", padding: 12 }}>{children}</div>;
window.MScreen = MScreen; window.CardMg = CardMg; window.secMg = secMg; window.FooterMg = FooterMg;

/* Small metric tile — actionable, tappable (drill-down). */
function Metric({ label, value, sub, subTone = "#8C8C8C", icon, onClick }) {
  return (
    <div onClick={onClick} style={{ background: "#fff", border: "1px solid #E5E5E5", borderRadius: 12, padding: 14, cursor: onClick ? "pointer" : "default", display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 12, color: "#666", fontWeight: 600 }}>{label}</span>
        {icon && <HM1.Icon name={icon} size={18} color="#995A00" />}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: "#333", lineHeight: 1.1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: subTone, fontWeight: 600 }}>{sub}</div>}
    </div>
  );
}
window.MgMetric = Metric;

/* Exception row — the actionable signal list managers/admins act on. */
function ExceptionRow({ icon, tone, title, sub, action }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px" }}>
      <div style={{ width: 36, height: 36, borderRadius: "50%", background: tone + "1A", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><HM1.Icon name={icon} size={20} color={tone} /></div>
      <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontSize: 14, fontWeight: 600, color: "#333" }}>{title}</div><div style={{ fontSize: 12, color: "#666" }}>{sub}</div></div>
      {action && <a href="#" style={{ fontSize: 13, color: "#995A00", fontWeight: 700, flexShrink: 0 }}>{action}</a>}
    </div>
  );
}

/* ---------- S-DASH-MGR / S-DASH-ADM Dashboard ---------- */
function MgmtDashboardScreen({ role = "mgr", variant = "default" }) {
  const adm = role === "adm";
  const title = adm ? "Admin dashboard" : "Manager dashboard";
  if (variant === "loading") {
    return <MScreen role={role} title={title} bell tab="dashboard"><div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}><HM1.Skeleton width="55%" height={20} /><div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>{[0,1,2,3].map(i => <HM1.Skeleton key={i} height={92} radius={12} />)}</div><HM1.Skeleton height={140} radius={12} /></div></MScreen>;
  }
  if (variant === "error") return <MScreen role={role} title={title} bell tab="dashboard"><HM1.ErrorState onRetry={() => {}} /></MScreen>;
  const scope = adm ? "Organization-wide · 6 regions · 148 employees" : "Your reporting tree only · 12 members";
  return (
    <MScreen role={role} title={title} bell bellCount={5} tab="dashboard" offline={variant === "offline"}>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#666" }}>
          <HM1.Icon name="LocationMarker" size={16} color="#8C8C8C" /> {scope}
          <span style={{ marginLeft: "auto", fontSize: 12, color: "#8C8C8C" }}>Today · 15 Jul</span>
        </div>

        {/* Actionable signals first */}
        <div>
          <p style={secMg}>Needs attention</p>
          <CardMg style={{ padding: 0, overflow: "hidden" }}>
            <ExceptionRow icon="CheckCircle" tone="#FFBF40" title={`${adm ? 34 : 7} approvals pending`} sub="Orders, beats & leave" action="Review" />
            <div style={{ borderTop: "1px solid #F0F0F0" }} />
            <ExceptionRow icon="Schedule" tone="#FFBF40" title={`${adm ? 16 : 2} no punch-in yet`} sub="Informational · 9–6 timings are not enforced" action="View" />
            <div style={{ borderTop: "1px solid #F0F0F0" }} />
            <ExceptionRow icon="Warning" tone="#CC0000" title={`${adm ? 5 : 1} PO/DP failures`} sub="Approved but downstream rejected" action="Fix" />
          </CardMg>
        </div>

        {/* Core KPI grid — attendance, route, visits, orders, approvals, optional target */}
        <div>
          <p style={secMg}>{adm ? "Organization today" : "Your team today"}</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Metric label={adm ? "Employees" : "Team members"} value={adm ? "148" : "12"} sub={adm ? "across 6 regions" : "in your tree"} icon="PersonRounded" onClick={() => {}} />
            <Metric label="Present today" value={adm ? "132 / 148" : "10 / 12"} sub="punched in" subTone="#008000" icon="Schedule" onClick={() => {}} />
            <Metric label="Route coverage" value={adm ? "72%" : "68%"} sub={adm ? "486 visited · 675 planned" : "34 visited · 50 planned"} subTone="#995A00" icon="LocationMarker" onClick={() => {}} />
            <Metric label="Visits" value={adm ? "612" : "42"} sub={`${adm ? 428 : 26} productive`} subTone="#008000" icon="InventoryOutlined" onClick={() => {}} />
            <Metric label="Orders" value={adm ? "₹ 42.8L" : "₹ 5.9L"} sub={`${adm ? 214 : 26} orders`} subTone="#0081F2" icon="ShoppingCartOutlined" onClick={() => {}} />
            <Metric label="Pending approvals" value={adm ? "34" : "7"} sub="Orders, beats & leave" subTone="#995A00" icon="CheckCircle" onClick={() => {}} />
          </div>
          <div style={{ marginTop: 12 }}>
            <Metric label="Target achieved · optional" value={adm ? "64%" : "71%"} sub="MTD" subTone="#008000" icon="RewardsOutlined" onClick={() => {}} />
          </div>
          <p style={{ margin: "10px 0 0", fontSize: 12, color: "#8C8C8C", lineHeight: 1.45 }}>Route coverage shows — when no route is planned. Targets are optional; where none is set, cards read <strong>No target</strong>.</p>
        </div>

        {!adm && (
          <div>
            <p style={secMg}>Combined visits (tag-along)</p>
            <CardMg style={{ padding: 0, overflow: "hidden" }}>
              <ExceptionRow icon="PersonRounded" tone="#0081F2" title="Metro Wholesale · Thu 17 Jul" sub="With R. Kumar · scheduled" action="Open" />
              <div style={{ borderTop: "1px solid #F0F0F0" }} />
              <ExceptionRow icon="Edit" tone="#FFBF40" title="Feedback pending" sub="Anand Distributors · punched out 3:40 PM" action="Fill" />
            </CardMg>
          </div>
        )}

        {adm && (
          <div>
            <p style={secMg}>Top regions</p>
            <CardMg style={{ padding: 0, overflow: "hidden" }}>
              {[["North", "₹ 12.4L", 78], ["West", "₹ 9.8L", 66], ["South", "₹ 8.1L", 59]].map((r, i) => (
                <React.Fragment key={r[0]}>
                  {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                  <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px" }}>
                    <span style={{ flex: 1, fontSize: 14, fontWeight: 600, color: "#333" }}>{r[0]}</span>
                    <span style={{ fontSize: 13, color: "#666", fontVariantNumeric: "tabular-nums" }}>{r[1]}</span>
                    <div style={{ width: 64, height: 6, borderRadius: 3, background: "#EEE", overflow: "hidden" }}><div style={{ width: `${r[2]}%`, height: "100%", background: "#995A00" }} /></div>
                  </div>
                </React.Fragment>
              ))}
            </CardMg>
          </div>
        )}

        <HM1.Button variant="outlined" color="primary" label="Open reports" rightIcon={<HM1.Icon name="ArrowRight" size={18} color="#995A00" />} onClick={() => {}} style={{ width: "100%" }} />
      </div>
    </MScreen>
  );
}

/* ---------- S-AP1 Approval inbox (unified: beat/order/leave) ---------- */
const APPROVALS = [
  ["order", "ShoppingCartOutlined", "Order PO-24817", "R. Kumar · Krishna Stores · ₹ 5,540", "2h ago"],
  ["beat", "Calendar", "Beat: North BLR–West", "R. Kumar · 24 outlets · Weekly", "3h ago"],
  ["leave", "Schedule", "Leave: 22–23 Jul", "S. Iyer · Casual leave · 2 days", "5h ago"],
  ["order", "ShoppingCartOutlined", "Order PO-24820", "M. Das · Metro Wholesale · ₹ 84,000", "Yesterday"],
  ["order", "ShoppingCartOutlined", "Order PO-24821", "A. Rao · Gupta & Sons · ₹ 12,300", "Yesterday"],
];
function ApprovalInboxScreen({ role = "mgr", variant = "default" }) {
  const [filter, setFilter] = useStateMg("all");
  if (variant === "empty") return <MScreen role={role} title="Approvals" bell tab="approvals"><HM1.EmptyState icon="CheckCircle" title="All caught up" message="No pending approvals right now. New requests will appear here." /></MScreen>;
  if (variant === "loading") return <MScreen role={role} title="Approvals" bell tab="approvals"><div>{[0,1,2,3].map(i => <HM1.SkeletonRow key={i} />)}</div></MScreen>;
  const FILTERS = [["all", "All"], ["order", "Orders"], ["beat", "Beats"], ["leave", "Leave"]];
  const rows = filter === "all" ? APPROVALS : APPROVALS.filter((a) => a[0] === filter);
  return (
    <MScreen role={role} title="Approvals" bell bellCount={5} tab="approvals" offline={variant === "offline"}>
      <div style={{ padding: "12px 16px", background: "#fff", borderBottom: "1px solid #E5E5E5", fontSize: 13, color: "#666" }}>
        {role === "adm" ? "Org-wide" : "Your tree"} · <strong style={{ color: "#333" }}>{APPROVALS.length} pending</strong>
      </div>
      <div style={{ display: "flex", gap: 8, padding: 12, overflowX: "auto", background: "#fff", borderBottom: "1px solid #E5E5E5" }}>
        {FILTERS.map((f) => {
          const on = filter === f[0];
          return <span key={f[0]} onClick={() => setFilter(f[0])} style={{ flexShrink: 0, padding: "6px 14px", borderRadius: 999, fontSize: 13, fontWeight: 600, cursor: "pointer", border: `1px solid ${on ? "#995A00" : "#D9D9D9"}`, color: on ? "#995A00" : "#666", background: on ? "#995A001F" : "#fff" }}>{f[1]}</span>;
        })}
      </div>
      <div style={{ background: "#fff" }}>
        {rows.map((a, i) => (
          <React.Fragment key={i}>
            {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
            <HM1.ListRow leading={<span style={{ width: 36, height: 36, borderRadius: 8, background: "#995A001F", display: "flex", alignItems: "center", justifyContent: "center" }}><HM1.Icon name={a[1]} size={20} color="#995A00" /></span>}
              title={a[2]} subtitle={a[3]} meta={a[4]} trailing={<HM1.StatusChip status="pending" label="Pending" type="outlined" />} showChevron onClick={() => {}} />
          </React.Fragment>
        ))}
      </div>
    </MScreen>
  );
}

/* ---------- S-AP2 Approval detail (approve / edit / reject) ---------- */
function ApprovalDetailScreen({ role = "mgr", variant = "direct" }) {
  const [sheet, setSheet] = useStateMg(null); // 'reject' | 'edit'
  const escalated = variant === "escalated";
  return (
    <MScreen role={role} title="Order PO-24817" back tab="approvals" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: escalated ? "#0081F20D" : "#F7F7F7", border: `1px solid ${escalated ? "#AFD8FA" : "#E5E5E5"}`, borderRadius: 10, padding: 12 }}>
          <HM1.Icon name="InfoFilled" size={18} color={escalated ? "#0081F2" : "#8C8C8C"} />
          <span style={{ fontSize: 13, color: "#666", lineHeight: 1.45 }}>{escalated
            ? <React.Fragment>Routed to you because <strong style={{ color: "#333" }}>P. Nair</strong> (the parent manager) is on leave. Skip-level approvals happen only in this case.</React.Fragment>
            : <React.Fragment>You are <strong style={{ color: "#333" }}>R. Kumar's</strong> parent manager — only you can approve this. Edits are allowed now; none after approval.</React.Fragment>}</span>
        </div>
        {/* Summary first */}
        <CardMg style={{ padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div><div style={{ fontSize: 16, fontWeight: 700, color: "#333" }}>Krishna Stores</div><div style={{ fontSize: 13, color: "#666", marginTop: 2 }}>R. Kumar · PO · Aashirvaad (ITC)</div></div>
            <HM1.StatusChip status="pending" label="Pending" type="filled" />
          </div>
          <div style={{ display: "flex", gap: 16, marginTop: 14 }}>
            <div><div style={{ fontSize: 12, color: "#8C8C8C" }}>Order value</div><div style={{ fontSize: 18, fontWeight: 700, color: "#995A00" }}>₹ 5,540</div></div>
            <div><div style={{ fontSize: 12, color: "#8C8C8C" }}>Credit left</div><div style={{ fontSize: 18, fontWeight: 700, color: "#008000" }}>₹ 40,000</div></div>
          </div>
        </CardMg>
        {/* Critical deltas second */}
        <div>
          <p style={secMg}>Line items · 2</p>
          <CardMg style={{ padding: 0, overflow: "hidden" }}>
            {[["Aashirvaad Atta 10kg", "4 × ₹ 545", "₹ 2,180"], ["Fortune Oil 5L", "2 × ₹ 1,180", "₹ 2,360"]].map((l, i) => (
              <React.Fragment key={l[0]}>
                {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 16px", fontSize: 14 }}><span style={{ color: "#333" }}>{l[0]} <span style={{ color: "#8C8C8C" }}>{l[1]}</span></span><span style={{ fontWeight: 600, color: "#333" }}>{l[2]}</span></div>
              </React.Fragment>
            ))}
          </CardMg>
        </div>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: "#FFF6E5", border: "1px solid #FFD98A", borderRadius: 10, padding: 12 }}>
          <HM1.Icon name="InfoFilled" size={18} color="#995A00" /><span style={{ fontSize: 13, color: "#8A6D3B" }}>Above this SP's ₹ 4,000 avg order — confirm quantities before approving.</span>
        </div>
        <div>
          <p style={secMg}>Approval trail</p>
          <CardMg style={{ padding: 16 }}>
            <HM1.ApprovalTimeline steps={escalated
              ? [{ label: "Submitted", detail: "by R. Kumar", time: "10:24 AM", state: "done" }, { label: "P. Nair on leave", detail: "Routed one level up", time: "10:25 AM", state: "edited" }, { label: "Awaiting your approval", state: "current" }]
              : [{ label: "Submitted", detail: "by R. Kumar", time: "10:24 AM", state: "done" }, { label: "Awaiting your approval", state: "current" }]} />
          </CardMg>
        </div>
      </div>
      {/* Action controls last */}
      <FooterMg>
        <div style={{ display: "flex", gap: 8 }}>
          <HM1.Button variant="outlined" color="error" label="Reject" onClick={() => setSheet("reject")} style={{ flex: 1 }} />
          <HM1.Button variant="outlined" color="neutral" label="Edit" leftIcon={<HM1.Icon name="Edit" size={18} color="#333" />} onClick={() => setSheet("edit")} style={{ flex: 1 }} />
          <HM1.Button variant="filled" color="success" label="Approve" onClick={() => {}} style={{ flex: 1.4 }} />
        </div>
      </FooterMg>
      <HM1.BottomSheet open={sheet === "reject"} onClose={() => setSheet(null)} title="Reject request">
        <p style={{ fontSize: 14, color: "#666", margin: "0 0 12px" }}>Add a reason — the sales person will see this.</p>
        <HM1.TextField placeholder="e.g. Quantity too high for this outlet" multiline rows={3} value="" onChange={() => {}} />
        <div style={{ marginTop: 16 }}><HM1.Button variant="filled" color="error" label="Reject request" onClick={() => setSheet(null)} style={{ width: "100%" }} /></div>
      </HM1.BottomSheet>
      <HM1.BottomSheet open={sheet === "edit"} onClose={() => setSheet(null)} title="Edit before approving">
        <p style={{ fontSize: 14, color: "#666", margin: "0 0 12px" }}>Adjust quantities, then approve with edits.</p>
        {[["Aashirvaad Atta 10kg", 4], ["Fortune Oil 5L", 2]].map((l) => (
          <div key={l[0]} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0" }}>
            <span style={{ fontSize: 14, color: "#333" }}>{l[0]}</span>
            <div style={{ display: "inline-flex", alignItems: "center", border: "1px solid #995A00", borderRadius: 8, height: 34 }}>
              <button style={{ width: 32, height: 32, border: "none", background: "none", color: "#995A00", cursor: "pointer" }}><HM1.Icon name="Minus" size={16} color="#995A00" /></button>
              <span style={{ minWidth: 24, textAlign: "center", fontWeight: 700 }}>{l[1]}</span>
              <button style={{ width: 32, height: 32, border: "none", background: "none", color: "#995A00", cursor: "pointer" }}><HM1.Icon name="Add" size={16} color="#995A00" /></button>
            </div>
          </div>
        ))}
        <div style={{ marginTop: 16 }}><HM1.Button variant="filled" color="success" label="Approve with edits" onClick={() => setSheet(null)} style={{ width: "100%" }} /></div>
      </HM1.BottomSheet>
    </MScreen>
  );
}

Object.assign(window, { MgmtDashboardScreen, ApprovalInboxScreen, ApprovalDetailScreen });
