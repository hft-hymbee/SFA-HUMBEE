/* Humbee SFA — SP data capture: new outlet onboarding, external outlet insight web view, manufacturer lead capture. */
const HC = window.HumbeeDesignSystem_c38d59;
const ScreenC = window.SFA_Screen, CardC = window.SFA_Card;
const { useState: useStateC } = React;
const secC = { fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C", margin: "0 0 8px" };
const FooterC = ({ children }) => <div style={{ position: "sticky", bottom: 0, background: "#fff", borderTop: "1px solid #E5E5E5", padding: 12 }}>{children}</div>;
const NoteC = ({ children, tone = "info" }) => {
  const T = { info: ["#F7F7F7", "#E5E5E5", "#666", "#0081F2"], warn: ["#FFF6E5", "#FFD98A", "#8A6D3B", "#995A00"] }[tone];
  return <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: T[0], border: `1px solid ${T[1]}`, borderRadius: 10, padding: 12 }}><HC.Icon name="InfoFilled" size={18} color={T[3]} /><span style={{ fontSize: 13, color: T[2], lineHeight: 1.45 }}>{children}</span></div>;
};

/* ---------- S-OUT1 New outlet onboarding ---------- */
function OutletOnboardingScreen({ variant = "form" }) {
  const [cat, setCat] = useStateC("grocery");
  const [gstYes, setGstYes] = useStateC(true);
  const [step, setStep] = useStateC(0);
  if (variant === "submitted") {
    return (
      <ScreenC title="New outlet" back tab="route" noNav>
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
          <CardC style={{ padding: 20, textAlign: "center" }}>
            <div style={{ width: 56, height: 56, borderRadius: "50%", background: "#0080001A", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 12px" }}><HC.Icon name="CheckCircle" size={30} color="#008000" /></div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "#333" }}>Outlet submitted</div>
            <div style={{ fontSize: 14, color: "#666", marginTop: 4 }}>Sai Provision Store · Yeshwanthpur</div>
            <div style={{ marginTop: 12 }}><HC.StatusChip status="pending" label="Pending verification" type="filled" /></div>
          </CardC>
          <CardC style={{ padding: 16 }}>
            <HC.ApprovalTimeline steps={[
              { label: "Captured in field", detail: "by R. Kumar", time: "11:48 AM", state: "done" },
              { label: "Sent to Humbee outlet master", time: "11:48 AM", state: "done" },
              { label: "Verification by Admin", state: "current" },
              { label: "Available for beats & orders", state: "todo" },
            ]} />
          </CardC>
          <NoteC>Counts towards your <strong style={{ color: "#333" }}>New outlets onboarded</strong> target only after verification.</NoteC>
        </div>
        <FooterC><div style={{ display: "flex", gap: 8 }}><HC.Button variant="outlined" color="neutral" label="Back to route" onClick={() => {}} style={{ flex: 1 }} /><HC.Button variant="filled" color="primary" label="Onboard another" onClick={() => {}} style={{ flex: 1 }} /></div></FooterC>
      </ScreenC>
    );
  }
  const CATS = [["grocery", "Grocery / kirana"], ["wholesale", "Wholesale"], ["chemist", "Chemist"], ["gm", "General merchant"], ["horeca", "HoReCa"]];
  return (
    <ScreenC title="Onboard new outlet" back tab="route" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <HC.Stepper steps={[{ label: "Shop" }, { label: "Location" }, { label: "Proof" }]} activeStep={step} size="small" />
        <NoteC>Final field list comes from the Humbee onboarding API — this captures the standard set. Anything extra will be added when the schema is shared.</NoteC>
        <div>
          <p style={secC}>Shop details</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <HC.TextField label="Shop name" placeholder="e.g. Sai Provision Store" value="" onChange={() => {}} required />
            <HC.TextField label="Owner / contact person" placeholder="e.g. Mahesh Shetty" value="" onChange={() => {}} required />
            <HC.TextField label="Mobile number" placeholder="98765 43210" value="" onChange={() => {}} startAdornment={<span style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>+91</span>} required />
            <div>
              <p style={{ ...secC, margin: "0 0 8px" }}>Shop category</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {CATS.map((c) => {
                  const on = cat === c[0];
                  return <button key={c[0]} type="button" onClick={() => setCat(c[0])} style={{ minHeight: 36, padding: "8px 12px", borderRadius: 999, cursor: "pointer", background: on ? "#995A001F" : "#fff", border: `1px solid ${on ? "#995A00" : "#D9D9D9"}`, color: on ? "#995A00" : "#555", fontFamily: "var(--font-family-base)", fontSize: 13, fontWeight: 700 }}>{c[1]}</button>;
                })}
              </div>
            </div>
            <HC.Select label="Association level" fullWidth value="dealer" onChange={() => {}} options={[{ value: "dealer", label: "Dealer (buys from a Distribution Partner)" }, { value: "dp", label: "Distribution Partner" }]} />
            <HC.Select label="Buys from (Distribution Partner)" fullWidth value="anand" onChange={() => {}} options={[{ value: "anand", label: "Anand Distributors · Malleshwaram" }, { value: "metro", label: "Metro Wholesale · Yeshwanthpur" }]} />
          </div>
        </div>
        <div>
          <p style={secC}>Address & location</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <HC.TextField label="Address" placeholder="Shop no, street, landmark" value="" onChange={() => {}} multiline rows={2} />
            <div style={{ display: "flex", gap: 12 }}>
              <HC.TextField label="Pincode" placeholder="560022" value="" onChange={() => {}} style={{ flex: 1 }} />
              <HC.TextField label="City / locality" placeholder="Yeshwanthpur" value="" onChange={() => {}} style={{ flex: 1.4 }} />
            </div>
            <CardC style={{ padding: 12, display: "flex", alignItems: "center", gap: 10, background: "#0080000D", borderColor: "#B7E0B7" }}>
              <HC.Icon name="GpsFixed" size={22} color="#008000" />
              <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontSize: 13, fontWeight: 700, color: "#333" }}>Shop GPS captured</div><div style={{ fontSize: 12, color: "#5B865B" }}>12.9982, 77.5525 · ±8 m accuracy</div></div>
              <HC.Button variant="outlined" color="neutral" size="small" label="Recapture" onClick={() => setStep(1)} />
            </CardC>
          </div>
        </div>
        <div>
          <p style={secC}>Proof & compliance</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <CardC style={{ padding: "8px 16px" }}><HC.ToggleSwitch label="GST registered" checked={gstYes} onChange={(e) => setGstYes(e.target.checked)} /></CardC>
            {gstYes && <HC.TextField label="GSTIN" placeholder="29ABCDE1234F1Z5" value="" onChange={() => {}} helperText="Validated against the GST master on submit" />}
            <div style={{ display: "flex", gap: 12 }}>
              {[["Shop front photo", "Image"], ["Shop board / signage", "Image"]].map((p) => (
                <button key={p[0]} type="button" onClick={() => setStep(2)} style={{ flex: 1, minHeight: 96, border: "1.5px dashed #D9D9D9", borderRadius: 12, background: "#fff", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, padding: 10, fontFamily: "var(--font-family-base)" }}>
                  <HC.Icon name={p[1]} size={24} color="#995A00" />
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#666", textAlign: "center" }}>{p[0]}</span>
                </button>
              ))}
            </div>
            <HC.TextField label="Remarks (optional)" placeholder="Anything the Admin should know" value="" onChange={() => {}} multiline rows={2} />
          </div>
        </div>
        <NoteC tone="warn">Submitting sends the outlet to Admin for verification. It becomes available for beats and orders once verified.</NoteC>
      </div>
      <FooterC>
        <div style={{ display: "flex", gap: 8 }}>
          <HC.Button variant="outlined" color="neutral" label="Save draft" onClick={() => {}} style={{ flex: 1 }} />
          <HC.Button variant="filled" color="primary" label="Submit outlet" onClick={() => {}} style={{ flex: 1.4 }} />
        </div>
      </FooterC>
    </ScreenC>
  );
}

