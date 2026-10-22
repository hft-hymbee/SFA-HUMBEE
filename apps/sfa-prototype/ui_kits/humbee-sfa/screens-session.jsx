/* Humbee SFA — Sales Person screens, part 4: Splash & session (S-A1, S-A4, S-A5, S-A6). */
const HS4 = window.HumbeeDesignSystem_c38d59;
const Card4 = window.SFA_Card;
const HS4State = React.useState;

/* ---------- S-A1 Splash / launch ---------- */
function SplashScreen() {
  return (
    <div style={{ height: "100%", background: "#995A00", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, fontFamily: "var(--font-family-base)" }}>
      <div style={{ background: "#fff", borderRadius: 24, padding: "28px 32px", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <img src="../../assets/logo-tagline.svg" alt="Humbee" style={{ width: 236, display: "block" }} />
      </div>
      <div style={{ fontSize: 14, color: "#FFE9C7", letterSpacing: ".5px", marginTop: 4 }}>Sales Force Automation</div>
      <span style={{ width: 26, height: 26, marginTop: 8, display: "inline-block", border: "3px solid rgba(255,255,255,0.4)", borderTopColor: "#fff", borderRadius: "50%", animation: "hb-spin 0.8s linear infinite" }}>
        <style>{"@keyframes hb-spin{to{transform:rotate(360deg)}}"}</style>
      </span>
      <div style={{ position: "absolute", bottom: 28, fontSize: 12, color: "#FFE9C7", opacity: 0.8 }}>v1.0 · Checking session…</div>
    </div>
  );
}

/* ---------- S-A4 Account deactivated ---------- */
function AccountDeactivatedScreen() {
  return (
    <div style={{ height: "100%", background: "#fff", display: "flex", flexDirection: "column", fontFamily: "var(--font-family-base)" }}>
      <HS4.TopAppBar title="Sign in" onBack={() => {}} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: 24, gap: 10 }}>
        <div style={{ width: 80, height: 80, borderRadius: "50%", background: "#CC00000D", display: "flex", alignItems: "center", justifyContent: "center" }}><HS4.Icon name="Lock" size={40} color="#CC0000" /></div>
        <h2 style={{ margin: "6px 0 0", fontSize: 20, fontWeight: 700, color: "#333" }}>Account deactivated</h2>
        <p style={{ margin: 0, fontSize: 15, color: "#666", maxWidth: 280, lineHeight: 1.5 }}>Your login has been disabled by your administrator. Contact your reporting manager to restore access.</p>
      </div>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
        <HS4.Button variant="filled" color="primary" label="Call my manager" leftIcon={<HS4.Icon name="Call" size={20} color="#fff" />} onClick={() => {}} style={{ width: "100%" }} />
        <HS4.Button variant="text" color="neutral" label="Back to login" onClick={() => {}} style={{ width: "100%" }} />
      </div>
    </div>
  );
}

/* ---------- S-A5 Session expired / re-auth (modal over dimmed app) ---------- */
function ReauthScreen() {
  const [otp, setOtp] = HS4State("04");
  const [secs, setSecs] = HS4State(21);
  React.useEffect(() => { if (secs <= 0) return; const t = setTimeout(() => setSecs((s) => s - 1), 1000); return () => clearTimeout(t); }, [secs]);
  return (
    <div style={{ height: "100%", background: "#F5F5F5", position: "relative", fontFamily: "var(--font-family-base)" }}>
      <div style={{ opacity: 0.4, pointerEvents: "none" }}>
        <HS4.TopAppBar title="Today" />
        <div style={{ padding: 16 }}><Card4 style={{ height: 120 }} /></div>
      </div>
      <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16, zIndex: 50 }}>
        <div style={{ background: "#fff", borderRadius: 16, width: "100%", maxWidth: 330, boxShadow: "0px 11px 15px -7px rgba(0,0,0,0.2),0px 24px 38px 3px rgba(0,0,0,0.14)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: 16, borderBottom: "1px solid #D9D9D9" }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: "#333" }}>Session expired</span>
            <button type="button" style={{ background: "none", border: "none", cursor: "pointer", display: "inline-flex", padding: 0 }}><HS4.Icon name="Close" size={20} color="#333" /></button>
          </div>
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
            <p style={{ margin: 0, fontSize: 15, color: "#666", lineHeight: 1.45 }}>Your session expired. Verify the OTP sent to <strong style={{ color: "#333" }}>+91 ·····3210</strong> to continue.</p>
            <HS4.OTPInput length={6} value={otp} onChange={setOtp} />
            <div style={{ fontSize: 14, color: "#666" }}>
              {secs > 0 ? <span>Resend code in <strong style={{ color: "#333" }}>0:{String(secs).padStart(2, "0")}</strong></span>
                : <a href="#" style={{ color: "#995A00", fontWeight: 700 }}>Resend code</a>}
            </div>
            <HS4.Button variant="filled" color="primary" label="Verify & continue" onClick={() => {}} style={{ width: "100%" }} disabled={otp.replace(/\s/g, "").length < 6} />
            <p style={{ margin: 0, fontSize: 12, color: "#8C8C8C", textAlign: "center" }}>You'll return to where you left off.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------- S-A6 Logout confirm (action sheet) ---------- */
function LogoutConfirmScreen() {
  return (
    <div style={{ height: "100%", background: "#F5F5F5", position: "relative", fontFamily: "var(--font-family-base)" }}>
      <div style={{ opacity: 0.5, pointerEvents: "none" }}>
        <HS4.TopAppBar title="More" onBell={() => {}} />
        <div style={{ background: "#fff" }}>
          <HS4.ListRow leading={<HS4.Icon name="ProfileOutlined" size={22} color="#666" />} title="My profile" showChevron />
          <div style={{ borderTop: "1px solid #F0F0F0" }} />
          <HS4.ListRow leading={<HS4.Icon name="LogoutOutlined" size={22} color="#CC0000" />} title="Log out" />
        </div>
      </div>
      <HS4.BottomSheet open title="Log out?" onClose={() => {}}>
        <p style={{ fontSize: 14, color: "#666", margin: "0 0 16px" }}>You'll need to sign in again to punch in and run your route.</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <HS4.Button variant="filled" color="error" label="Log out" onClick={() => {}} style={{ width: "100%" }} />
          <HS4.Button variant="outlined" color="neutral" label="Cancel" onClick={() => {}} style={{ width: "100%" }} />
        </div>
      </HS4.BottomSheet>
    </div>
  );
}

Object.assign(window, { SplashScreen, AccountDeactivatedScreen, ReauthScreen, LogoutConfirmScreen });
