/* Humbee SFA — Sales Person screens, part 6: Profile, Attendance history, Leave, Targets, Dashboard. */
const HM = window.HumbeeDesignSystem_c38d59;
const ScreenM = window.SFA_Screen, CardM = window.SFA_Card;
const { useState: useStateM } = React;
const secM = { fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C", margin: "0 0 8px" };
const FooterM = ({ children }) => <div style={{ position: "sticky", bottom: 0, background: "#fff", borderTop: "1px solid #E5E5E5", padding: 12 }}>{children}</div>;

/* ---------- S-PROFILE My profile ---------- */
function ProfileScreen() {
  const InfoRow = ({ icon, label, value }) => (
    <HM.ListRow leading={<HM.Icon name={icon} size={22} color="#995A00" />} title={value} subtitle={label} />
  );
  return (
    <ScreenM title="My profile" back tab="more" noNav bodyBg="#fff">
      <div style={{ padding: 24, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, borderBottom: "1px solid #F0F0F0" }}>
        <div style={{ width: 72, height: 72, borderRadius: "50%", background: "#995A00", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28, fontWeight: 700 }}>RK</div>
        <div style={{ fontSize: 18, fontWeight: 700, color: "#333" }}>Rahul Kumar</div>
        <HM.StatusChip status="verified" label="Sales Person · HB-SP-2048" type="outlined" />
      </div>
      <p style={{ ...secM, padding: "16px 16px 0", margin: 0 }}>Assignment</p>
      <InfoRow icon="PersonRounded" label="Reporting manager" value="A. Sharma" />
      <div style={{ borderTop: "1px solid #F0F0F0" }} />
      <InfoRow icon="LocationMarker" label="Geography scope (set by Admin)" value="Malleshwaram, Rajajinagar" />
      <div style={{ borderTop: "1px solid #F0F0F0" }} />
      <InfoRow icon="Call" label="Login number" value="+91 ·····3210" />
      <div style={{ borderTop: "1px solid #F0F0F0" }} />
      <InfoRow icon="Calendar" label="Joined" value="12 Mar 2024" />
      <p style={{ ...secM, padding: "16px 16px 0", margin: 0 }}>Account</p>
      <HM.ListRow leading={<HM.Icon name="Schedule" size={22} color="#666" />} title="Official work history" showChevron onClick={() => {}} />
      <div style={{ borderTop: "1px solid #F0F0F0" }} />
      <HM.ListRow leading={<HM.Icon name="NotificationsOutlined" size={22} color="#666" />} title="Notifications" trailing={<HM.ToggleSwitch checked onChange={() => {}} size="small" />} />
      <div style={{ borderTop: "1px solid #F0F0F0" }} />
      <HM.ListRow leading={<HM.Icon name="LogoutOutlined" size={22} color="#CC0000" />} title={<span style={{ color: "#CC0000" }}>Log out</span>} onClick={() => {}} />
    </ScreenM>
  );
}

/* ---------- S-ATT2 Attendance history ---------- */
function AttendanceHistoryScreen({ variant = "list" }) {
  if (variant === "empty") return <ScreenM title="Attendance" back tab="more" noNav><HM.EmptyState icon="Calendar" title="No records yet" message="Your punch-in history will appear here once you start marking attendance." /></ScreenM>;
  // status per day-of-month: p=present, l=late, a=absent, o=leave/off, undefined=future/no-data
  const S = { 1:"p",2:"p",3:"p",4:"p",5:"o",7:"p",8:"p",9:"p",10:"p",11:"a",12:"l",14:"p",15:"c" };
  const TONE = { p:"#008000", l:"#FFBF40", a:"#CC0000", o:"#8C8C8C", c:"#995A00" };
  const BG   = { p:"#0080001A", l:"#FFBF401A", a:"#CC00001A", o:"#F0F0F0", c:"#995A001F" };
  const firstDow = 2; // Jul 1 2026 = Tuesday (Sun=0)
  const cells = [];
  for (let i = 0; i < firstDow; i++) cells.push(null);
  for (let d = 1; d <= 31; d++) cells.push(d);
  const dow = ["S","M","T","W","T","F","S"];
  return (
    <ScreenM title="Attendance" back tab="more" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Month switcher */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <button style={arrowBtn}><HM.Icon name="KeyboardArrowLeft" size={22} color="#333" /></button>
          <span style={{ fontSize: 16, fontWeight: 700, color: "#333" }}>July 2026</span>
          <button style={arrowBtn}><HM.Icon name="KeyboardArrowRight" size={22} color="#333" /></button>
        </div>
        {/* Summary tiles */}
        <div style={{ display: "flex", gap: 8 }}>
          {[["11","Present","#008000"],["1","Late","#FFBF40"],["1","Absent","#CC0000"],["1","Leave","#8C8C8C"]].map((s) => (
            <div key={s[1]} style={{ flex: 1, textAlign: "center", border: "1px solid #E5E5E5", borderRadius: 10, padding: "8px 4px" }}>
              <div style={{ fontSize: 20, fontWeight: 700, color: s[2] }}>{s[0]}</div>
              <div style={{ fontSize: 11, color: "#666" }}>{s[1]}</div>
            </div>
          ))}
        </div>
        {/* Calendar grid */}
        <CardM style={{ padding: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 4, marginBottom: 4 }}>
            {dow.map((d, i) => <div key={i} style={{ textAlign: "center", fontSize: 11, fontWeight: 700, color: "#8C8C8C" }}>{d}</div>)}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 4 }}>
            {cells.map((d, i) => {
              if (!d) return <div key={i} />;
              const st = S[d], today = d === 15;
              return (
                <div key={i} style={{ aspectRatio: "1", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: today ? 800 : 600,
                  background: st ? BG[st] : "transparent", color: st ? TONE[st] : "#BDBDBD",
                  border: today ? "2px solid #995A00" : "1px solid transparent" }}>{d}</div>
              );
            })}
          </div>
        </CardM>
        {/* Legend */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 14px" }}>
          {[["#008000","Present"],["#FFBF40","Late"],["#CC0000","Absent"],["#8C8C8C","Leave"],["#995A00","Today"]].map((l) => (
            <span key={l[1]} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "#666" }}><span style={{ width: 10, height: 10, borderRadius: 3, background: l[0] }} />{l[1]}</span>
          ))}
        </div>
        {/* Selected-day detail */}
        <div>
          <p style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C", margin: "0 0 8px" }}>Tue, 15 Jul</p>
          <CardM style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 16px" }}><span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, color: "#333" }}><HM.Icon name="LocationMarker" size={18} color="#008000" /> Punched in</span><span style={{ fontSize: 14, fontWeight: 700, color: "#333" }}>9:12 AM</span></div>
            <div style={{ borderTop: "1px solid #F0F0F0" }} />
            <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 16px" }}><span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, color: "#333" }}><HM.Icon name="Schedule" size={18} color="#8C8C8C" /> On duty</span><span style={{ fontSize: 14, fontWeight: 700, color: "#995A00" }}>Currently active</span></div>
          </CardM>
        </div>
      </div>
    </ScreenM>
  );
}
const arrowBtn = { width: 36, height: 36, borderRadius: 8, border: "1px solid #E5E5E5", background: "#fff", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" };

/* ---------- S-LV1 Apply leave ---------- */
function ApplyLeaveScreen() {
  const [type, setType] = useStateM("casual");
  return (
    <ScreenM title="Apply leave" back tab="more" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <HM.Select label="Leave type" fullWidth value={type} onChange={setType} options={[{value:"casual",label:"Casual leave"},{value:"sick",label:"Sick leave"},{value:"earned",label:"Earned leave"}]} />
        <div style={{ display: "flex", gap: 12 }}>
          <HM.DateField label="From" value="22 Jul" onClick={() => {}} />
          <HM.DateField label="To" value="23 Jul" onClick={() => {}} />
        </div>
        <CardM style={{ padding: 12, display: "flex", alignItems: "center", gap: 8, background: "#F7F7F7" }}>
          <HM.Icon name="InfoFilled" size={18} color="#0081F2" /><span style={{ fontSize: 13, color: "#666" }}>2 days · balance after: 6 casual</span>
        </CardM>
        <HM.TextField label="Reason" placeholder="Add a short reason" multiline rows={3} value="" onChange={() => {}} />
        <CardM style={{ padding: 12, display: "flex", alignItems: "flex-start", gap: 8, background: "#F7F7F7" }}>
          <HM.Icon name="InfoFilled" size={18} color="#0081F2" /><span style={{ fontSize: 13, color: "#666", lineHeight: 1.45 }}>Goes to <strong style={{ color: "#333" }}>P. Nair</strong>, your reporting manager. If they're on leave it routes one level up automatically.</span>
        </CardM>
      </div>
      <FooterM><HM.Button variant="filled" color="primary" label="Submit for approval" onClick={() => {}} style={{ width: "100%" }} /></FooterM>
    </ScreenM>
  );
}

/* ---------- S-LV2 Leave status & history ---------- */
function LeaveStatusScreen() {
  const [tab, setTab] = useStateM("all");
  const rows = [
    ["Casual · 22–23 Jul", "Applied 2h ago · 2 days", "pending", "Pending"],
    ["Sick · 08 Jul", "1 day", "approved", "Approved"],
    ["Earned · 01–03 Jul", "3 days", "cancelled", "Rejected"],
  ];
  return (
    <ScreenM title="Leave" back tab="more" noNav>
      <div style={{ padding: 12, background: "#fff", borderBottom: "1px solid #E5E5E5", display: "flex", gap: 12, alignItems: "center", justifyContent: "space-between" }}>
        <HM.Tabs tabs={[{label:"All",value:"all"},{label:"Pending",value:"pn"},{label:"History",value:"hs"}]} value={tab} onChange={setTab} type="boxed" size="small" />
      </div>
      <div style={{ background: "#fff" }}>
        {rows.map((r, i) => (
          <React.Fragment key={i}>
            {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
            <HM.ListRow leading={<HM.Icon name="Calendar" size={22} color="#995A00" />} title={r[0]} subtitle={r[1]} trailing={<HM.StatusChip status={r[2]} label={r[3]} type="outlined" />} showChevron onClick={() => {}} />
          </React.Fragment>
        ))}
      </div>
      <HM.FAB iconName="Add" label="Apply leave" onClick={() => {}} />
    </ScreenM>
  );
}

/* ---------- S-TGT4 My targets — three types: sales (per manufacturer), new outlets, manufacturer leads ---------- */
function MyTargetsScreen({ variant = "default" }) {
  if (variant === "notarget") {
    return (
      <ScreenM title="My targets" back tab="more" noNav>
        <HM.EmptyState icon="RewardsOutlined" title="No target set for July" message="Targets are optional at Humbee. You can keep selling normally — your sales still count and show on your dashboard." actionLabel="View dashboard" onAction={() => {}} />
        <div style={{ padding: 16 }}>
          <p style={secM}>This month so far</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <HM.StatCard icon="ShoppingCartOutlined" label="MTD sales" value="₹ 2.1L" sub="28 orders" deltaTone="flat" />
            <HM.StatCard icon="InventoryOutlined" label="SKUs sold" value="14" sub="distinct SKUs" deltaTone="flat" />
          </div>
        </div>
      </ScreenM>
    );
  }
  return (
    <ScreenM title="My targets" back tab="more" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <CardM style={{ padding: 16, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
          <HM.Gauge value={68} max={100} size={180} label="August · sales target" />
          <div style={{ display: "flex", gap: 24, marginTop: 4 }}>
            <div style={{ textAlign: "center" }}><div style={{ fontSize: 18, fontWeight: 700, color: "#333" }}>₹ 3.4L</div><div style={{ fontSize: 12, color: "#8C8C8C" }}>Achieved</div></div>
            <div style={{ textAlign: "center" }}><div style={{ fontSize: 18, fontWeight: 700, color: "#333" }}>₹ 5.0L</div><div style={{ fontSize: 12, color: "#8C8C8C" }}>Target</div></div>
            <div style={{ textAlign: "center" }}><div style={{ fontSize: 18, fontWeight: 700, color: "#995A00" }}>₹ 1.6L</div><div style={{ fontSize: 12, color: "#8C8C8C" }}>To go</div></div>
          </div>
        </CardM>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <HM.StatCard icon="ShoppingCartOutlined" label="Volume MTD" value="182" sub="of 250 units" delta="73%" deltaTone="up" />
          <HM.StatCard icon="Schedule" label="Days left" value="16" sub="in this period" deltaTone="flat" />
        </div>
        <div>
          <p style={secM}>Sales target by manufacturer</p>
          <CardM style={{ padding: 0, overflow: "hidden" }}>
            {[["Aashirvaad (ITC)", 186000, 250000], ["Fortune (Adani)", 154000, 150000], ["Tata Consumer", 0, 100000]].map((m, i) => {
              const pct = Math.round(m[1] / m[2] * 100);
              const tone = pct >= 80 ? "#008000" : pct >= 50 ? "#995A00" : "#CC0000";
              return (
                <React.Fragment key={m[0]}>
                  {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                  <div style={{ padding: "12px 16px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 6 }}>
                      <span style={{ fontSize: 14, fontWeight: 600, color: "#333" }}>{m[0]}</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: tone }}>{pct}%</span>
                    </div>
                    <div style={{ height: 6, borderRadius: 3, background: "#EEE", overflow: "hidden" }}><div style={{ width: `${Math.min(100, pct)}%`, height: "100%", background: tone }} /></div>
                    <div style={{ fontSize: 12, color: "#8C8C8C", marginTop: 4 }}>₹ {(m[1] / 1000).toFixed(0)}k of ₹ {(m[2] / 1000).toFixed(0)}k · amount based</div>
                  </div>
                </React.Fragment>
              );
            })}
          </CardM>
        </div>
        <div>
          <p style={secM}>Other targets</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[["InventoryOutlined", "New outlets onboarded", "6 of 8", 75, "MTD · verified outlets only", "Onboard outlet"], ["RewardsOutlined", "Manufacturer leads", "7 of 10", 70, "MTD · 2 per week pace", "Capture lead"]].map((t) => (
              <CardM key={t[1]} style={{ padding: 14 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ width: 38, height: 38, borderRadius: 10, background: "#995A001F", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><HM.Icon name={t[0]} size={20} color="#995A00" /></div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14.5, fontWeight: 700, color: "#333" }}>{t[1]}</div>
                    <div style={{ fontSize: 12, color: "#8C8C8C" }}>{t[4]}</div>
                  </div>
                  <span style={{ fontSize: 15, fontWeight: 800, color: "#995A00", flexShrink: 0 }}>{t[2]}</span>
                </div>
                <div style={{ height: 6, borderRadius: 3, background: "#EEE", overflow: "hidden", margin: "10px 0" }}><div style={{ width: `${t[3]}%`, height: "100%", background: t[3] >= 80 ? "#008000" : "#995A00" }} /></div>
                <HM.Button variant="outlined" color="primary" size="small" label={t[5]} onClick={() => {}} style={{ width: "100%" }} />
              </CardM>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: "#F7F7F7", border: "1px solid #E5E5E5", borderRadius: 10, padding: 12 }}>
          <HM.Icon name="InfoFilled" size={18} color="#0081F2" /><span style={{ fontSize: 13, color: "#666", lineHeight: 1.45 }}>Achievement is calculated by Humbee and shown here read-only.</span>
        </div>
      </div>
    </ScreenM>
  );
}

/* ---------- S-DASH-SP Sales Person dashboard ---------- */
function DashboardScreen({ variant = "default" }) {
  if (variant === "loading") return <ScreenM title="Dashboard" bell tab="more"><div style={{ padding: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>{[0,1,2,3].map(i => <HM.Skeleton key={i} height={96} radius={12} />)}</div></ScreenM>;
  return (
    <ScreenM title="Dashboard" bell tab="more" offline={variant === "offline"}>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ fontSize: 14, color: "#666" }}>Your month at a glance · July</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <HM.StatCard icon="Schedule" iconColor="#008000" label="Attendance" value="18 / 19" sub="days present" delta="95%" deltaTone="up" onClick={() => {}} />
          <HM.StatCard icon="Schedule" iconColor="#0081F2" label="Official work" value="6h 20m" sub="this month" deltaTone="flat" onClick={() => {}} />
          <HM.StatCard icon="LocationMarker" iconColor="#995A00" label="Route coverage" value="82%" sub="21 visited · 3 missed" delta="+6%" deltaTone="up" onClick={() => {}} />
          <HM.StatCard icon="ShoppingCartOutlined" iconColor="#0081F2" label="Orders" value="₹ 3.4L" sub="42 orders · submitted" delta="+8%" deltaTone="up" onClick={() => {}} />
          <HM.StatCard icon="RewardsOutlined" iconColor="#995A00" label="Target" value="68%" sub="₹ 3.4L / 5.0L" delta="-2%" deltaTone="down" onClick={() => {}} />
        </div>
        <div>
          <p style={secM}>Leave status</p>
          <CardM style={{ padding: 0, overflow: "hidden" }}>
            <HM.ListRow leading={<HM.Icon name="Calendar" size={22} color="#995A00" />} title="Casual · 22–23 Jul" subtitle="2 days" trailing={<HM.StatusChip status="pending" label="Pending" type="outlined" />} showChevron onClick={() => {}} />
          </CardM>
        </div>
      </div>
    </ScreenM>
  );
}

/* ---------- S-DASH-DRILL Metric drill-down (orders) ---------- */
function DashDrillScreen() {
  const rows = [
    ["PO-24817", "Krishna Stores", "₹ 5,540", "pending", "Pending"],
    ["PO-24816", "Metro Wholesale", "₹ 84,000", "approved", "Approved"],
    ["PO-24815", "Sri Balaji Agency", "₹ 12,360", "partially-completed", "Edited"],
    ["PO-24810", "Gupta & Sons", "₹ 9,800", "not-verified", "PO failed"],
  ];
  return (
    <ScreenM title="Orders" back tab="more" noNav>
      <div style={{ padding: 16 }}>
        <CardM style={{ padding: 16, display: "flex", justifyContent: "space-around", textAlign: "center" }}>
          <div><div style={{ fontSize: 20, fontWeight: 700, color: "#333" }}>42</div><div style={{ fontSize: 12, color: "#8C8C8C" }}>Orders</div></div>
          <div><div style={{ fontSize: 20, fontWeight: 700, color: "#995A00" }}>₹ 3.4L</div><div style={{ fontSize: 12, color: "#8C8C8C" }}>Value</div></div>
          <div><div style={{ fontSize: 20, fontWeight: 700, color: "#FFBF40" }}>7</div><div style={{ fontSize: 12, color: "#8C8C8C" }}>Pending</div></div>
        </CardM>
      </div>
      <p style={{ ...secM, padding: "0 16px" }}>Recent orders</p>
      <div style={{ background: "#fff" }}>
        {rows.map((r, i) => (
          <React.Fragment key={r[0]}>
            {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
            <HM.ListRow title={`${r[0]} · ${r[1]}`} subtitle={r[2]} trailing={<HM.StatusChip status={r[3]} label={r[4]} type="outlined" />} showChevron onClick={() => {}} />
          </React.Fragment>
        ))}
      </div>
    </ScreenM>
  );
}

Object.assign(window, { ProfileScreen, AttendanceHistoryScreen, ApplyLeaveScreen, LeaveStatusScreen, MyTargetsScreen, DashboardScreen, DashDrillScreen });