/* ---------- S-OUT2 Outlet insight web view (rendered by external API) ---------- */
function OutletInsightWebviewScreen({ variant = "loaded" }) {
  return (
    <ScreenC title="Krishna Stores · Insights" back tab="route" noNav bodyBg="#fff">
      <div style={{ padding: "10px 16px", background: "#F7F7F7", borderBottom: "1px solid #E5E5E5", display: "flex", alignItems: "center", gap: 8 }}>
        <HC.Icon name="Lock" size={16} color="#008000" />
        <span style={{ fontSize: 12, color: "#8C8C8C", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>insights.humbee.in/outlet/29ABCDE1234F1Z5</span>
        <HC.Icon name="Autorenew" size={16} color="#8C8C8C" />
      </div>
      {variant === "loading" ? (
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <HC.Skeleton height={120} radius={12} />{[0, 1, 2, 3].map((i) => <HC.SkeletonRow key={i} />)}
          <div style={{ textAlign: "center", fontSize: 13, color: "#8C8C8C" }}>Loading outlet insights…</div>
        </div>
      ) : variant === "error" ? (
        <HC.ErrorState title="Insights unavailable" message="The outlet insight service didn't respond. Your visit and order flow are unaffected." onRetry={() => {}} />
      ) : (
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ border: "1px dashed #D9D9D9", borderRadius: 12, padding: 14, background: "#FAFAFA" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <HC.StatusBadge label="External web view" color="#0081F2" variant="soft" size="small" />
              <span style={{ fontSize: 12, color: "#8C8C8C" }}>rendered by Humbee insights API</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {[["Credit outstanding", "₹ 18,200"], ["Avg. order value", "₹ 11,600"], ["Purchase trend", "▲ 12% QoQ"], ["Top SKU", "Atta 10 kg"], ["Returns", "1 in 6 mo"], ["Score", "A–"]].map((s) => (
                <div key={s[0]} style={{ background: "#fff", border: "1px solid #EEE", borderRadius: 10, padding: "10px 12px" }}>
                  <div style={{ fontSize: 11, color: "#8C8C8C", fontWeight: 600 }}>{s[0]}</div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>{s[1]}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 10, height: 88, borderRadius: 10, background: "linear-gradient(180deg,#fff,#F2F2F2)", border: "1px solid #EEE", display: "flex", alignItems: "flex-end", gap: 6, padding: 10 }}>
              {[38, 52, 44, 66, 58, 74, 82].map((h, i) => <div key={i} style={{ flex: 1, height: `${h}%`, borderRadius: 4, background: i === 6 ? "#995A00" : "#995A0059" }} />)}
            </div>
          </div>
          <NoteC>This view is read-only and owned by the insight service. Humbee SFA only passes the outlet identifier.</NoteC>
        </div>
      )}
      <FooterC><HC.Button variant="outlined" color="neutral" label="Back to visit" onClick={() => {}} style={{ width: "100%" }} /></FooterC>
    </ScreenC>
  );
}

/* ---------- S-LEAD1 Manufacturer lead capture (feeds the lead target) ---------- */
function LeadCaptureScreen({ variant = "form" }) {
  const [interest, setInterest] = useStateC("hot");
  if (variant === "list") {
    const LEADS = [
      ["Sai Provision Store", "Aashirvaad · Atta 10kg · hot", "approved", "Qualified"],
      ["Gupta & Sons", "Fortune · Oil 5L · warm", "pending", "In review"],
      ["Balaji Traders", "Tata Salt · cold", "default", "Captured"],
    ];
    return (
      <ScreenC title="My leads" back tab="more" noNav>
        <div style={{ padding: "12px 16px", background: "#fff", borderBottom: "1px solid #E5E5E5", fontSize: 13, color: "#666" }}>MTD: <strong style={{ color: "#333" }}>7 of 10</strong> leads captured · weekly pace 2/wk</div>
        <div style={{ background: "#fff" }}>
          {LEADS.map((l, i) => (
            <React.Fragment key={l[0]}>
              {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
              <HC.ListRow leading={<HC.Icon name="RewardsOutlined" size={22} color="#995A00" />} title={l[0]} subtitle={l[1]} trailing={<HC.StatusChip status={l[2]} label={l[3]} type="outlined" />} showChevron onClick={() => {}} />
            </React.Fragment>
          ))}
        </div>
        <HC.FAB iconName="Add" label="Capture lead" onClick={() => {}} />
      </ScreenC>
    );
  }
  return (
    <ScreenC title="Capture lead" back tab="more" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <HC.Select label="Manufacturer" fullWidth value="itc" onChange={() => {}} options={[{ value: "itc", label: "ITC — Aashirvaad" }, { value: "adani", label: "Adani Wilmar — Fortune" }, { value: "tata", label: "Tata Consumer" }, { value: "hul", label: "HUL" }]} helperText="Manufacturer list comes from the Humbee API" />
        <HC.Select label="Product / brand interest" fullWidth value="atta" onChange={() => {}} options={[{ value: "atta", label: "Atta 10 kg" }, { value: "oil", label: "Oil 5 L" }, { value: "salt", label: "Salt 1 kg" }]} />
        <HC.TextField label="Outlet / prospect name" placeholder="e.g. Sai Provision Store" value="" onChange={() => {}} required />
        <HC.TextField label="Contact person" placeholder="e.g. Mahesh Shetty" value="" onChange={() => {}} />
        <HC.TextField label="Mobile number" placeholder="98765 43210" value="" onChange={() => {}} startAdornment={<span style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>+91</span>} required />
        <div>
          <p style={secC}>Interest level</p>
          <div style={{ display: "flex", gap: 8 }}>
            {[["hot", "Hot", "#CC0000"], ["warm", "Warm", "#995A00"], ["cold", "Cold", "#0081F2"]].map((t) => {
              const on = interest === t[0];
              return <button key={t[0]} type="button" onClick={() => setInterest(t[0])} style={{ flex: 1, minHeight: 44, borderRadius: 10, cursor: "pointer", background: on ? t[2] + "1F" : "#fff", border: `1.5px solid ${on ? t[2] : "#E5E5E5"}`, color: on ? t[2] : "#555", fontFamily: "var(--font-family-base)", fontSize: 14, fontWeight: 700 }}>{t[1]}</button>;
            })}
          </div>
        </div>
        <HC.TextField label="Expected monthly volume" placeholder="e.g. 40 units" value="" onChange={() => {}} />
        <HC.TextField label="Notes" placeholder="What the prospect asked for" value="" onChange={() => {}} multiline rows={2} />
        <NoteC>Each captured lead counts towards your <strong style={{ color: "#333" }}>Manufacturer leads</strong> target (MTD or weekly, as set by your manager).</NoteC>
      </div>
      <FooterC><HC.Button variant="filled" color="primary" label="Save lead" onClick={() => {}} style={{ width: "100%" }} /></FooterC>
    </ScreenC>
  );
}

Object.assign(window, { OutletOnboardingScreen, OutletInsightWebviewScreen, LeadCaptureScreen });
