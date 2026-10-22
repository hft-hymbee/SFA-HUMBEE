/* Humbee SFA — Sales Person screens, part 1: Auth + Today hub. Exports to window. */
const H = window.HumbeeDesignSystem_c38d59;
const { useState, useEffect } = React;

/* Shared scaffold: fills the PhoneFrame body. */
function Screen({ title, back, bell, bellCount, tab, offline, children, noNav, bodyBg = "#F5F5F5" }) {
  return (
    <React.Fragment>
      <H.TopAppBar title={title} onBack={back ? () => {} : undefined} onBell={bell ? () => {} : undefined} bellCount={bellCount} />
      {offline && <H.OfflineBanner />}
      <div style={{ flex: 1, overflowY: "auto", background: bodyBg }}>{children}</div>
      {!noNav && <H.BottomNav active={tab} onNav={() => {}} />}
    </React.Fragment>
  );
}
const Card = ({ children, style }) => <div style={{ background: "#fff", border: "1px solid #E5E5E5", borderRadius: 12, ...style }}>{children}</div>;
const secLabel = { fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C", margin: "0 0 8px" };

/* ---------- S-A2 Login (phone + OTP only) ---------- */
function LoginScreen({ error }) {
  const [phone, setPhone] = useState("98450 03210");
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#fff" }}>
      <div style={{ background: "#995A00", padding: "40px 24px 28px", color: "#fff" }}>
        <div style={{ background: "#fff", borderRadius: 14, padding: "14px 18px", display: "inline-flex", alignItems: "center", marginBottom: 16 }}>
          <img src="../../assets/logo.svg" alt="Humbee" style={{ width: 168, display: "block" }} />
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "#fff" }}>Sales Force Automation</div>
        <div style={{ fontSize: 14, color: "#FFE9C7", marginTop: 2 }}>Sign in to start your day</div>
      </div>
      <div style={{ flex: 1, padding: 24, display: "flex", flexDirection: "column", gap: 18 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "#333" }}>Log in</h1>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#666" }}>Sign in to start your day</p>
        </div>
        {error && (
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start", background: "#CC00000D", border: "1px solid #F3B0B0", borderRadius: 8, padding: 12 }}>
            <H.Icon name="Warning" size={20} color="#CC0000" />
            <span style={{ fontSize: 13, color: "#CC0000", lineHeight: 1.4 }}>This number isn't registered with Humbee. Check the number, or contact your manager.</span>
          </div>
        )}
        <H.TextField label="Mobile number" placeholder="98765 43210" value={phone} onChange={(e) => setPhone(e.target.value)} error={error}
          startAdornment={<span style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>+91</span>} helperText="We'll send a 6-digit OTP to this number" />
        <div style={{ marginTop: 4 }}>
          <H.Button variant="filled" color="primary" label="Send OTP" onClick={() => {}} style={{ width: "100%" }} disabled={phone.replace(/\D/g, "").length < 10} />
        </div>
      </div>
      <div style={{ padding: 16, textAlign: "center", fontSize: 12, color: "#8C8C8C" }}>Number not working? Contact your manager</div>
    </div>
  );
}

/* ---------- S-A3 OTP verification ---------- */
function OtpScreen({ error }) {
  const [otp, setOtp] = useState(error ? "0428" : "042");
  const [secs, setSecs] = useState(24);
  useEffect(() => { if (secs <= 0) return; const t = setTimeout(() => setSecs((s) => s - 1), 1000); return () => clearTimeout(t); }, [secs]);
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#fff" }}>
      <H.TopAppBar title="Verify OTP" onBack={() => {}} />
      <div style={{ flex: 1, padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: "#333" }}>Enter the code</h1>
          <p style={{ margin: "6px 0 0", fontSize: 15, color: "#666" }}>We sent a 6-digit code to <strong style={{ color: "#333" }}>+91 ·····3210</strong></p>
        </div>
        <H.OTPInput length={6} value={otp} onChange={setOtp} error={error} />
        {error && <span style={{ fontSize: 13, color: "#CC0000" }}>That code isn't right. Check and re-enter.</span>}
        <div style={{ fontSize: 14, color: "#666" }}>
          {secs > 0 ? <span>Resend code in <strong style={{ color: "#333" }}>0:{String(secs).padStart(2, "0")}</strong></span>
            : <a href="#" style={{ color: "#995A00", fontWeight: 700 }}>Resend code</a>}
        </div>
        <div style={{ marginTop: "auto" }}>
          <H.Button variant="filled" color="primary" label="Verify & continue" onClick={() => {}} style={{ width: "100%" }} disabled={otp.replace(/\s/g,"").length < 6} />
        </div>
      </div>
    </div>
  );
}

