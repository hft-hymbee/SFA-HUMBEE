/* Humbee SFA — Sales Person screens, part 2: Attendance + Route. */
const H2 = window.HumbeeDesignSystem_c38d59;
const Screen2 = window.SFA_Screen, Card2 = window.SFA_Card;
const secLabel2 = { fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C", margin: "0 0 8px" };

/* In-frame confirmation modal (contained to the phone frame — not the fixed DS Modal). */
function ConfirmSheet({ onDuty, onCancel, onConfirm }) {
  const tone = onDuty ? "#CC0000" : "#995A00";
  return (
    <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16, zIndex: 60 }}>
      <div style={{ background: "#fff", borderRadius: 16, width: "100%", maxWidth: 320, padding: 20, textAlign: "center", boxShadow: "0px 11px 15px -7px rgba(0,0,0,0.2),0px 24px 38px 3px rgba(0,0,0,0.14)", fontFamily: "var(--font-family-base)" }}>
        <div style={{ width: 56, height: 56, borderRadius: "50%", background: tone + "1A", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 12px" }}>
          <H2.Icon name={onDuty ? "LogoutOutlined" : "Fingerprint"} size={28} color={tone} />
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, color: "#333" }}>{onDuty ? "Punch out now?" : "Punch in now?"}</div>
        <p style={{ fontSize: 14, color: "#666", margin: "6px 0 4px", lineHeight: 1.4 }}>{onDuty ? "Ends your duty for the day. Your exit time and location will be recorded." : "Starts your day. Your time and GPS location will be recorded."}</p>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, fontSize: 13, color: "#8C8C8C", marginBottom: 16 }}><H2.Icon name="LocationMarker" size={16} color="#8C8C8C" /> MG Road, Bengaluru · ±8 m</div>
        <div style={{ display: "flex", gap: 10 }}>
          <H2.Button variant="outlined" color="neutral" label="Cancel" onClick={onCancel} style={{ flex: 1 }} />
          <H2.Button variant="filled" color={onDuty ? "error" : "primary"} label={onDuty ? "Punch out" : "Punch in"} onClick={onConfirm} style={{ flex: 1 }} />
        </div>
      </div>
    </div>
  );
}

const FooterSFA = ({ children }) => <div style={{ position: "sticky", bottom: 0, background: "#fff", borderTop: "1px solid #E5E5E5", padding: 12, flexShrink: 0 }}>{children}</div>;

