/* Humbee SFA — part 7: task types (Official Work), visit-type tracking, missed-visit audit,
   combined (tag-along) visits, Admin beat management, PO selector. Added per the confirmed change notes. */
const H4 = window.HumbeeDesignSystem_c38d59;
const Screen4 = window.SFA_Screen, Card4 = window.SFA_Card, MScreen4 = window.MScreen, CardMg4 = window.CardMg, FooterMg4 = window.FooterMg;
const { useState: useState4, useEffect: useEffect4 } = React;
const sec4 = { fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C", margin: "0 0 8px" };
const Footer4 = ({ children }) => <div style={{ position: "sticky", bottom: 0, background: "#fff", borderTop: "1px solid #E5E5E5", padding: 12 }}>{children}</div>;
const Note4 = ({ children, tone = "info" }) => {
  const T = { info: ["#F7F7F7", "#E5E5E5", "#666", "#0081F2", "InfoFilled"], warn: ["#FFF6E5", "#FFD98A", "#8A6D3B", "#995A00", "InfoFilled"] }[tone];
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: T[0], border: `1px solid ${T[1]}`, borderRadius: 10, padding: 12 }}>
      <H4.Icon name={T[4]} size={18} color={T[3]} /><span style={{ fontSize: 13, color: T[2], lineHeight: 1.45 }}>{children}</span>
    </div>
  );
};
const PLACEHOLDER = "Fields pending from the business team — shell only for now.";

/* ---------- S-OFF1 Official Work timer (task type: Official Work) ---------- */
function OfficialWorkScreen({ variant = "start" }) {
  const running = variant === "running";
  const [s, setS] = useState4(running ? 4128 : 0);
  useEffect4(() => { if (!running) return; const t = setInterval(() => setS((v) => v + 1), 1000); return () => clearInterval(t); }, [running]);
  const hh = Math.floor(s / 3600), mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0"), ss = String(s % 60).padStart(2, "0");
  const TYPES = [["meeting", "Internal meeting"], ["training", "Training"], ["collection", "Collection / follow-up"], ["other", "Other office work"]];
  const [type, setType] = useState4("meeting");
  return (
    <Screen4 title="Official work" back tab="today" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ background: running ? "#0081F20D" : "#fff", border: `1px solid ${running ? "#AFD8FA" : "#E5E5E5"}`, borderRadius: 12, padding: 18, textAlign: "center" }}>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: running ? "#0081F2" : "#8C8C8C" }}>{running ? "Official work in progress" : "Not started"}</div>
          <div style={{ fontSize: 40, fontWeight: 700, color: running ? "#0081F2" : "#BDBDBD", fontVariantNumeric: "tabular-nums", lineHeight: 1.15, marginTop: 4 }}>{hh}:{mm}:{ss}</div>
          <div style={{ fontSize: 13, color: "#666" }}>{running ? "Started 9:40 AM · tracked separately from outlet visits" : "Time is tracked from the moment you start"}</div>
        </div>
        <div>
          <p style={sec4}>Work type</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {TYPES.map((t) => {
              const on = type === t[0];
              return <button key={t[0]} type="button" onClick={() => setType(t[0])} style={{ padding: 14, borderRadius: 12, cursor: "pointer", textAlign: "left", background: on ? "#995A001F" : "#fff", border: `1.5px solid ${on ? "#995A00" : "#E5E5E5"}`, fontFamily: "var(--font-family-base)", fontSize: 14, fontWeight: 700, color: on ? "#995A00" : "#333" }}>{t[1]}</button>;
            })}
          </div>
        </div>
        <div>
          <p style={sec4}>Details</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <H4.TextField label="Purpose" placeholder="e.g. Distributor settlement meeting" value="" onChange={() => {}} />
            <H4.TextField label="Notes" placeholder="Optional" multiline rows={2} value="" onChange={() => {}} />
          </div>
        </div>
        <Note4>{PLACEHOLDER} Official work does not count as an outlet visit.</Note4>
      </div>
      <Footer4>
        {running
          ? <H4.Button variant="filled" color="error" label="End official work" leftIcon={<H4.Icon name="LogoutOutlined" size={20} color="#fff" />} onClick={() => {}} style={{ width: "100%" }} />
          : <H4.Button variant="filled" color="primary" label="Start official work" leftIcon={<H4.Icon name="Schedule" size={20} color="#fff" />} onClick={() => {}} style={{ width: "100%" }} />}
      </Footer4>
    </Screen4>
  );
}

