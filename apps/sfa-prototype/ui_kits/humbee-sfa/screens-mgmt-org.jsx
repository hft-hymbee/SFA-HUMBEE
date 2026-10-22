/* Humbee SFA — Manager & Admin screens, part B: Org & workforce. */
const HM2 = window.HumbeeDesignSystem_c38d59;
const MScreen2 = window.MScreen, CardMg2 = window.CardMg, secMg2 = window.secMg, FooterMg2 = window.FooterMg;
const { useState: useStateOrg } = React;

const EMPLOYEES = [
  ["R. Kumar", "Sales Person", "North BLR–West", "active", "Active", "RK"],
  ["S. Iyer", "Sales Person", "Peenya", "active", "Active", "SI"],
  ["M. Das", "Sales Person", "Yeshwanthpur", "active", "Active", "MD"],
  ["A. Rao", "Sales Person", "Malleshwaram", "cancelled", "Inactive", "AR"],
  ["P. Nair", "Manager", "North Bengaluru", "active", "Active", "PN"],
];

/* ---------- S-ORG1 Employee list ---------- */
function EmployeeListScreen({ role = "adm", variant = "default" }) {
  const [f, setF] = useStateOrg("all");
  const tab = role === "adm" ? "org" : "team";
  const title = role === "adm" ? "Employees" : "My team";
  if (variant === "empty") return <MScreen2 role={role} title={title} bell tab={tab}><HM2.EmptyState icon="PersonRounded" title="No employees found" message="Adjust filters, or add an employee to get started." actionLabel={role === "adm" ? "Add employee" : undefined} onAction={() => {}} /></MScreen2>;
  if (variant === "loading") return <MScreen2 role={role} title={title} bell tab={tab}><div>{[0,1,2,3,4].map(i => <HM2.SkeletonRow key={i} />)}</div></MScreen2>;
  const FILTERS = [["all", "All"], ["sp", "Sales"], ["mgr", "Managers"], ["inactive", "Inactive"]];
  return (
    <MScreen2 role={role} title={title} bell tab={tab} offline={variant === "offline"}>
      <div style={{ padding: 12, background: "#fff", borderBottom: "1px solid #E5E5E5", display: "flex", flexDirection: "column", gap: 10 }}>
        <HM2.TextField placeholder="Search by name or geography" value="" onChange={() => {}} startAdornment={<HM2.Icon name="SearchOutlined" size={20} color="#8C8C8C" />} />
        <div style={{ display: "flex", gap: 8, overflowX: "auto" }}>
          {FILTERS.map((x) => { const on = f === x[0]; return <span key={x[0]} onClick={() => setF(x[0])} style={{ flexShrink: 0, padding: "6px 14px", borderRadius: 999, fontSize: 13, fontWeight: 600, cursor: "pointer", border: `1px solid ${on ? "#995A00" : "#D9D9D9"}`, color: on ? "#995A00" : "#666", background: on ? "#995A001F" : "#fff" }}>{x[1]}</span>; })}
        </div>
      </div>
      <div style={{ padding: "10px 16px", fontSize: 12, color: "#8C8C8C", background: "#fff" }}>{role === "adm" ? "142 employees org-wide" : "8 in your tree"}</div>
      <div style={{ background: "#fff" }}>
        {EMPLOYEES.map((e, i) => (
          <React.Fragment key={e[0]}>
            {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
            <HM2.ListRow leading={<span style={{ width: 40, height: 40, borderRadius: "50%", background: e[3] === "active" ? "#995A00" : "#BDBDBD", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 14 }}>{e[5]}</span>}
              title={e[0]} subtitle={`${e[1]} · ${e[2]}`} trailing={<HM2.StatusChip status={e[3] === "active" ? "verified" : "cancelled"} label={e[4]} type="outlined" />} showChevron onClick={() => {}} />
          </React.Fragment>
        ))}
      </div>
    </MScreen2>
  );
}

/* ---------- S-ORG2 Employee detail ---------- */
function EmployeeDetailScreen({ role = "adm" }) {
  const canEdit = role === "adm";
  const tab = role === "adm" ? "org" : "team";
  const [period, setPeriod] = useStateOrg("today");
  const TODAY = [["On duty", "Yes · since 09:12 AM", "#008000"], ["Route progress", "3 / 6 visited"], ["Total visits", "4"], ["Productive visits", "3"], ["Orders", "3"], ["Order value", "₹ 34,800"]];
  const MTD = [["Present days", "18 / 19", "#008000"], ["Route coverage", "82%"], ["Total visits", "96"], ["Productive visits", "64"], ["Orders", "42"], ["Order value", "₹ 3.4L"], ["Official work", "6h 20m"], ["Target achieved", "68%"]];
  const stats = period === "today" ? TODAY : MTD;
  return (
    <MScreen2 role={role} title="R. Kumar" back tab={tab} noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <CardMg2 style={{ padding: 16, display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ width: 56, height: 56, borderRadius: "50%", background: "#995A00", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 20 }}>RK</span>
          <div style={{ flex: 1 }}><div style={{ fontSize: 18, fontWeight: 700, color: "#333" }}>Rahul Kumar</div><div style={{ fontSize: 13, color: "#666" }}>Sales Person · HB-SP-2048</div></div>
          <HM2.StatusChip status="verified" label="Active" type="outlined" />
        </CardMg2>
        <div>
          <p style={secMg2}>Details</p>
          <CardMg2 style={{ padding: 0, overflow: "hidden" }}>
            {[["Role", "Sales Person"], ["Reports to", "P. Nair (Manager)"], ["Zone cluster", "South Zone"], ["State cluster", "Karnataka"], ["District cluster", "Bengaluru Urban, Bengaluru Rural", canEdit], ["Shop category", "Grocery / kirana, Wholesale"], ["Beats", "2 active", canEdit], ["Phone (login)", "+91 ·····3210"], ["Login", "Active"]].map((r, i) => (
              <React.Fragment key={r[0]}>
                {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                <div onClick={() => {}} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "12px 16px", fontSize: 13, lineHeight: "20px", cursor: r[2] ? "pointer" : "default" }}>
                  <span style={{ color: "#8C8C8C", flexShrink: 0 }}>{r[0]}</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 4, minWidth: 0, textAlign: "right" }}>
                    <span style={{ color: r[2] ? "#995A00" : "#333", fontWeight: 600 }}>{r[1]}</span>
                    {r[2] && <HM2.Icon name="ChevronRight" size={18} color="#995A00" />}
                  </span>
                </div>
              </React.Fragment>
            ))}
          </CardMg2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {[["Coverage", "68%"], ["MTD sales", "₹ 3.4L"]].map((s) => (
            <CardMg2 key={s[0]} style={{ padding: 14 }}><div style={{ fontSize: 12, color: "#666" }}>{s[0]}</div><div style={{ fontSize: 22, fontWeight: 700, color: "#995A00" }}>{s[1]}</div></CardMg2>
          ))}
        </div>
        <div onClick={() => {}} style={{ display: "flex", alignItems: "center", gap: 12, background: "linear-gradient(135deg,#663C00,#995A00)", borderRadius: 12, padding: 14, cursor: "pointer", color: "#fff" }}>
          <div style={{ width: 38, height: 38, borderRadius: 10, background: "#ffffff26", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><HM2.Icon name="Schedule" size={20} color="#fff" /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 800 }}>Day timeline</div>
            <div style={{ fontSize: 12, color: "#F2E2CB" }}>Today, yesterday or any date · activity + day KPIs</div>
          </div>
          <HM2.Icon name="KeyboardArrowRight" size={22} color="#fff" />
        </div>
        {/* Compact operational snapshot — Today / MTD */}
        <div>
          <p style={secMg2}>Activity snapshot</p>
          <div style={{ display: "flex", gap: 6, background: "#F0F0F0", borderRadius: 10, padding: 4, marginBottom: 10 }}>
            {[["today", "Today"], ["mtd", "MTD"]].map((p) => {
              const on = period === p[0];
              return <button key={p[0]} type="button" onClick={() => setPeriod(p[0])} style={{ flex: 1, minHeight: 44, border: "none", borderRadius: 8, cursor: "pointer", background: on ? "#fff" : "transparent", color: on ? "#995A00" : "#666", fontFamily: "var(--font-family-base)", fontSize: 14, fontWeight: 700, boxShadow: on ? "0 1px 3px rgba(0,0,0,0.12)" : "none" }}>{p[1]}</button>;
            })}
          </div>
          <CardMg2 style={{ padding: 0, overflow: "hidden" }}>
            {stats.map((s, i) => (
              <React.Fragment key={s[0]}>
                {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "11px 16px", fontSize: 14 }}>
                  <span style={{ color: "#8C8C8C", minWidth: 0 }}>{s[0]}</span>
                  <span style={{ color: s[2] || "#333", fontWeight: 700, textAlign: "right", flexShrink: 0 }}>{s[1]}</span>
                </div>
              </React.Fragment>
            ))}
          </CardMg2>
          <p style={{ margin: "8px 0 0", fontSize: 12, color: "#8C8C8C", lineHeight: 1.45 }}>{canEdit ? "Organization-wide view." : "Read-only · people in your reporting tree."} Attendance timings are informational. Targets are optional.</p>
        </div>
      </div>
      {canEdit ? (
        <FooterMg2>
          <div style={{ display: "flex", gap: 8 }}><HM2.Button variant="outlined" color="neutral" label="Assign geography" onClick={() => {}} style={{ flex: 1 }} /><HM2.Button variant="filled" color="primary" label="Edit employee" onClick={() => {}} style={{ flex: 1 }} /></div>
        </FooterMg2>
      ) : null}
    </MScreen2>
  );
}