/* ---------- S-HOME Today (shared body pieces) ---------- */
function Greeting() {
  return (
    <div style={{ padding: "16px 16px 4px" }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: "#333" }}>Hi, Rahul</div>
      <div style={{ fontSize: 14, color: "#666" }}>Tuesday, 15 Jul · North Bengaluru beat</div>
    </div>
  );
}
function AttendanceCard({ state }) {
  if (state === "in") {
    return (
      <Card style={{ padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: "50%", background: "#0080001A", display: "flex", alignItems: "center", justifyContent: "center" }}><H.Icon name="CheckCircle" size={24} color="#008000" /></div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>Punched in</div>
            <div style={{ fontSize: 13, color: "#666" }}>Since 9:12 AM · MG Road</div>
          </div>
          <H.StatusChip status="verified" label="On duty" type="outlined" />
        </div>
        <H.Button variant="outlined" color="neutral" label="Punch out" size="small" onClick={() => {}} style={{ width: "100%", marginTop: 12 }} />
      </Card>
    );
  }
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <div style={{ width: 44, height: 44, borderRadius: "50%", background: "#FFF6E5", display: "flex", alignItems: "center", justifyContent: "center" }}><H.Icon name="Schedule" size={24} color="#995A00" /></div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>Not punched in</div>
          <div style={{ fontSize: 13, color: "#666" }}>Punch in to start your day</div>
        </div>
      </div>
      <H.Button variant="filled" color="primary" label="Punch in" leftIcon={<H.Icon name="LocationMarker" size={20} color="#fff" />} onClick={() => {}} style={{ width: "100%" }} />
    </Card>
  );
}
function RouteCard({ locked }) {
  return (
    <Card style={{ padding: 16, position: "relative", opacity: locked ? 0.55 : 1 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>Today's route</span>
        <span style={{ fontSize: 13, color: "#666" }}>{locked ? "12 outlets" : "3 / 12 visited"}</span>
      </div>
      <div style={{ height: 6, borderRadius: 3, background: "#EEE", overflow: "hidden", marginBottom: 12 }}>
        <div style={{ width: locked ? "0%" : "25%", height: "100%", background: "#995A00" }} />
      </div>
      {!locked && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <H.Icon name="LocationPin" size={20} color="#CC0000" />
          <div style={{ flex: 1 }}><div style={{ fontSize: 14, fontWeight: 600, color: "#333" }}>Next: Krishna Stores</div><div style={{ fontSize: 12, color: "#8C8C8C" }}>Yeshwanthpur · 1.4 km</div></div>
        </div>
      )}
      {locked
        ? <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#995A00", fontWeight: 700 }}><H.Icon name="Lock" size={18} color="#995A00" /> Punch in to unlock your route</div>
        : <H.Button variant="filled" color="primary" label="Resume route" onClick={() => {}} style={{ width: "100%" }} />}
    </Card>
  );
}
/* Task type — Sales vs Official Work (locked until punch-in). */
function TaskTypeCard({ locked }) {
  const [task, setTask] = useState("sales");
  const TASKS = [["sales", "Sales", "InventoryOutlined", "Run your route & place orders"], ["official", "Official work", "Schedule", "Meetings, training, collections"]];
  return (
    <Card style={{ padding: 12, opacity: locked ? 0.55 : 1 }}>
      <div style={{ display: "flex", gap: 10 }}>
        {TASKS.map((t) => {
          const on = !locked && task === t[0];
          return (
            <button key={t[0]} type="button" disabled={locked} onClick={() => setTask(t[0])}
              style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 6, padding: 12, borderRadius: 10, cursor: locked ? "not-allowed" : "pointer", textAlign: "left", background: on ? "#995A001F" : "#fff", border: `1.5px solid ${on ? "#995A00" : "#E5E5E5"}`, fontFamily: "var(--font-family-base)" }}>
              <H.Icon name={t[2]} size={22} color={on ? "#995A00" : "#8C8C8C"} />
              <span style={{ fontSize: 14, fontWeight: 700, color: on ? "#995A00" : "#333" }}>{t[1]}</span>
              <span style={{ fontSize: 12, color: "#8C8C8C", lineHeight: 1.3 }}>{t[3]}</span>
            </button>
          );
        })}
      </div>
      <div style={{ fontSize: 12, color: "#8C8C8C", marginTop: 10 }}>{locked ? "Punch in to choose your task for the day" : "Official work is time-tracked separately from outlet visits"}</div>
    </Card>
  );
}
function RequestsCard() {
  return (
    <Card style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px" }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>My requests</span>
        <a href="#" style={{ fontSize: 13, color: "#995A00", fontWeight: 700 }}>View all</a>
      </div>
      <div style={{ borderTop: "1px solid #F0F0F0" }} />
      <H.ListRow leading={<H.Icon name="RewardsOutlined" size={22} color="#995A00" />} title="Beat: North BLR–West" subtitle="Submitted 2h ago" trailing={<H.StatusChip status="pending" label="Pending" />} />
      <div style={{ borderTop: "1px solid #F0F0F0" }} />
      <H.ListRow leading={<H.Icon name="ShoppingCartOutlined" size={22} color="#995A00" />} title="Order PO-24817" subtitle="Sunrise Traders" trailing={<H.StatusChip status="approved" label="Approved" />} />
    </Card>
  );
}
function TargetsCard() {
  return (
    <Card style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
      <H.Gauge value={68} max={100} size={120} label="Monthly target" />
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, color: "#666" }}>Achieved</div>
        <div style={{ fontSize: 22, fontWeight: 700, color: "#995A00" }}>₹ 3.4L</div>
        <div style={{ fontSize: 12, color: "#8C8C8C" }}>of ₹ 5.0L target</div>
        <a href="#" style={{ fontSize: 13, color: "#995A00", fontWeight: 700, display: "inline-block", marginTop: 6 }}>View targets</a>
      </div>
    </Card>
  );
}

