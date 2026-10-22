/* Humbee SFA — Manager & Admin screens, part C: oversight ops (route, attendance, leave, targets, more). */
const HM3 = window.HumbeeDesignSystem_c38d59;
const MScreen3 = window.MScreen, CardMg3 = window.CardMg, secMg3 = window.secMg, FooterMg3 = window.FooterMg;
const { useState: useStateOps } = React;

/* ---------- S-ROUTE5 Team route / live coverage ---------- */
function TeamRouteScreen({ role = "mgr", variant = "default" }) {
  if (variant === "empty") return <MScreen3 role={role} title="Team coverage" bell tab="reports"><HM3.EmptyState icon="LocationMarker" title="No active routes" message="Coverage appears once your team punches in and starts their routes today." /></MScreen3>;
  if (variant === "loading") return <MScreen3 role={role} title="Team coverage" bell tab="reports"><div>{[0,1,2,3].map(i => <HM3.SkeletonRow key={i} />)}</div></MScreen3>;
  const TEAM = [
    ["R. Kumar", "North BLR–West", 4, 6, "on", "9:12 AM"],
    ["S. Iyer", "Peenya", 2, 5, "on", "9:04 AM"],
    ["M. Das", "Yeshwanthpur", 5, 5, "on", "8:58 AM"],
    ["A. Rao", "Malleshwaram", 0, 6, "off", "—"],
  ];
  return (
    <MScreen3 role={role} title="Team coverage" bell tab="reports" offline={variant === "offline"}>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <HM3.MapPreview height={150} label={`${role === "adm" ? "Org" : "Team"} · live positions`} />
        <div style={{ display: "flex", gap: 12 }}>
          {[["3/4", "On route", "#008000"], ["11/22", "Visited", "#995A00"], ["50%", "Coverage", "#0081F2"]].map((s) => (
            <div key={s[1]} style={{ flex: 1, textAlign: "center", border: "1px solid #E5E5E5", borderRadius: 10, padding: "10px 4px", background: "#fff" }}>
              <div style={{ fontSize: 20, fontWeight: 700, color: s[2] }}>{s[0]}</div><div style={{ fontSize: 11, color: "#666" }}>{s[1]}</div>
            </div>
          ))}
        </div>
        <div>
          <p style={secMg3}>Sales persons</p>
          <CardMg3 style={{ padding: 0, overflow: "hidden" }}>
            {TEAM.map((t, i) => (
              <React.Fragment key={t[0]}>
                {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                <HM3.ListRow
                  leading={<span style={{ position: "relative", width: 40, height: 40, borderRadius: "50%", background: t[4] === "on" ? "#995A00" : "#BDBDBD", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 13 }}>{t[0].split(" ").map(w=>w[0]).join("")}<span style={{ position: "absolute", right: -1, bottom: -1, width: 12, height: 12, borderRadius: "50%", background: t[4] === "on" ? "#008000" : "#BDBDBD", border: "2px solid #fff" }} /></span>}
                  title={t[0]} subtitle={`${t[1]} · in ${t[5]}`}
                  trailing={<span style={{ fontSize: 13, fontWeight: 700, color: t[2] === t[3] ? "#008000" : "#995A00" }}>{t[2]}/{t[3]}</span>} showChevron onClick={() => {}} />
              </React.Fragment>
            ))}
          </CardMg3>
        </div>
      </div>
    </MScreen3>
  );
}

/* ---------- S-ATT3 (team) / S-ATT4 (all + export) Attendance ---------- */
function TeamAttendanceScreen({ role = "mgr", variant = "default" }) {
  const adm = role === "adm";
  const title = adm ? "All attendance" : "Team attendance";
  if (variant === "empty") return <MScreen3 role={role} title={title} bell tab="reports"><HM3.EmptyState icon="Calendar" title="No attendance yet" message="Records appear as your team punches in today." /></MScreen3>;
  if (variant === "loading") return <MScreen3 role={role} title={title} bell tab="reports"><div>{[0,1,2,3,4].map(i => <HM3.SkeletonRow key={i} />)}</div></MScreen3>;
  const ROWS = [
    ["R. Kumar", "9:12 AM", "MG Road", "verified", "On duty"],
    ["S. Iyer", "9:04 AM", "Peenya", "verified", "On duty"],
    ["M. Das", "10:46 AM", "Yeshwanthpur", "pending", "Late punch-in"],
    ["A. Rao", "—", "—", "default", "No punch-in yet"],
  ];
  return (
    <MScreen3 role={role} title={title} bell tab="reports" offline={variant === "offline"}>
      <div style={{ padding: 12, background: "#fff", borderBottom: "1px solid #E5E5E5", display: "flex", alignItems: "center", gap: 8 }}>
        <HM3.DateField label="" value="Tue, 15 Jul" onClick={() => {}} style={{ flex: 1 }} />
        {adm && <HM3.Button variant="outlined" color="primary" size="small" label="Export" leftIcon={<HM3.Icon name="DownloadOutlined" size={18} color="#995A00" />} onClick={() => {}} />}
      </div>
      <div style={{ display: "flex", gap: 12, padding: 16, background: "#fff", borderBottom: "1px solid #E5E5E5" }}>
        {[[adm ? "126" : "6", "On duty", "#008000"], [adm ? "9" : "1", "After 9 AM", "#FFBF40"], [adm ? "7" : "1", "No punch-in", "#8C8C8C"]].map((s) => (
          <div key={s[1]} style={{ flex: 1, textAlign: "center", border: "1px solid #E5E5E5", borderRadius: 10, padding: "8px 4px" }}><div style={{ fontSize: 20, fontWeight: 700, color: s[2] }}>{s[0]}</div><div style={{ fontSize: 11, color: "#666" }}>{s[1]}</div></div>
        ))}
      </div>
      <div style={{ padding: 12, display: "flex", alignItems: "flex-start", gap: 8, background: "#F7F7F7", borderBottom: "1px solid #E5E5E5" }}>
        <HM3.Icon name="InfoFilled" size={18} color="#0081F2" /><span style={{ fontSize: 13, color: "#666", lineHeight: 1.45 }}>Punch timings are <strong style={{ color: "#333" }}>informational</strong>. The 9–6 window is a signal for you — it isn't enforced and nothing is blocked by it.</span>
      </div>
      <div style={{ background: "#fff" }}>
        {ROWS.map((r, i) => (
          <React.Fragment key={r[0]}>
            {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
            <HM3.ListRow leading={<HM3.Icon name="PersonRounded" size={22} color="#8C8C8C" />} title={r[0]} subtitle={r[1] === "—" ? "No punch-in" : `In ${r[1]} · ${r[2]}`} trailing={<HM3.StatusChip status={r[3]} label={r[4]} type="outlined" />} />
          </React.Fragment>
        ))}
      </div>
    </MScreen3>
  );
}

/* ---------- S-ORD7 Order detail (management scope) ---------- */
function OrderDetailMgmtScreen({ role = "mgr" }) {
  return (
    <MScreen3 role={role} title="PO-24817" back tab="reports" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <CardMg3 style={{ padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div><div style={{ fontSize: 16, fontWeight: 700, color: "#333" }}>Krishna Stores</div><div style={{ fontSize: 13, color: "#666" }}>R. Kumar · Aashirvaad (ITC) · 15 Jul</div></div>
            <HM3.StatusChip status="approved" label="Approved" type="filled" />
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "#995A00", marginTop: 12 }}>₹ 5,540</div>
        </CardMg3>
        <div>
          <p style={secMg3}>Status</p>
          <CardMg3 style={{ padding: 16 }}>
            <HM3.ApprovalTimeline steps={[
              { label: "Submitted", detail: "by R. Kumar", time: "10:24 AM", state: "done" },
              { label: "Approved", detail: role === "adm" ? "by P. Nair (Manager)" : "by you", time: "11:02 AM", state: "done" },
              { label: "Sent to PO/DP", time: "11:03 AM", state: "current" },
            ]} />
          </CardMg3>
        </div>
        {role === "adm" && (
          <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: "#F7F7F7", borderRadius: 10, padding: 12 }}>
            <HM3.Icon name="InfoFilled" size={18} color="#0081F2" /><span style={{ fontSize: 13, color: "#666" }}>Admin can override or re-submit failed orders across the org.</span>
          </div>
        )}
      </div>
      <FooterMg3><HM3.Button variant="outlined" color="neutral" label="Back to orders" onClick={() => {}} style={{ width: "100%" }} /></FooterMg3>
    </MScreen3>
  );
}

