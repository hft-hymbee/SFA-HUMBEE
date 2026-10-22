/* Humbee SFA — Sales Person screens, part 5: Beats (plan-time) + Plan route. */
const HB = window.HumbeeDesignSystem_c38d59;
const ScreenB = window.SFA_Screen, CardB = window.SFA_Card;
const { useState: useStateB } = React;
const secB = { fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C", margin: "0 0 8px" };
const FooterB = ({ children }) => <div style={{ position: "sticky", bottom: 0, background: "#fff", borderTop: "1px solid #E5E5E5", padding: 12 }}>{children}</div>;

/* ---------- S-BEAT1 My beats ---------- */
const BEATS = [
  ["North BLR–West", "24 outlets · Bengaluru Urban · Grocery, Wholesale", "approved", "Approved"],
  ["Peenya Industrial", "18 outlets · edits pending approval", "pending", "Edit pending"],
  ["Yeshwanthpur Core", "12 outlets · Draft", "default", "Draft"],
];
function MyBeatsScreen({ variant = "list" }) {
  const [tab, setTab] = useStateB("all");
  if (variant === "empty") return <ScreenB title="My beats" bell tab="beats"><HB.EmptyState icon="Calendar" title="No beats yet" message="Create a beat plan from your assigned geography to start covering outlets." actionLabel="Create beat" onAction={() => {}} /></ScreenB>;
  if (variant === "loading") return <ScreenB title="My beats" bell tab="beats"><div>{[0,1,2].map(i => <HB.SkeletonRow key={i} />)}</div></ScreenB>;
  return (
    <ScreenB title="My beats" bell tab="beats">
      <div style={{ padding: 12, background: "#fff", borderBottom: "1px solid #E5E5E5" }}>
        <HB.Tabs tabs={[{label:"All",value:"all"},{label:"Approved",value:"ap"},{label:"Pending",value:"pn"},{label:"Draft",value:"dr"}]} value={tab} onChange={setTab} type="boxed" size="small" />
      </div>
      <div style={{ background: "#fff" }}>
        {BEATS.map((b, i) => (
          <React.Fragment key={b[0]}>
            {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
            <HB.ListRow leading={<HB.Icon name="Calendar" size={22} color="#995A00" />} title={b[0]} subtitle={b[1]} trailing={<HB.StatusChip status={b[2]} label={b[3]} type="outlined" />} showChevron onClick={() => {}} />
          </React.Fragment>
        ))}
      </div>
      <HB.FAB iconName="Add" label="Create beat" onClick={() => {}} />
    </ScreenB>
  );
}

/* Geography parameter set: Zone cluster · State cluster · District cluster · Shop category (all multi-select).
   Rendered by the shared GeoScopePicker so beat creation, Admin assignment and beat edit stay identical. */
const LOCATIONS = [["malle", "Malleshwaram", 18], ["raja", "Rajajinagar", 16], ["yesh", "Yeshwanthpur", 14], ["peenya", "Peenya Phase 1–2", 22]];
const SHOP_CATS = [{ value: "all", label: "All categories" }, { value: "grocery", label: "Grocery / kirana" }, { value: "wholesale", label: "Wholesale" }, { value: "chemist", label: "Chemist" }, { value: "gm", label: "General merchant" }];

/* ---------- S-BEAT2 Create beat — geography scope (Zone / State / District clusters + Shop category) ---------- */
function CreateBeatScopeScreen() {
  const [scope, setScope] = useStateB({ districts: ["blru"], outlets: 0 });
  const Geo = window.GeoScopePicker;
  return (
    <ScreenB title="Create beat" back tab="beats" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <HB.Stepper steps={[{label:"Scope"},{label:"Outlets"},{label:"Review"}]} activeStep={0} size="small" />
        <p style={{ fontSize: 14, color: "#666", margin: 0 }}>Pick the clusters this beat draws outlets from. Combine as many as you need — only values inside the geography Admin assigned to you are listed.</p>
        {Geo && <Geo assigned={{ zones: ["south"], states: ["ka"], districts: ["blru", "blrr", "tum"] }} initial={{ zones: ["south"], states: ["ka"], districts: ["blru"], cats: ["grocery", "wholesale"] }} onScope={setScope} />}
      </div>
      <FooterB><HB.Button variant="filled" color="primary" label={scope.outlets ? `Choose outlets · ${scope.outlets} available` : "Choose outlets"} onClick={() => {}} style={{ width: "100%" }} disabled={!scope.districts.length} /></FooterB>
    </ScreenB>
  );
}

/* ---------- S-BEAT3 Outlet picker / cluster ---------- */
const OUTLET_POOL = [
  ["Metro Wholesale", "Malleshwaram", "Wholesale · 0.8 km", true],
  ["Anand Distributors", "Malleshwaram", "Wholesale · 1.1 km", true],
  ["Sri Balaji Agency", "Rajajinagar", "Grocery · 1.3 km", false],
  ["Krishna Stores", "Rajajinagar", "Grocery · 1.4 km", true],
  ["Gupta & Sons", "Rajajinagar", "General merchant · 2.6 km", false],
];
function OutletPickerScreen() {
  const sel = OUTLET_POOL.filter(o => o[3]).length;
  const groups = ["Malleshwaram", "Rajajinagar"];
  return (
    <ScreenB title="Choose outlets" back tab="beats" noNav>
      <div style={{ padding: 12, background: "#fff", borderBottom: "1px solid #E5E5E5" }}>
        <HB.TextField placeholder="Search outlets" value="" onChange={() => {}} startAdornment={<HB.Icon name="SearchOutlined" size={20} color="#8C8C8C" />} />
      </div>
      {groups.map((g) => (
        <React.Fragment key={g}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 16px", background: "#F5F5F5", borderTop: "1px solid #E5E5E5", borderBottom: "1px solid #E5E5E5" }}>
            <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C" }}>{g}</span>
            <span style={{ fontSize: 12, color: "#8C8C8C" }}>{OUTLET_POOL.filter(o => o[1] === g).length} outlets</span>
          </div>
          <div style={{ background: "#fff" }}>
            {OUTLET_POOL.filter(o => o[1] === g).map((o, i) => (
              <React.Fragment key={o[0]}>
                {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                <HB.ListRow leading={<HB.Checkbox checked={o[3]} onChange={() => {}} />} title={o[0]} subtitle={o[2]} onClick={() => {}} />
              </React.Fragment>
            ))}
          </div>
        </React.Fragment>
      ))}
      <FooterB>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#333" }}>{sel} selected</span>
          <HB.Button variant="filled" color="primary" label="Review beat" onClick={() => {}} style={{ flex: 1 }} />
        </div>
      </FooterB>
    </ScreenB>
  );
}

/* Visit-frequency chooser (SFA PJP model): Daily / Weekly / Fortnightly / Monthly,
   with conditional weekday selection + week-cycle for fortnightly/monthly. */
function FrequencyChooser() {
  const [freq, setFreq] = useStateB("weekly");
  const [days, setDays] = useStateB([1, 4]); // Mon, Thu
  const [weeks, setWeeks] = useStateB([1, 3]); // W1, W3
  const FREQS = [["daily", "Daily"], ["weekly", "Weekly"], ["fortnightly", "Fortnightly"], ["monthly", "Monthly"]];
  const DOW = ["S", "M", "T", "W", "T", "F", "S"];
  const toggle = (arr, set, v) => set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);
  const perMonth = { daily: "~26 visits/mo", weekly: `${days.length}×/wk · ~${days.length * 4}/mo`, fortnightly: `${days.length * weeks.length}/mo`, monthly: `${days.length}/mo` }[freq];
  return (
    <div>
      <p style={secB}>Visit frequency</p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}>
        {FREQS.map(([v, l]) => {
          const on = freq === v;
          return (
            <button key={v} type="button" onClick={() => setFreq(v)}
              style={{ padding: "12px 14px", borderRadius: 10, cursor: "pointer", textAlign: "left", background: on ? "#995A001F" : "#fff", border: `1.5px solid ${on ? "#995A00" : "#E5E5E5"}`, fontFamily: "var(--font-family-base)", fontSize: 15, fontWeight: 700, color: on ? "#995A00" : "#333" }}>{l}</button>
          );
        })}
      </div>
      {freq !== "daily" && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#666", marginBottom: 8 }}>{freq === "monthly" ? "Visit day of week" : "Visit days"}</div>
          <div style={{ display: "flex", gap: 6 }}>
            {DOW.map((d, i) => {
              const on = days.includes(i);
              return (
                <button key={i} type="button" onClick={() => toggle(days, setDays, i)}
                  style={{ flex: 1, height: 40, borderRadius: 8, cursor: "pointer", background: on ? "#995A00" : "#fff", border: `1px solid ${on ? "#995A00" : "#D9D9D9"}`, color: on ? "#fff" : "#666", fontWeight: 700, fontSize: 14, fontFamily: "var(--font-family-base)" }}>{d}</button>
              );
            })}
          </div>
        </div>
      )}
      {(freq === "fortnightly" || freq === "monthly") && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#666", marginBottom: 8 }}>{freq === "monthly" ? "Which week" : "Week cycle"}</div>
          <div style={{ display: "flex", gap: 6 }}>
            {[1, 2, 3, 4].map((w) => {
              const on = weeks.includes(w);
              return (
                <button key={w} type="button" onClick={() => toggle(weeks, setWeeks, w)}
                  style={{ flex: 1, height: 40, borderRadius: 8, cursor: "pointer", background: on ? "#995A001F" : "#fff", border: `1px solid ${on ? "#995A00" : "#D9D9D9"}`, color: on ? "#995A00" : "#666", fontWeight: 700, fontSize: 13, fontFamily: "var(--font-family-base)" }}>W{w}</button>
              );
            })}
          </div>
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#F7F7F7", borderRadius: 10, padding: 12 }}>
        <HB.Icon name="Autorenew" size={18} color="#995A00" />
        <span style={{ fontSize: 13, color: "#666" }}>Coverage: <strong style={{ color: "#333" }}>{perMonth}</strong></span>
      </div>
    </div>
  );
}

/* ---------- S-BEAT4 Name & review beat ---------- */
function NameBeatScreen() {
  return (
    <ScreenB title="Review beat" back tab="beats" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <HB.Stepper steps={[{label:"Scope"},{label:"Outlets"},{label:"Review"}]} activeStep={2} size="small" />
        <HB.TextField label="Beat name" value="NBLR-W-Malleshwaram-01" onChange={() => {}} helperText="Convention: AREA-DIRECTION-LOCALITY-NN" />
        <FrequencyChooser />
        <div>
          <p style={secB}>3 outlets in this beat</p>
          <CardB style={{ padding: 0, overflow: "hidden" }}>
            {OUTLET_POOL.filter(o => o[3]).map((o, i) => (
              <React.Fragment key={o[0]}>
                {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                <HB.ListRow leading={<span style={{ width: 26, height: 26, borderRadius: "50%", background: "#995A001F", color: "#995A00", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 12 }}>{i+1}</span>} title={o[0]} subtitle={`${o[1]} · ${o[2]}`} />
              </React.Fragment>
            ))}
          </CardB>
        </div>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 13, color: "#666" }}>
          <HB.Icon name="InfoFilled" size={18} color="#0081F2" /><span>Submitting sends this beat to your manager for approval.</span>
        </div>
      </div>
      <FooterB><HB.Button variant="filled" color="primary" label="Submit for approval" onClick={() => {}} style={{ width: "100%" }} /></FooterB>
    </ScreenB>
  );
}