function TodayScreen({ variant = "locked" }) {
  if (variant === "loading") {
    return (
      <Screen title="Today" bell bellCount={3} tab="today">
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
          <H.Skeleton width="50%" height={22} />
          <H.Skeleton width="100%" height={96} radius={12} />
          <H.Skeleton width="100%" height={120} radius={12} />
          <H.Skeleton width="100%" height={88} radius={12} />
        </div>
      </Screen>
    );
  }
  const locked = variant === "locked";
  return (
    <Screen title="Today" bell bellCount={3} tab="today" offline={variant === "offline"}>
      <Greeting />
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
        {locked && <H.LockBanner onAction={() => {}} />}
        <div><p style={secLabel}>Attendance</p><AttendanceCard state={locked ? "out" : "in"} /></div>
        <div><p style={secLabel}>Task type</p><TaskTypeCard locked={locked} /></div>
        <div><p style={secLabel}>Route</p><RouteCard locked={locked} /></div>
        <div><p style={secLabel}>Requests</p><RequestsCard /></div>
        <div><p style={secLabel}>Targets</p><TargetsCard /></div>
      </div>
    </Screen>
  );
}

Object.assign(window, { SFA_Screen: Screen, SFA_Card: Card, LoginScreen, OtpScreen, TodayScreen });