/* ---------- S-ATT1 Punch in/out ---------- */
function PunchScreen({ variant = "in" }) {
  // variant: 'locating' | 'in' (ready to punch in) | 'out' (currently on duty → punch out) | 'confirm' | 'confirm-out'
  const [confirm, setConfirm] = React.useState(variant === "confirm" || variant === "confirm-out");
  const base = variant === "confirm-out" ? "out" : variant === "confirm" ? "in" : variant;
  const onDuty = base === "out";
  const locating = base === "locating";
  return (
    <Screen2 title="Attendance" back tab="today" noNav>
      {confirm && <ConfirmSheet onDuty={onDuty} onCancel={() => setConfirm(false)} onConfirm={() => setConfirm(false)} />}
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16, minHeight: "100%", boxSizing: "border-box" }}>
        <p style={secLabel2}>Your location</p>
        <H2.LocationCaptureCard status={locating ? "locating" : "captured"} address="MG Road, Bengaluru 560001" coords="12.9758° N, 77.6096° E" accuracy="±8 m" time={onDuty ? "9:12 AM" : undefined} />
        {onDuty && (
          <Card2 style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 40, height: 40, borderRadius: "50%", background: "#0080001A", display: "flex", alignItems: "center", justifyContent: "center" }}><H2.Icon name="Schedule" size={22} color="#008000" /></div>
            <div style={{ flex: 1 }}><div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>On duty since 9:12 AM</div><div style={{ fontSize: 13, color: "#666" }}>Elapsed 3h 48m</div></div>
          </Card2>
        )}
        <div style={{ position: "relative", width: 280, height: 280, margin: "auto auto 0", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <style>{"@keyframes hb-ripple{0%{transform:translate(-50%,-50%) scale(.8);opacity:.5}100%{transform:translate(-50%,-50%) scale(1.5);opacity:0}}@keyframes hb-spin2{to{transform:rotate(360deg)}}"}</style>
          {(() => {
            const grad = locating ? "radial-gradient(circle at 35% 28%, #EDEDED 0%, #D9D9D9 60%, #BDBDBD 100%)"
              : onDuty ? "radial-gradient(circle at 35% 28%, #F16D6D 0%, #CC0000 55%, #8F0000 100%)"
              : "radial-gradient(circle at 35% 28%, #C9871F 0%, #995A00 55%, #6E4200 100%)";
            const glow = onDuty ? "rgba(204,0,0,0.40)" : "rgba(153,90,0,0.40)";
            const ripple = onDuty ? "rgba(204,0,0,0.30)" : "rgba(153,90,0,0.28)";
            const dash = locating ? "#C9C9C9" : onDuty ? "#CC0000" : "#995A00";
            const shadow = `0 14px 32px ${glow}, inset 0 3px 8px rgba(255,255,255,0.35), inset 0 -10px 18px rgba(0,0,0,0.28)`;
            return (
              <React.Fragment>
                {!locating && [0, 1, 2].map((i) => (
                  <span key={i} style={{ position: "absolute", top: "50%", left: "50%", width: 200, height: 200, borderRadius: "50%", border: `2px solid ${ripple}`, transform: "translate(-50%,-50%)", animation: `hb-ripple 2.4s ease-out ${i * 0.8}s infinite` }} />
                ))}
                <span style={{ position: "absolute", top: "50%", left: "50%", width: 252, height: 252, borderRadius: "50%", border: "1px solid #EAE3D6", transform: "translate(-50%,-50%)" }} />
                <span style={{ position: "absolute", top: "50%", left: "50%", width: 188, height: 188, borderRadius: "50%", border: `2px dashed ${dash}`, opacity: locating ? 0.5 : 1, transform: "translate(-50%,-50%)" }} />
                <button type="button" disabled={locating} onClick={() => setConfirm(true)}
                  style={{ position: "relative", width: 168, height: 168, borderRadius: "50%", border: "none", cursor: locating ? "not-allowed" : "pointer", background: grad, color: "#fff", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, boxShadow: shadow, fontFamily: "var(--font-family-base)" }}>
                  {locating
                    ? <span style={{ width: 40, height: 40, display: "inline-block", border: "3px solid rgba(255,255,255,0.6)", borderTopColor: "#fff", borderRadius: "50%", animation: "hb-spin2 0.8s linear infinite" }} />
                    : <H2.Icon name="Fingerprint" size={46} color="#fff" />}
                  <span style={{ fontSize: 18, fontWeight: 700 }}>{locating ? "Locating…" : onDuty ? "Punch out" : "Punch in"}</span>
                </button>
              </React.Fragment>
            );
          })()}
        </div>
        <div style={{ textAlign: "center", flexShrink: 0 }}>
          <span style={{ fontSize: 13, color: "#8C8C8C" }}>{locating ? "Fetching precise GPS location" : "Tap to record your attendance with GPS"}</span>
        </div>
      </div>
    </Screen2>
  );
}

/* ---------- S-ATT1b Punch blocked ---------- */
function PunchBlockedScreen({ reason = "permission" }) {
  // reason: 'permission' | 'gpsoff' | 'geofence'
  const R = {
    permission: { icon: "Lock", title: "Location permission needed", msg: "Humbee needs location access to record attendance. Enable it in your settings to punch in.", cta: "Open settings" },
    gpsoff: { icon: "LocationMarker", title: "Turn on GPS", msg: "Your device location is off. Turn on GPS, then retry to capture your punch-in.", cta: "Retry" },
    geofence: { icon: "LocationPin", title: "You're outside the allowed area", msg: "You appear to be 1.2 km from your assigned start point. Move closer, or contact your manager.", cta: "Retry location" },
  }[reason];
  return (
    <Screen2 title="Attendance" back tab="today" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16, minHeight: "100%", boxSizing: "border-box" }}>
        {reason === "geofence" && <H2.MapPreview height={140} label="Allowed area: 300 m radius" />}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 8, padding: "24px 16px" }}>
          <div style={{ width: 72, height: 72, borderRadius: "50%", background: "#CC00000D", display: "flex", alignItems: "center", justifyContent: "center" }}><H2.Icon name={R.icon} size={36} color="#CC0000" /></div>
          <h3 style={{ margin: "4px 0 0", fontSize: 18, fontWeight: 700, color: "#333" }}>{R.title}</h3>
          <p style={{ margin: 0, fontSize: 14, color: "#666", maxWidth: 280, lineHeight: 1.45 }}>{R.msg}</p>
        </div>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: "#FFF6E5", border: "1px solid #FFD98A", borderRadius: 12, padding: 12, marginTop: "auto" }}>
          <H2.Icon name="Lock" size={20} color="#995A00" />
          <span style={{ fontSize: 13, color: "#8A6D3B", lineHeight: 1.4 }}>Route and orders stay locked until you punch in.</span>
        </div>
      </div>
      <FooterSFA><H2.Button variant="filled" color="primary" label={R.cta} leftIcon={<H2.Icon name={reason === "permission" ? "SettingsOutlined" : "Autorenew"} size={20} color="#fff" />} onClick={() => {}} style={{ width: "100%" }} /></FooterSFA>
    </Screen2>
  );
}