/* ---------- S-OFF2 Official Work history ---------- */
function OfficialWorkHistoryScreen({ variant = "list" }) {
  if (variant === "empty") return <Screen4 title="Official work" back tab="more" noNav><H4.EmptyState icon="Schedule" title="No official work logged" message="Start an official-work task from Today to track non-sales time." actionLabel="Go to Today" onAction={() => {}} /></Screen4>;
  const ROWS = [
    ["Internal meeting", "15 Jul · 9:40 – 10:52 AM", "1h 12m", "completed", "Logged"],
    ["Training", "14 Jul · 3:00 – 5:30 PM", "2h 30m", "completed", "Logged"],
    ["Collection / follow-up", "12 Jul · 11:15 AM – 12:05 PM", "50m", "completed", "Logged"],
    ["Other office work", "11 Jul · 4:20 – 4:55 PM", "35m", "completed", "Logged"],
  ];
  return (
    <Screen4 title="Official work" back tab="more" noNav>
      <div style={{ display: "flex", gap: 10, padding: 16, background: "#fff", borderBottom: "1px solid #E5E5E5" }}>
        {[["5h 07m", "This week", "#0081F2"], ["4", "Tasks", "#995A00"]].map((s) => (
          <div key={s[1]} style={{ flex: 1, border: "1px solid #E5E5E5", borderRadius: 10, padding: "10px 12px" }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: s[2] }}>{s[0]}</div>
            <div style={{ fontSize: 12, color: "#666" }}>{s[1]}</div>
          </div>
        ))}
      </div>
      <div style={{ background: "#fff" }}>
        {ROWS.map((r, i) => (
          <React.Fragment key={i}>
            {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
            <H4.ListRow leading={<H4.Icon name="Schedule" size={22} color="#0081F2" />} title={r[0]} subtitle={r[1]} meta={r[2]} trailing={<H4.StatusChip status={r[3]} label={r[4]} type="outlined" />} showChevron onClick={() => {}} />
          </React.Fragment>
        ))}
      </div>
    </Screen4>
  );
}