/* ---------- S-BEAT5 Beat detail ---------- */
function BeatDetailScreen({ variant = "active" }) {
  const inactive = variant === "inactive";
  return (
    <ScreenB title="North BLR–West" back tab="beats" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <CardB style={{ padding: 16, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
          <div><div style={{ fontSize: 16, fontWeight: 700, color: "#333" }}>NBLR-W-Malleshwaram-01</div><div style={{ fontSize: 13, color: "#666" }}>24 outlets · Weekly (Mon, Thu) · created 12 Jul</div></div>
          <HB.StatusChip status={inactive ? "cancelled" : "approved"} label={inactive ? "Inactive" : "Approved"} type="filled" />
        </CardB>
        <div>
          <p style={secB}>Geography scope</p>
          <CardB style={{ padding: 0, overflow: "hidden" }}>
            {[["Zone cluster", "South Zone"], ["State cluster", "Karnataka"], ["District cluster", "Bengaluru Urban"], ["Shop category", "Grocery / kirana, Wholesale"]].map((r, i) => (
              <React.Fragment key={r[0]}>
                {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "11px 16px", fontSize: 14 }}>
                  <span style={{ color: "#8C8C8C", flexShrink: 0 }}>{r[0]}</span>
                  <span style={{ color: "#333", fontWeight: 600, textAlign: "right" }}>{r[1]}</span>
                </div>
              </React.Fragment>
            ))}
          </CardB>
        </div>
        {inactive && (
          <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: "#FFF6E5", border: "1px solid #FFD98A", borderRadius: 10, padding: 12 }}>
            <HB.Icon name="InfoFilled" size={18} color="#995A00" /><span style={{ fontSize: 13, color: "#8A6D3B", lineHeight: 1.45 }}>Deactivated by Admin on 14 Jul. It can't be used for new routes; all past visits and orders stay on record. Only Admin can reactivate it.</span>
          </div>
        )}
        <div>
          <p style={secB}>Approval</p>
          <CardB style={{ padding: 16 }}>
            <HB.ApprovalTimeline steps={[
              { label: "Submitted", time: "12 Jul, 4:10 PM", state: "done" },
              { label: "Approved", detail: "by A. Sharma (Manager)", time: "12 Jul, 6:02 PM", state: "done" },
              { label: "Ready to plan route", state: "current" },
            ]} />
          </CardB>
        </div>
        <div>
          <p style={secB}>Outlets</p>
          <CardB style={{ padding: 0, overflow: "hidden" }}>
            {OUTLET_POOL.slice(0,4).map((o, i) => (
              <React.Fragment key={o[0]}>
                {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                <HB.ListRow leading={<HB.Icon name="LocationPin" size={20} color="#8C8C8C" />} title={o[0]} subtitle={`${o[1]} · ${o[2]}`} />
              </React.Fragment>
            ))}
          </CardB>
        </div>
      </div>
      <FooterB>
        {inactive
          ? <HB.Button variant="filled" color="primary" label="Beat inactive — contact Admin" onClick={() => {}} style={{ width: "100%" }} disabled />
          : <div style={{ display: "flex", gap: 8 }}>
              <HB.Button variant="outlined" color="neutral" label="Edit beat" leftIcon={<HB.Icon name="Edit" size={18} color="#333" />} onClick={() => {}} style={{ flex: 1 }} />
              <HB.Button variant="filled" color="primary" label="Plan route" onClick={() => {}} style={{ flex: 1.2 }} />
            </div>}
      </FooterB>
    </ScreenB>
  );
}