/* ---------- S-LV3 Team leave status & history ---------- */
function TeamLeaveScreen({ role = "mgr", variant = "default" }) {
  if (variant === "empty") return <MScreen3 role={role} title="Team leave" bell tab="reports"><HM3.EmptyState icon="Schedule" title="No leave records" message="Leave requests and history for your team appear here." /></MScreen3>;
  const ROWS = [
    ["S. Iyer", "22–23 Jul · Casual", "pending", "Pending"],
    ["M. Das", "18 Jul · Sick", "approved", "Approved"],
    ["A. Rao", "10–11 Jul · Casual · routed from P. Nair (on leave)", "pending", "Pending"],
    ["V. Menon", "12 Jul · Casual · highest level", "approved", "Auto-approved"],
    ["R. Kumar", "5 Jul · Earned", "approved", "Approved"],
  ];
  return (
    <MScreen3 role={role} title="Team leave" bell tab="reports" offline={variant === "offline"}>
      <div style={{ display: "flex", gap: 8, padding: 12, overflowX: "auto", background: "#fff", borderBottom: "1px solid #E5E5E5" }}>
        {["All", "Pending", "Approved", "Auto-approved", "Rejected"].map((c, i) => (
          <span key={c} style={{ flexShrink: 0, padding: "6px 14px", borderRadius: 999, fontSize: 13, fontWeight: 600, cursor: "pointer", border: `1px solid ${i === 0 ? "#995A00" : "#D9D9D9"}`, color: i === 0 ? "#995A00" : "#666", background: i === 0 ? "#995A001F" : "#fff" }}>{c}</span>
        ))}
      </div>
      <div style={{ background: "#fff" }}>
        {ROWS.map((r, i) => (
          <React.Fragment key={i}>
            {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
            <HM3.ListRow leading={<span style={{ width: 36, height: 36, borderRadius: "50%", background: "#F0F0F0", color: "#666", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 12 }}>{r[0].split(" ").map(w=>w[0]).join("")}</span>}
              title={r[0]} subtitle={r[1]} trailing={<HM3.StatusChip status={r[2]} label={r[3]} type="outlined" />} showChevron onClick={() => {}} />
          </React.Fragment>
        ))}
      </div>
    </MScreen3>
  );
}

/* ---------- S-TGT1 Set target — three target types (Sales · New outlets · Manufacturer leads) ---------- */
const TGT_TYPES = [
  ["sales", "Sales target", "ShoppingCartOutlined", "Amount or volume, per manufacturer"],
  ["outlets", "New outlets onboarded", "InventoryOutlined", "Count of verified new outlets, MTD"],
  ["leads", "Manufacturer leads", "RewardsOutlined", "Leads captured, MTD or weekly"],
];
const MFRS = [["itc", "Aashirvaad (ITC)"], ["adani", "Fortune (Adani Wilmar)"], ["tata", "Tata Consumer"], ["hul", "HUL"]];
function SetTargetScreen({ role = "mgr", type = "sales" }) {
  const [kind, setKind] = useStateOps(type);
  const [basis, setBasis] = useStateOps("amount");
  const [mfrs, setMfrs] = useStateOps(["itc", "adani"]);
  const [cadence, setCadence] = useStateOps("mtd");
  const toggleMfr = (id) => setMfrs((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  const unit = basis === "amount" ? "₹" : "units";
  return (
    <MScreen3 role={role} title="Set target" back tab="reports" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <p style={secMg3}>Sales person</p>
          <CardMg3 style={{ padding: 14, display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ width: 40, height: 40, borderRadius: "50%", background: "#995A00", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 }}>RK</span>
            <div style={{ flex: 1 }}><div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>R. Kumar</div><div style={{ fontSize: 13, color: "#666" }}>Sales Person · {role === "adm" ? "North BLR–West" : "your reporting tree"}</div></div>
            <a href="#" style={{ fontSize: 13, color: "#995A00", fontWeight: 700 }}>Change</a>
          </CardMg3>
        </div>
        <div>
          <p style={secMg3}>Target type</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {TGT_TYPES.map((t) => {
              const on = kind === t[0];
              return (
                <button key={t[0]} type="button" onClick={() => setKind(t[0])} style={{ display: "flex", alignItems: "center", gap: 12, textAlign: "left", padding: "12px 13px", borderRadius: 12, cursor: "pointer", background: on ? "#995A0014" : "#fff", border: `1.5px solid ${on ? "#995A00" : "#E5E5E5"}`, fontFamily: "var(--font-family-base)" }}>
                  <div style={{ width: 38, height: 38, borderRadius: 10, background: on ? "#995A001F" : "#F5F5F5", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><HM3.Icon name={t[2]} size={20} color={on ? "#995A00" : "#8C8C8C"} /></div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14.5, fontWeight: 800, color: on ? "#995A00" : "#333" }}>{t[1]}</div>
                    <div style={{ fontSize: 12, color: "#8C8C8C" }}>{t[3]}</div>
                  </div>
                  {on && <HM3.Icon name="CheckCircle" size={20} color="#995A00" />}
                </button>
              );
            })}
          </div>
        </div>
        {kind === "sales" && (
          <React.Fragment>
            <HM3.RadioGroup label="Target basis" value={basis} onChange={setBasis} row options={[{ value: "amount", label: "Amount (₹)" }, { value: "volume", label: "Volume (units)" }]} />
            <div>
              <p style={secMg3}>Manufacturers · from Humbee API</p>
              <CardMg3 style={{ padding: 0, overflow: "hidden" }}>
                {MFRS.map((m, i) => {
                  const on = mfrs.includes(m[0]);
                  return (
                    <React.Fragment key={m[0]}>
                      {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                      <div style={{ padding: "10px 14px", background: on ? "#995A0008" : "#fff" }}>
                        <div onClick={() => toggleMfr(m[0])} style={{ display: "flex", alignItems: "center", gap: 12, cursor: "pointer", minHeight: 44 }}>
                          <HM3.Checkbox checked={on} onChange={() => toggleMfr(m[0])} />
                          <span style={{ flex: 1, fontSize: 14.5, fontWeight: 600, color: "#333" }}>{m[1]}</span>
                          {on && <span style={{ fontSize: 12, color: "#8C8C8C" }}>{basis === "amount" ? "₹ / month" : "units / month"}</span>}
                        </div>
                        {on && <HM3.TextField label="" placeholder={basis === "amount" ? "e.g. 250000" : "e.g. 600"} value={basis === "amount" ? "250000" : "600"} onChange={() => {}} startAdornment={<span style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>{unit}</span>} />}
                      </div>
                    </React.Fragment>
                  );
                })}
              </CardMg3>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 13 }}>
                <span style={{ color: "#8C8C8C" }}>Total monthly target</span>
                <strong style={{ color: "#995A00" }}>{basis === "amount" ? "₹ 5,00,000" : "1,200 units"}</strong>
              </div>
            </div>
          </React.Fragment>
        )}
        {kind === "outlets" && (
          <React.Fragment>
            <HM3.TextField label="New outlets to onboard (MTD)" placeholder="e.g. 8" value="8" onChange={() => {}} helperText="Counted month-to-date, only after Admin verifies each outlet" />
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {["Grocery / kirana", "Wholesale", "Chemist", "Any category"].map((c, i) => (
                <span key={c} style={{ padding: "7px 12px", borderRadius: 999, fontSize: 13, fontWeight: 700, border: `1px solid ${i === 3 ? "#995A00" : "#D9D9D9"}`, color: i === 3 ? "#995A00" : "#666", background: i === 3 ? "#995A001F" : "#fff" }}>{c}</span>
              ))}
            </div>
          </React.Fragment>
        )}
        {kind === "leads" && (
          <React.Fragment>
            <HM3.RadioGroup label="Measured" value={cadence} onChange={setCadence} row options={[{ value: "mtd", label: "Month-to-date" }, { value: "weekly", label: "Weekly" }]} />
            <HM3.TextField label={cadence === "mtd" ? "Leads per month" : "Leads per week"} placeholder={cadence === "mtd" ? "e.g. 10" : "e.g. 3"} value={cadence === "mtd" ? "10" : "3"} onChange={() => {}} helperText="Each lead is captured by the SP on the lead form (manufacturer, product, contact, interest)" />
            <div>
              <p style={secMg3}>Manufacturers in scope</p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {MFRS.map((m) => { const on = mfrs.includes(m[0]); return <span key={m[0]} onClick={() => toggleMfr(m[0])} style={{ padding: "7px 12px", borderRadius: 999, fontSize: 13, fontWeight: 700, cursor: "pointer", border: `1px solid ${on ? "#995A00" : "#D9D9D9"}`, color: on ? "#995A00" : "#666", background: on ? "#995A001F" : "#fff" }}>{m[1]}</span>; })}
              </div>
            </div>
          </React.Fragment>
        )}
        <HM3.Select label="Period" fullWidth value="aug" onChange={() => {}} options={[{ value: "aug", label: "August 2026" }, { value: "sep", label: "September 2026" }]} />
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: "#F7F7F7", borderRadius: 10, padding: 12 }}>
          <HM3.Icon name="InfoFilled" size={18} color="#0081F2" /><span style={{ fontSize: 13, color: "#666", lineHeight: 1.45 }}>Targets are optional — an SP with none still sells normally. Achievement is calculated by Humbee and shown read-only.</span>
        </div>
      </div>
      <FooterMg3>
        <div style={{ display: "flex", gap: 8 }}>
          <HM3.Button variant="outlined" color="neutral" label="Remove" onClick={() => {}} style={{ flex: 1 }} />
          <HM3.Button variant="filled" color="primary" label="Save target" onClick={() => {}} style={{ flex: 1.6 }} />
        </div>
      </FooterMg3>
    </MScreen3>
  );
}