/* ---------- S-ORG3 Add / Edit employee (Admin) ---------- */
function AddEmployeeScreen() {
  const [role, setRole] = useStateOrg("sp");
  const [active, setActive] = useStateOrg(true);
  return (
    <MScreen2 role="adm" title="Add employee" back tab="org" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <HM2.TextField label="Full name" placeholder="e.g. Rahul Kumar" value="" onChange={() => {}} />
        <HM2.TextField label="Employee ID" placeholder="e.g. HB-SP-2049" value="" onChange={() => {}} />
        <HM2.TextField label="Mobile number" placeholder="98765 43210" value="" onChange={() => {}} startAdornment={<span style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>+91</span>} helperText="This number is the login — sign-in is phone + OTP" required />
        <HM2.RadioGroup label="Role" value={role} onChange={setRole} row options={[{ value: "sp", label: "Sales Person" }, { value: "mgr", label: "Manager" }]} />
        <HM2.Select label="Reports to" fullWidth value="pnair" onChange={() => {}} options={[{ value: "pnair", label: "P. Nair (Manager)" }, { value: "top", label: "— Top level —" }]} />
        <CardMg2 style={{ padding: "8px 16px" }}><HM2.ToggleSwitch label="Login active" checked={active} onChange={(e) => setActive(e.target.checked)} /></CardMg2>
      </div>
      <FooterMg2><HM2.Button variant="filled" color="primary" label="Create employee" onClick={() => {}} style={{ width: "100%" }} /></FooterMg2>
    </MScreen2>
  );
}