/* ---------- S-VISIT2 Missed visit audit (no SP action; audit trail only) ---------- */
function MissedVisitAuditScreen({ role = "sp" }) {
  const sp = role === "sp";
  const ROWS = [
    ["Gupta & Sons", "Peenya · planned Mon 14 Jul", "Physical visit"],
    ["New Vaishnavi Mart", "Peenya · planned Mon 14 Jul", "Physical visit"],
    ["Sri Ganesh Traders", "Rajajinagar · planned Fri 11 Jul", "Telephonic call"],
  ];
  const Body = (
    <React.Fragment>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
        <Note4 tone="warn">Planned visits not completed by end of day are recorded as <strong>missed</strong>. No action is needed — the audit trail stays available for reporting.</Note4>
        <div style={{ display: "flex", gap: 10 }}>
          {[["3", "Missed", "#CC0000"], ["21", "Visited", "#008000"], ["88%", "Adherence", "#995A00"]].map((s) => (
            <div key={s[1]} style={{ flex: 1, background: "#fff", border: "1px solid #E5E5E5", borderRadius: 10, padding: "10px 12px" }}>
              <div style={{ fontSize: 20, fontWeight: 700, color: s[2] }}>{s[0]}</div>
              <div style={{ fontSize: 12, color: "#666" }}>{s[1]}</div>
            </div>
          ))}
        </div>
      </div>
      <p style={{ ...sec4, padding: "0 16px" }}>Missed this week{sp ? "" : " · R. Kumar"}</p>
      <div style={{ background: "#fff" }}>
        {ROWS.map((r, i) => (
          <React.Fragment key={r[0]}>
            {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
            <H4.ListRow leading={<H4.Icon name="Close" size={22} color="#CC0000" />} title={r[0]} subtitle={r[1]} trailing={<H4.StatusChip status="cancelled" label="Missed" type="outlined" />} meta={r[2]} />
          </React.Fragment>
        ))}
      </div>
    </React.Fragment>
  );
  return sp
    ? <Screen4 title="Missed visits" back tab="route" noNav>{Body}</Screen4>
    : <MScreen4 role={role} title="Missed visits" back tab="reports" noNav>{Body}</MScreen4>;
}

/* ---------- S-ORD1b PO selector (DP ordering direct from a manufacturer) ---------- */
function PoSelectorScreen({ variant = "list" }) {
  if (variant === "empty") return <Screen4 title="Select PO" back tab="orders" noNav><H4.EmptyState icon="InvoiceOutlined" title="No open POs" message="This distribution partner has no open PO with the manufacturer. Ask your manager to get one raised." actionLabel="Back to visit" onAction={() => {}} /></Screen4>;
  const POS = [
    ["PO-91204", "Aashirvaad (ITC)", "₹ 1,24,000 open", "raised 12 Jul", true],
    ["PO-91188", "Fortune (Adani)", "₹ 68,500 open", "raised 10 Jul", false],
    ["PO-91162", "Tata Consumer", "₹ 42,000 open", "raised 08 Jul", false],
  ];
  const [sel, setSel] = useState4("PO-91204");
  return (
    <Screen4 title="Select PO" back tab="orders" noNav>
      <div style={{ padding: 12, background: "#fff", borderBottom: "1px solid #E5E5E5", fontSize: 13, color: "#666", display: "flex", alignItems: "center", gap: 6 }}>
        <H4.Icon name="InventoryOutlined" size={16} color="#8C8C8C" /> Metro Wholesale · Distribution partner outlet
      </div>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        <Note4>A distribution partner orders <strong>direct from the manufacturer</strong> against an open PO. Manager approval is required before the order is created.</Note4>
        {POS.map((p) => {
          const on = sel === p[0];
          return (
            <button key={p[0]} type="button" onClick={() => setSel(p[0])} style={{ display: "flex", alignItems: "center", gap: 12, width: "100%", padding: 14, borderRadius: 12, cursor: "pointer", background: on ? "#995A001F" : "#fff", border: `1.5px solid ${on ? "#995A00" : "#E5E5E5"}`, fontFamily: "var(--font-family-base)", textAlign: "left" }}>
              <H4.Icon name={on ? "CheckCircle" : "InvoiceOutlined"} size={24} color={on ? "#995A00" : "#8C8C8C"} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>{p[0]}</div>
                <div style={{ fontSize: 13, color: "#666" }}>{p[1]} · {p[3]}</div>
              </div>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#008000", flexShrink: 0 }}>{p[2]}</span>
            </button>
          );
        })}
      </div>
      <Footer4><H4.Button variant="filled" color="primary" label="Continue with this PO" onClick={() => {}} style={{ width: "100%" }} /></Footer4>
    </Screen4>
  );
}

/* ---------- S-CVIS1 Combined visit (tag-along) scheduling — Manager ---------- */
function CombinedVisitScreen({ role = "mgr", step = "outlet" }) {
  const OUTLETS = [["Metro Wholesale", "Malleshwaram · Distribution partner"], ["Anand Distributors", "Rajajinagar · Dealer"], ["Sri Balaji Agency", "Yeshwanthpur · Dealer"], ["Krishna Stores", "Yeshwanthpur · Dealer"]];
  const [outlet, setOutlet] = useState4("Metro Wholesale");
  const [day, setDay] = useState4(17);
  const DAYS = [["16", "Wed"], ["17", "Thu"], ["18", "Fri"], ["21", "Mon"], ["22", "Tue"]];
  return (
    <MScreen4 role={role} title="Combined visit" back tab="team" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <H4.Stepper steps={[{ label: "Beat" }, { label: "Outlet" }, { label: "Day" }]} activeStep={step === "beat" ? 0 : step === "day" ? 2 : 1} size="small" />
        <div>
          <p style={sec4}>Beat</p>
          <H4.Select label="Beat under you" fullWidth value="nblrw" onChange={() => {}} options={[{ value: "nblrw", label: "NBLR-W-Malleshwaram-01 · R. Kumar (24)" }, { value: "peenya", label: "PNY-Industrial-02 · S. Iyer (18)" }]} />
        </div>
        <div>
          <p style={sec4}>Outlet under this beat</p>
          <CardMg4 style={{ padding: 0, overflow: "hidden" }}>
            {OUTLETS.map((o, i) => {
              const on = outlet === o[0];
              return (
                <React.Fragment key={o[0]}>
                  {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                  <div onClick={() => setOutlet(o[0])} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", cursor: "pointer", background: on ? "#995A000D" : "#fff" }}>
                    <H4.Icon name="InventoryOutlined" size={22} color={on ? "#995A00" : "#8C8C8C"} />
                    <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontSize: 15, fontWeight: 600, color: "#333" }}>{o[0]}</div><div style={{ fontSize: 12, color: "#8C8C8C" }}>{o[1]}</div></div>
                    <H4.Radio checked={on} onChange={() => setOutlet(o[0])} />
                  </div>
                </React.Fragment>
              );
            })}
          </CardMg4>
        </div>
        <div>
          <p style={sec4}>Combined-visit day</p>
          <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 2 }}>
            {DAYS.map((d) => {
              const on = day === Number(d[0]);
              return (
                <button key={d[0]} type="button" onClick={() => setDay(Number(d[0]))} style={{ flexShrink: 0, width: 64, padding: "10px 0", borderRadius: 12, cursor: "pointer", background: on ? "#995A00" : "#fff", border: `1.5px solid ${on ? "#995A00" : "#E5E5E5"}`, fontFamily: "var(--font-family-base)" }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: on ? "#FFE9C7" : "#8C8C8C" }}>{d[1]}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: on ? "#fff" : "#333" }}>{d[0]}</div>
                </button>
              );
            })}
          </div>
        </div>
        <Note4>The sales person keeps their own route. After outlet punch-out you'll be notified to fill the combined-visit feedback form.</Note4>
      </div>
      <FooterMg4><H4.Button variant="filled" color="primary" label={`Schedule tag-along · ${outlet} · Jul ${day}`} onClick={() => {}} style={{ width: "100%" }} /></FooterMg4>
    </MScreen4>
  );
}