/* ---------- S-TGT3 Team targets & achievement — by target type ---------- */
function TeamTargetsScreen({ role = "mgr", variant = "default", type = "sales" }) {
  const [kind, setKind] = useStateOps(type);
  if (variant === "loading") return <MScreen3 role={role} title="Targets" bell tab="reports"><div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>{[0,1,2].map(i => <HM3.Skeleton key={i} height={72} radius={12} />)}</div></MScreen3>;
  const DATA = {
    sales: { unit: "₹", rows: [["R. Kumar", 340000, 500000], ["S. Iyer", 410000, 450000], ["M. Das", 180000, 400000], ["A. Rao", 95000, 0]], fmt: (v) => `₹ ${(v / 100000).toFixed(1)}L`, gaugeLabel: role === "adm" ? "Org MTD sales" : "Team MTD sales" },
    outlets: { unit: "", rows: [["R. Kumar", 6, 8], ["S. Iyer", 9, 8], ["M. Das", 3, 6], ["A. Rao", 1, 0]], fmt: (v) => `${v} outlets`, gaugeLabel: "New outlets MTD" },
    leads: { unit: "", rows: [["R. Kumar", 7, 10], ["S. Iyer", 11, 10], ["M. Das", 4, 8], ["A. Rao", 2, 0]], fmt: (v) => `${v} leads`, gaugeLabel: "Leads captured MTD" },
  }[kind];
  const withTgt = DATA.rows.filter((r) => r[2] > 0);
  const totAch = withTgt.reduce((s, r) => s + r[1], 0), totTgt = withTgt.reduce((s, r) => s + r[2], 0);
  return (
    <MScreen3 role={role} title="Targets" bell tab="reports" offline={variant === "offline"}>
      <div style={{ padding: 12, background: "#fff", borderBottom: "1px solid #E5E5E5" }}>
        <HM3.Tabs tabs={[{ label: "Sales", value: "sales" }, { label: "New outlets", value: "outlets" }, { label: "Leads", value: "leads" }]} value={kind} onChange={setKind} type="boxed" size="small" />
      </div>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <CardMg3 style={{ padding: 16, display: "flex", alignItems: "center", gap: 16 }}>
          <HM3.Gauge value={Math.round(totAch / totTgt * 100)} max={100} size={120} label={DATA.gaugeLabel} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: "#666" }}>Achieved</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: "#995A00" }}>{DATA.fmt(totAch)}</div>
            <div style={{ fontSize: 12, color: "#8C8C8C" }}>of {DATA.fmt(totTgt)} target · {DATA.rows.length - withTgt.length} without target</div>
          </div>
        </CardMg3>
        <div>
          <p style={secMg3}>By sales person</p>
          <CardMg3 style={{ padding: 0, overflow: "hidden" }}>
            {DATA.rows.map((r, i) => {
              const none = r[2] === 0;
              const pct = none ? 0 : Math.round(r[1] / r[2] * 100);
              const tone = pct >= 80 ? "#008000" : pct >= 50 ? "#995A00" : "#CC0000";
              return (
                <React.Fragment key={r[0]}>
                  {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                  <div style={{ padding: "12px 16px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 14, fontWeight: 600, color: "#333" }}>{r[0]}</span>
                      {none ? <HM3.StatusChip status="default" label="No target" type="outlined" /> : <span style={{ fontSize: 13, fontWeight: 700, color: tone }}>{pct}%</span>}
                    </div>
                    {!none && <div style={{ height: 6, borderRadius: 3, background: "#EEE", overflow: "hidden" }}><div style={{ width: `${Math.min(100, pct)}%`, height: "100%", background: tone }} /></div>}
                    <div style={{ fontSize: 12, color: "#8C8C8C", marginTop: 4 }}>{none ? `${DATA.fmt(r[1])} · targets are optional` : `${DATA.fmt(r[1])} of ${DATA.fmt(r[2])}`}</div>
                  </div>
                </React.Fragment>
              );
            })}
          </CardMg3>
        </div>
      </div>
      <HM3.FAB iconName="Add" label="Set target" onClick={() => {}} />
    </MScreen3>
  );
}

/* ---------- Management More (profile / logout entry) ---------- */
function MgmtMoreScreen({ role = "mgr" }) {
  const adm = role === "adm";
  const items = adm
    ? [["PersonRounded", "My profile"], ["Calendar", "Beat management"], ["Dashboard", "Org tree"], ["RewardsOutlined", "Targets"], ["InventoryOutlined", "Outlet verification"], ["SettingsOutlined", "Settings"], ["NotificationsOutlined", "Notifications"]]
    : [["PersonRounded", "My profile"], ["PersonRounded", "My team"], ["PersonRounded", "Combined visits"], ["RewardsOutlined", "Targets"], ["Schedule", "Team leave"], ["NotificationsOutlined", "Notifications"]];
  return (
    <MScreen3 role={role} title="More" tab="more">
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <CardMg3 style={{ padding: 16, display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ width: 52, height: 52, borderRadius: "50%", background: "#995A00", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 18 }}>{adm ? "VM" : "PN"}</span>
          <div style={{ flex: 1 }}><div style={{ fontSize: 17, fontWeight: 700, color: "#333" }}>{adm ? "V. Menon" : "P. Nair"}</div><div style={{ fontSize: 13, color: "#666" }}>{adm ? "Admin · Org-wide" : "Manager · North Bengaluru"}</div></div>
        </CardMg3>
        <CardMg3 style={{ padding: 0, overflow: "hidden" }}>
          {items.map((it, i) => (
            <React.Fragment key={it[1]}>
              {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
              <HM3.ListRow leading={<HM3.Icon name={it[0]} size={22} color="#995A00" />} title={it[1]} showChevron onClick={() => {}} />
            </React.Fragment>
          ))}
        </CardMg3>
        <HM3.Button variant="outlined" color="error" label="Log out" leftIcon={<HM3.Icon name="LogoutOutlined" size={20} color="#CC0000" />} onClick={() => {}} style={{ width: "100%" }} />
      </div>
    </MScreen3>
  );
}

Object.assign(window, { TeamRouteScreen, TeamAttendanceScreen, OrderDetailMgmtScreen, TeamLeaveScreen, SetTargetScreen, TeamTargetsScreen, MgmtMoreScreen });