/* ---------- S-ROUTE1 / S-ROUTE3 Today's route / run ---------- */
const OUTLETS = [
  { n: 1, name: "Metro Wholesale", area: "Malleshwaram · 0.8 km", status: "done", chip: ["completed", "Order placed"], type: "Physical", planned: true },
  { n: 2, name: "Anand Distributors", area: "Rajajinagar · 1.1 km", status: "done", chip: ["partially-completed", "No stock"], type: "Telephonic", planned: true },
  { n: 3, name: "Sri Balaji Agency", area: "Yeshwanthpur · 1.3 km", status: "done", chip: ["completed", "Order placed"], type: "Physical", planned: false },
  { n: 4, name: "Krishna Stores", area: "Yeshwanthpur · 1.4 km", status: "next", chip: null, planned: true },
  { n: 5, name: "Gupta & Sons", area: "Peenya · 2.6 km", status: "todo", chip: null, planned: true },
  { n: 6, name: "New Vaishnavi Mart", area: "Peenya · 2.9 km", status: "todo", chip: null, planned: true },
];
function OutletRow({ o }) {
  const done = o.status === "done", next = o.status === "next";
  const badgeBg = done ? "#0080001A" : next ? "#995A00" : "#F0F0F0";
  const badgeColor = done ? "#008000" : next ? "#fff" : "#8C8C8C";
  return (
    <H2.ListRow
      leading={<span style={{ width: 30, height: 30, borderRadius: "50%", background: badgeBg, color: badgeColor, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 13 }}>{done ? <H2.Icon name="Check" size={18} color="#008000" /> : o.n}</span>}
      title={o.name} subtitle={`${o.area}${o.type ? " · " + o.type : ""}${o.planned ? "" : " · Unplanned"}`}
      trailing={o.chip ? <H2.StatusChip status={o.chip[0]} label={o.chip[1]} type="outlined" /> : next ? <H2.StatusChip status="pending" label="Next" type="filled" /> : null}
      showChevron onClick={() => {}} />
  );
}
function RouteScreen({ variant = "running" }) {
  if (variant === "loading") {
    return <Screen2 title="Today's route" bell tab="route"><div>{[0,1,2,3,4].map(i => <H2.SkeletonRow key={i} />)}</div></Screen2>;
  }
  if (variant === "locked") {
    return (
      <Screen2 title="Today's route" bell tab="route">
        <div style={{ padding: 16 }}><H2.LockBanner onAction={() => {}} /></div>
        <div style={{ opacity: 0.5, pointerEvents: "none" }}>
          {OUTLETS.slice(0, 4).map((o) => <React.Fragment key={o.n}><OutletRow o={{ ...o, status: "todo", chip: null }} /><div style={{ borderTop: "1px solid #F0F0F0" }} /></React.Fragment>)}
        </div>
      </Screen2>
    );
  }
  if (variant === "empty") {
    return (
      <Screen2 title="Today's route" bell tab="route">
        <H2.EmptyState icon="LocationMarker" title="No route planned" message="Plan today's run from your approved beats to get started." actionLabel="Plan route" onAction={() => {}} />
      </Screen2>
    );
  }
  if (variant === "error") {
    return <Screen2 title="Today's route" bell tab="route"><H2.ErrorState onRetry={() => {}} /></Screen2>;
  }
  // running
  return (
    <Screen2 title="Today's route" bell tab="route">
      <div style={{ padding: "16px 16px 8px", background: "#fff", borderBottom: "1px solid #E5E5E5" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <H2.StatusChip status="verified" label="Today's beat" type="outlined" />
          <span style={{ flex: 1 }} />
          <a href="#" style={{ fontSize: 13, fontWeight: 700, color: "#995A00" }}>Change beat</a>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>NBLR-W-Malleshwaram-01</span>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#995A00" }}>3 / 6 visited</span>
        </div>
        <div style={{ height: 6, borderRadius: 3, background: "#EEE", overflow: "hidden" }}><div style={{ width: "50%", height: "100%", background: "#995A00" }} /></div>
      </div>
      <div style={{ background: "#fff" }}>
        {OUTLETS.map((o, i) => <React.Fragment key={o.n}>{i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}<OutletRow o={o} /></React.Fragment>)}
      </div>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
        <H2.Button variant="outlined" color="primary" label="Add unplanned visit" leftIcon={<H2.Icon name="Add" size={20} color="#995A00" />} onClick={() => {}} style={{ width: "100%" }} />
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: "#FFF6E5", border: "1px solid #FFD98A", borderRadius: 10, padding: 12 }}>
          <H2.Icon name="InfoFilled" size={18} color="#995A00" />
          <span style={{ fontSize: 13, color: "#8A6D3B", lineHeight: 1.45 }}>Anything still pending at end of day is recorded as a <strong>missed visit</strong> — no action needed from you. <a href="#" style={{ color: "#995A00", fontWeight: 700 }}>See missed visits</a></span>
        </div>
      </div>
    </Screen2>
  );
}