/* ---------- S-CVIS2 Combined visit feedback (placeholder form) ---------- */
function CombinedVisitFeedbackScreen({ role = "mgr" }) {
  const [rating, setRating] = useState4("good");
  return (
    <MScreen4 role={role} title="Visit feedback" back tab="team" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10, background: "#0080000D", border: "1px solid #B7E0B7", borderRadius: 12, padding: 14 }}>
          <H4.Icon name="CheckCircle" size={22} color="#008000" />
          <div><div style={{ fontSize: 14, fontWeight: 700, color: "#448044" }}>Punch-out recorded · Metro Wholesale</div><div style={{ fontSize: 13, color: "#5B865B" }}>Tag-along with R. Kumar · 42 min on outlet</div></div>
        </div>
        <div>
          <p style={sec4}>Overall assessment</p>
          <H4.RadioGroup value={rating} onChange={setRating} row options={[{ value: "good", label: "Good" }, { value: "average", label: "Average" }, { value: "poor", label: "Needs work" }]} />
        </div>
        <div>
          <p style={sec4}>Observations</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <H4.TextField label="What went well" placeholder="e.g. Strong rapport, clean order pitch" multiline rows={2} value="" onChange={() => {}} />
            <H4.TextField label="What needs coaching" placeholder="e.g. Missed scheme explanation" multiline rows={2} value="" onChange={() => {}} />
            <H4.TextField label="Action for next visit" placeholder="Optional" value="" onChange={() => {}} />
          </div>
        </div>
        <Note4>{PLACEHOLDER}</Note4>
      </div>
      <FooterMg4><H4.Button variant="filled" color="primary" label="Submit feedback" onClick={() => {}} style={{ width: "100%" }} /></FooterMg4>
    </MScreen4>
  );
}