/* ---------- S-BEAT7 Edit beat (Sales Person) — changes go to manager/Admin for approval ---------- */
function EditBeatScreen({ variant = "edit" }) {
  const [scope, setScope] = useStateB({ outlets: 148 });
  const Geo = window.GeoScopePicker;
  if (variant === "pending") {
    return (
      <ScreenB title="NBLR-W-Malleshwaram-01" back tab="beats" noNav>
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: "#FFF6E5", border: "1px solid #FFD98A", borderRadius: 10, padding: 12 }}>
            <HB.Icon name="Lock" size={18} color="#995A00" /><span style={{ fontSize: 13, color: "#8A6D3B", lineHeight: 1.45 }}>Your edit is with <strong style={{ color: "#663C00" }}>P. Nair (Manager)</strong>. The beat keeps running on its approved version until the change is approved.</span>
          </div>
          <div>
            <p style={secB}>Requested changes</p>
            <CardB style={{ padding: 0, overflow: "hidden" }}>
              {[["Outlets", "24 → 27"], ["District cluster", "Bengaluru Urban → + Tumakuru"], ["Visit frequency", "Weekly (Mon, Thu) → Weekly (Mon, Wed, Fri)"]].map((r, i) => (
                <React.Fragment key={r[0]}>
                  {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                  <div style={{ padding: "11px 16px" }}>
                    <div style={{ fontSize: 12, color: "#8C8C8C", fontWeight: 600 }}>{r[0]}</div>
                    <div style={{ fontSize: 14, color: "#333", fontWeight: 600 }}>{r[1]}</div>
                  </div>
                </React.Fragment>
              ))}
            </CardB>
          </div>
          <CardB style={{ padding: 16 }}>
            <HB.ApprovalTimeline steps={[
              { label: "Edit submitted", detail: "by you", time: "Today, 11:20 AM", state: "done" },
              { label: "Pending manager approval", detail: "P. Nair", state: "current" },
              { label: "Applied to beat", state: "todo" },
            ]} />
          </CardB>
        </div>
        <FooterB><HB.Button variant="outlined" color="error" label="Withdraw edit request" onClick={() => {}} style={{ width: "100%" }} /></FooterB>
      </ScreenB>
    );
  }
  return (
    <ScreenB title="Edit beat" back tab="beats" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <HB.TextField label="Beat name" value="NBLR-W-Malleshwaram-01" onChange={() => {}} helperText="Convention: AREA-DIRECTION-LOCALITY-NN" />
        <div>
          <p style={secB}>Geography scope</p>
          {Geo && <Geo assigned={{ zones: ["south"], states: ["ka"], districts: ["blru", "blrr", "tum"] }} initial={{ zones: ["south"], states: ["ka"], districts: ["blru"], cats: ["grocery", "wholesale"] }} onScope={setScope} />}
        </div>
        <FrequencyChooser />
        <div>
          <p style={secB}>Outlets in this beat · 24</p>
          <CardB style={{ padding: 0, overflow: "hidden" }}>
            {OUTLET_POOL.map((o, i) => (
              <React.Fragment key={o[0]}>
                {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                <HB.ListRow leading={<HB.Checkbox checked={o[3]} onChange={() => {}} />} title={o[0]} subtitle={`${o[1]} · ${o[2]}`} />
              </React.Fragment>
            ))}
          </CardB>
          <HB.Button variant="outlined" color="primary" size="small" label="Add outlets from scope" leftIcon={<HB.Icon name="Add" size={18} color="#995A00" />} onClick={() => {}} style={{ width: "100%", marginTop: 10 }} />
        </div>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: "#F7F7F7", border: "1px solid #E5E5E5", borderRadius: 10, padding: 12 }}>
          <HB.Icon name="InfoFilled" size={18} color="#0081F2" /><span style={{ fontSize: 13, color: "#666", lineHeight: 1.45 }}>You can edit your own beats. Changes need <strong style={{ color: "#333" }}>manager or Admin approval</strong> before they apply — the current version stays live until then.</span>
        </div>
      </div>
      <FooterB>
        <div style={{ display: "flex", gap: 8 }}>
          <HB.Button variant="outlined" color="neutral" label="Discard" onClick={() => {}} style={{ flex: 1 }} />
          <HB.Button variant="filled" color="primary" label="Send for approval" onClick={() => {}} style={{ flex: 1.6 }} />
        </div>
      </FooterB>
    </ScreenB>
  );
}