/* ---------- S-ROUTE2 Choose beat (today's assigned beat, or another of your beats = unplanned) ---------- */
const TODAY_BEATS = [
  { name: "NBLR-W-Malleshwaram-01", meta: "Mon · 6 outlets · 4.2 km", outlets: 6 },
  { name: "NBLR-W-Rajajinagar-02", meta: "Mon · 8 outlets · 6.0 km", outlets: 8 },
];
const OTHER_BEATS = [
  { name: "PNY-IND-Peenya-01", meta: "Assigned for Wed · 9 outlets" },
  { name: "NBLR-N-Yeshwanthpur-03", meta: "Assigned for Thu · 7 outlets" },
  { name: "NBLR-W-Jalahalli-05", meta: "Assigned for Sat · 5 outlets" },
];
function BeatChooserScreen({ variant = "today" }) {
  const other = variant === "other";
  const [pick, setPick] = React.useState(other ? "PNY-IND-Peenya-01" : "NBLR-W-Malleshwaram-01");
  const Row = ({ b, unplanned }) => {
    const on = pick === b.name;
    return (
      <div onClick={() => setPick(b.name)} style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px", cursor: "pointer", background: on ? "#995A000D" : "#fff" }}>
        <H2.Icon name={unplanned ? "Calendar" : "LocationMarker"} size={22} color={on ? "#995A00" : "#8C8C8C"} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: "#333" }}>{b.name}</div>
          <div style={{ fontSize: 12, color: "#8C8C8C" }}>{b.meta}</div>
        </div>
        <H2.Radio checked={on} onChange={() => setPick(b.name)} />
      </div>
    );
  };
  return (
    <Screen2 title="Choose today's beat" back tab="route" noNav>
      <p style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C", margin: 0, padding: "16px 16px 8px" }}>Assigned for today</p>
      <div style={{ background: "#fff" }}>
        {TODAY_BEATS.map((b, i) => <React.Fragment key={b.name}>{i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}<Row b={b} /></React.Fragment>)}
      </div>
      <p style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C", margin: 0, padding: "20px 16px 8px" }}>Your other beats</p>
      <div style={{ background: "#fff" }}>
        {OTHER_BEATS.map((b, i) => <React.Fragment key={b.name}>{i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}<Row b={b} unplanned /></React.Fragment>)}
      </div>
      <div style={{ padding: 16 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: other ? "#FFF6E5" : "#F7F7F7", border: `1px solid ${other ? "#FFD98A" : "#E5E5E5"}`, borderRadius: 10, padding: 12 }}>
          <H2.Icon name="InfoFilled" size={18} color={other ? "#995A00" : "#0081F2"} />
          <span style={{ fontSize: 13, color: other ? "#8A6D3B" : "#666", lineHeight: 1.45 }}>{other
            ? <>You picked a beat assigned to another day. The whole run is recorded as an <strong>unplanned beat</strong> and your manager is notified.</>
            : <>Only beats assigned to you appear here. Picking one from another day records the run as an unplanned beat.</>}</span>
        </div>
      </div>
      <FooterSFA><H2.Button variant="filled" color="primary" label={other ? "Start unplanned beat" : "Start this beat"} onClick={() => {}} style={{ width: "100%" }} /></FooterSFA>
    </Screen2>
  );
}

Object.assign(window, { PunchScreen, PunchBlockedScreen, RouteScreen, BeatChooserScreen });