/* ---------- S-BEAT6 Admin beat management (create / assign / frequency / active-inactive) ---------- */
function AdminBeatMgmtScreen({ variant = "list" }) {
  const BEATS = [
    ["NBLR-W-Malleshwaram-01", "R. Kumar · 24 outlets · Weekly (Mon, Thu)", true, "Malleshwaram, Rajajinagar"],
    ["PNY-Industrial-02", "S. Iyer · 18 outlets · Fortnightly", true, "Peenya Phase 1–2"],
    ["YPR-Core-03", "M. Das · 12 outlets · Weekly (Tue)", false, "Yeshwanthpur"],
  ];
  if (variant === "empty") return <MScreen4 role="adm" title="Beats" bell tab="org"><H4.EmptyState icon="Calendar" title="No beats yet" message="Create a beat from assigned geography, or approve a beat submitted by a sales person." actionLabel="Create beat" onAction={() => {}} /></MScreen4>;
  if (variant === "edit") {
    return (
      <MScreen4 role="adm" title="Edit beat" back tab="org" noNav>
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
          <H4.TextField label="Beat name" value="NBLR-W-Malleshwaram-01" onChange={() => {}} helperText="Convention: AREA-DIRECTION-LOCALITY-NN" />
          <H4.Select label="Assigned sales person" fullWidth value="rk" onChange={() => {}} options={[{ value: "rk", label: "R. Kumar (North BLR–West)" }, { value: "si", label: "S. Iyer (Peenya)" }]} />
          <H4.Select label="Visit frequency" fullWidth value="weekly" onChange={() => {}} options={[{ value: "daily", label: "Daily" }, { value: "weekly", label: "Weekly" }, { value: "fortnightly", label: "Fortnightly" }, { value: "monthly", label: "Monthly" }]} />
          <CardMg4 style={{ padding: "8px 16px" }}><H4.ToggleSwitch label="Beat active" checked onChange={() => {}} /></CardMg4>
          <Note4 tone="warn">Beats are never deleted. Deactivating is a soft delete — the beat stops appearing for route planning, and all history stays in place.</Note4>
        </div>
        <FooterMg4>
          <div style={{ display: "flex", gap: 8 }}>
            <H4.Button variant="outlined" color="error" label="Deactivate" onClick={() => {}} style={{ flex: 1 }} />
            <H4.Button variant="filled" color="primary" label="Save changes" onClick={() => {}} style={{ flex: 1.4 }} />
          </div>
        </FooterMg4>
      </MScreen4>
    );
  }
  return (
    <MScreen4 role="adm" title="Beats" bell tab="org">
      <div style={{ padding: "12px 16px", background: "#fff", borderBottom: "1px solid #E5E5E5", fontSize: 13, color: "#666" }}>Org-wide · <strong style={{ color: "#333" }}>3 beats</strong> · Admin owns beat management</div>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        {BEATS.map((b) => (
          <CardMg4 key={b[0]} style={{ padding: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>{b[0]}</div>
                <div style={{ fontSize: 13, color: "#666", marginTop: 2 }}>{b[1]}</div>
                <div style={{ fontSize: 12, color: "#8C8C8C", marginTop: 2 }}>{b[3]}</div>
              </div>
              <H4.StatusChip status={b[2] ? "verified" : "cancelled"} label={b[2] ? "Active" : "Inactive"} type="outlined" />
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <H4.Button variant="outlined" color="neutral" size="small" label="Edit" onClick={() => {}} style={{ flex: 1 }} />
              <H4.Button variant="outlined" color={b[2] ? "error" : "success"} size="small" label={b[2] ? "Deactivate" : "Reactivate"} onClick={() => {}} style={{ flex: 1 }} />
            </div>
          </CardMg4>
        ))}
      </div>
      <H4.FAB iconName="Add" label="Create beat" onClick={() => {}} />
    </MScreen4>
  );
}

Object.assign(window, { OfficialWorkScreen, OfficialWorkHistoryScreen, MissedVisitAuditScreen, PoSelectorScreen, CombinedVisitScreen, CombinedVisitFeedbackScreen, AdminBeatMgmtScreen });