/* ---------- S-ORG4 Org tree view ---------- */
function OrgTreeScreen({ role = "adm" }) {
  const tab = role === "adm" ? "org" : "team";
  const Node = ({ name, sub, level, chip, last }) => (
    <div style={{ display: "flex", gap: 8, paddingLeft: level * 20 }}>
      {level > 0 && <div style={{ width: 12, borderLeft: "2px solid #E5E5E5", borderBottom: "2px solid #E5E5E5", height: 24, borderBottomLeftRadius: 6, marginTop: -12 }} />}
      <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 10, background: "#fff", border: "1px solid #E5E5E5", borderRadius: 10, padding: "10px 12px", marginBottom: 8 }}>
        <span style={{ width: 34, height: 34, borderRadius: "50%", background: level === 0 ? "#663C00" : level === 1 ? "#995A00" : "#995A001F", color: level < 2 ? "#fff" : "#995A00", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 12 }}>{name.split(" ").map(w => w[0]).join("")}</span>
        <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontSize: 14, fontWeight: 600, color: "#333" }}>{name}</div><div style={{ fontSize: 12, color: "#8C8C8C" }}>{sub}</div></div>
        {chip && <HM2.StatusBadge label={chip} color="#995A00" variant="soft" size="small" />}
      </div>
    </div>
  );
  return (
    <MScreen2 role={role} title="Org tree" back={role === "mgr"} bell tab={tab}>
      <div style={{ padding: 16 }}>
        {role === "adm" && <p style={secMg2}>Org-wide hierarchy · ≤5 levels</p>}
        {role === "adm" && <Node name="V. Menon" sub="National Head" level={0} />}
        <Node name="P. Nair" sub="Manager · North Bengaluru" level={role === "adm" ? 1 : 0} chip={role === "mgr" ? "You" : null} />
        <Node name="R. Kumar" sub="Sales Person · North BLR–West" level={role === "adm" ? 2 : 1} />
        <Node name="S. Iyer" sub="Sales Person · Peenya" level={role === "adm" ? 2 : 1} />
        <Node name="M. Das" sub="Sales Person · Yeshwanthpur" level={role === "adm" ? 2 : 1} />
      </div>
    </MScreen2>
  );
}