/* ---------- S-ROUTE2 Plan route ---------- */
function PlanRouteScreen({ variant = "default" }) {
  if (variant === "nobeats") {
    return <ScreenB title="Plan route" back tab="route" noNav><HB.EmptyState icon="Calendar" title="No approved beats" message="You need an approved beat before you can plan a route. Create one and wait for manager approval." actionLabel="Go to beats" onAction={() => {}} /></ScreenB>;
  }
  return (
    <ScreenB title="Plan route" back tab="route" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <HB.DateField label="Route date" value="Wed, 16 Jul" onClick={() => {}} />
        <HB.Select label="From approved beat" fullWidth value="nblr" onChange={() => {}} options={[{value:"nblr",label:"North BLR–West (24)"},{value:"peenya",label:"Peenya Industrial (18)"}]} />
        <div>
          <p style={secB}>Sequence outlets · drag to reorder</p>
          <CardB style={{ padding: 0, overflow: "hidden" }}>
            {["Metro Wholesale","Anand Distributors","Sri Balaji Agency","Krishna Stores"].map((o, i) => (
              <React.Fragment key={o}>
                {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                <HB.ListRow leading={<span style={{ width: 26, height: 26, borderRadius: "50%", background: "#995A001F", color: "#995A00", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 12 }}>{i+1}</span>} title={o} subtitle={`${(i*0.6+0.8).toFixed(1)} km`} trailing={<HB.Icon name="Sort" size={18} color="#8C8C8C" />} />
              </React.Fragment>
            ))}
          </CardB>
        </div>
      </div>
      <FooterB><HB.Button variant="filled" color="primary" label="Save route for 16 Jul" onClick={() => {}} style={{ width: "100%" }} /></FooterB>
    </ScreenB>
  );
}

Object.assign(window, { MyBeatsScreen, CreateBeatScopeScreen, OutletPickerScreen, NameBeatScreen, BeatDetailScreen, EditBeatScreen, PlanRouteScreen });