/* ---------- S-ORG5 Assign / move in hierarchy (Admin) ---------- */
function AssignHierarchyScreen() {
  return (
    <MScreen2 role="adm" title="Move in hierarchy" back tab="org" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <p style={secMg2}>Employee</p>
          <CardMg2 style={{ padding: 14, display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ width: 40, height: 40, borderRadius: "50%", background: "#995A00", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 }}>RK</span>
            <div style={{ flex: 1 }}><div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>R. Kumar</div><div style={{ fontSize: 13, color: "#666" }}>Sales Person</div></div>
          </CardMg2>
        </div>
        <div>
          <p style={secMg2}>Current → New manager</p>
          <CardMg2 style={{ padding: 14, display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <span style={{ fontSize: 14, color: "#8C8C8C" }}>P. Nair</span>
            <HM2.Icon name="ArrowRight" size={18} color="#995A00" />
            <span style={{ fontSize: 14, fontWeight: 700, color: "#333" }}>K. Reddy</span>
          </CardMg2>
          <HM2.Select label="New manager" fullWidth value="kreddy" onChange={() => {}} options={[{ value: "kreddy", label: "K. Reddy (Manager · South)" }, { value: "pnair", label: "P. Nair (Manager · North)" }]} />
        </div>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: "#F7F7F7", borderRadius: 10, padding: 12 }}>
          <HM2.Icon name="InfoFilled" size={18} color="#0081F2" /><span style={{ fontSize: 13, color: "#666" }}>Moves this SP's geography scope and open requests to the new manager (≤5 levels enforced).</span>
        </div>
      </div>
      <FooterMg2><HM2.Button variant="filled" color="primary" label="Confirm move" onClick={() => {}} style={{ width: "100%" }} /></FooterMg2>
    </MScreen2>
  );
}

/* ---------- S-ORG6 Assign geography / outlet scope (Admin owns; Manager view-only) ----------
   Parameters: Zone cluster · State cluster · District cluster · Shop category — all multi-select, via GeoScopePicker. */
function AssignGeographyScreen({ role = "adm" }) {
  const tab = role === "adm" ? "org" : "team";
  const readOnly = role !== "adm";
  const [scope, setScope] = useStateOrg({ districts: ["blru"], outlets: 0 });
  const Geo = window.GeoScopePicker;
  return (
    <MScreen2 role={role} title={readOnly ? "Geography scope" : "Assign geography"} back tab={tab} noNav>
      <div style={{ padding: "10px 16px", background: "#995A000D", borderBottom: "1px solid #E5E5E5", display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#8C8C8C", flexWrap: "wrap" }}>
        <span>{role === "adm" ? "Employees" : "My team"}</span><HM2.Icon name="ChevronRight" size={14} color="#BDBDBD" />
        <span>R. Kumar</span><HM2.Icon name="ChevronRight" size={14} color="#BDBDBD" />
        <span style={{ color: "#995A00", fontWeight: 700 }}>Geography</span>
      </div>
      <div style={{ padding: 12, background: "#fff", borderBottom: "1px solid #E5E5E5", fontSize: 13, color: "#666" }}>
        {readOnly
          ? <React.Fragment>Scope for <strong style={{ color: "#333" }}>R. Kumar</strong> · read-only — <strong style={{ color: "#333" }}>Admin</strong> owns geography and outlet assignment.</React.Fragment>
          : <React.Fragment>Assigning to <strong style={{ color: "#333" }}>R. Kumar</strong> · values come from the Humbee geography master</React.Fragment>}
      </div>
      <div style={{ padding: 16 }}>
        {Geo && <Geo readOnly={readOnly} initial={{ zones: ["south"], states: ["ka"], districts: ["blru", "blrr"], cats: ["grocery", "wholesale"] }} onScope={setScope} />}
      </div>
      <FooterMg2>
        {readOnly
          ? <HM2.Button variant="outlined" color="neutral" label="Assignment is Admin-only" onClick={() => {}} style={{ width: "100%" }} disabled />
          : <HM2.Button variant="filled" color="primary" label={`Assign scope · ${scope.outlets} outlets`} onClick={() => {}} style={{ width: "100%" }} disabled={!scope.districts.length} />}
      </FooterMg2>
    </MScreen2>
  );
}

Object.assign(window, { EmployeeListScreen, EmployeeDetailScreen, AddEmployeeScreen, OrgTreeScreen, AssignHierarchyScreen, AssignGeographyScreen });
