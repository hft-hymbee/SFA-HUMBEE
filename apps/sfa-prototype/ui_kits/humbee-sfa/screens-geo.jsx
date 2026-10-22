/* Humbee SFA — shared geography scoping (cluster model).
   One picker used everywhere geography is defined: Admin → assign SP, beat creation, beat edit.
   Parameters (all multi-select, cascading): Zone cluster · State cluster · District cluster · Shop category.
   UI: a compact summary card; each level opens a full-height selection sheet built for long lists
   (search, A–Z sections, select-all-matching, sticky selected footer). */
const HGeo = window.HumbeeDesignSystem_c38d59;
const { useState: useStateGeo, useMemo: useMemoGeo } = React;

const GEO_CSS = `
@keyframes hbSheetIn{from{transform:translateY(14px);opacity:.6}to{transform:none;opacity:1}}
@keyframes hbScrimIn{from{opacity:0}to{opacity:1}}
`;

const GEO_ZONES = [
  ["south", "South Zone", ["ka", "tn", "kl", "tg", "ap"]],
  ["west", "West Zone", ["mh", "gj", "rj", "goa"]],
  ["north", "North Zone", ["dl", "up", "hr", "pb"]],
  ["east", "East Zone", ["wb", "or", "as", "br"]],
];
const GEO_STATES = {
  ka: "Karnataka", tn: "Tamil Nadu", kl: "Kerala", tg: "Telangana", ap: "Andhra Pradesh",
  mh: "Maharashtra", gj: "Gujarat", rj: "Rajasthan", goa: "Goa",
  dl: "Delhi NCR", up: "Uttar Pradesh", hr: "Haryana", pb: "Punjab",
  wb: "West Bengal", or: "Odisha", as: "Assam", br: "Bihar",
};
const GEO_DISTRICTS = [
  ["blru", "Bengaluru Urban", "ka", 148], ["blrr", "Bengaluru Rural", "ka", 62], ["mys", "Mysuru", "ka", 74],
  ["tum", "Tumakuru", "ka", 41], ["blg", "Belagavi", "ka", 58], ["hub", "Dharwad–Hubballi", "ka", 66],
  ["mng", "Dakshina Kannada", "ka", 52], ["kal", "Kalaburagi", "ka", 37], ["dvg", "Davanagere", "ka", 29],
  ["chn", "Chennai", "tn", 132], ["cbe", "Coimbatore", "tn", 88], ["mdu", "Madurai", "tn", 64], ["tcy", "Tiruchirappalli", "tn", 47],
  ["ekm", "Ernakulam", "kl", 71], ["tvm", "Thiruvananthapuram", "kl", 58], ["koz", "Kozhikode", "kl", 44],
  ["hyd", "Hyderabad", "tg", 119], ["wgl", "Warangal", "tg", 38],
  ["vjw", "Vijayawada", "ap", 56], ["vsp", "Visakhapatnam", "ap", 61],
  ["pun", "Pune", "mh", 126], ["mum", "Mumbai Suburban", "mh", 164], ["ngp", "Nagpur", "mh", 73], ["nsk", "Nashik", "mh", 59],
  ["ahm", "Ahmedabad", "gj", 97], ["srt", "Surat", "gj", 84], ["vad", "Vadodara", "gj", 51],
  ["jai", "Jaipur", "rj", 79], ["jod", "Jodhpur", "rj", 42], ["pan", "North Goa", "goa", 23],
  ["ndl", "New Delhi", "dl", 141], ["gzb", "Ghaziabad", "up", 68], ["lko", "Lucknow", "up", 77],
  ["ggn", "Gurugram", "hr", 72], ["ldh", "Ludhiana", "pb", 54],
  ["kol", "Kolkata", "wb", 118], ["how", "Howrah", "wb", 46], ["bbs", "Khordha–Bhubaneswar", "or", 49],
  ["ghy", "Kamrup–Guwahati", "as", 41], ["ptn", "Patna", "br", 63],
];
const GEO_CATS = [
  ["grocery", "Grocery / kirana", 0.34], ["wholesale", "Wholesale", 0.13], ["chemist", "Chemist", 0.11],
  ["gm", "General merchant", 0.16], ["horeca", "HoReCa", 0.07], ["cnd", "Confectionery / bakery", 0.06],
  ["cosm", "Cosmetics & personal care", 0.05], ["mt", "Modern trade / self-service", 0.04], ["pan", "Pan / cigarette shop", 0.04],
];

/* ---------- Selection sheet — built for long lists ---------- */
function GeoSheet({ title, subtitle, options, value, onApply, onClose, grouped }) {
  const [sel, setSel] = useStateGeo(value);
  const [q, setQ] = useStateGeo("");
  const ql = q.trim().toLowerCase();
  const list = options.filter((o) => !ql || o[1].toLowerCase().includes(ql));
  const toggle = (id) => setSel((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  const allShown = list.length > 0 && list.every((o) => sel.includes(o[0]));
  const toggleAll = () => setSel((s) => allShown ? s.filter((x) => !list.some((o) => o[0] === x)) : [...new Set([...s, ...list.map((o) => o[0])])]);
  /* Sectioned by parent group (states) or A–Z (long flat lists). */
  const sections = useMemoGeo(() => {
    if (!grouped) return [["", list]];
    const map = new Map();
    list.forEach((o) => { const k = o[3] || "Other"; if (!map.has(k)) map.set(k, []); map.get(k).push(o); });
    return [...map.entries()];
  }, [list, grouped]);
  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 40, display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
      <div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(20,14,4,.52)", backdropFilter: "blur(2px)", animation: "hbScrimIn .2s ease both" }} />
      <div style={{ position: "relative", background: "#fff", borderTopLeftRadius: 22, borderTopRightRadius: 22, maxHeight: "88%", display: "flex", flexDirection: "column", boxShadow: "0 -10px 40px rgba(0,0,0,.28)", animation: "hbSheetIn .26s cubic-bezier(.2,.8,.2,1) both" }}>
        <div style={{ padding: "10px 0 0", display: "flex", justifyContent: "center", flexShrink: 0 }}><span style={{ width: 42, height: 4, borderRadius: 2, background: "#E0E0E0" }} /></div>
        <div style={{ padding: "10px 16px 12px", display: "flex", alignItems: "flex-start", gap: 12, flexShrink: 0 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 17, fontWeight: 800, color: "#333", letterSpacing: "-.2px" }}>{title}</div>
            <div style={{ fontSize: 12.5, color: "#8C8C8C" }}>{subtitle}</div>
          </div>
          <button type="button" onClick={onClose} style={{ width: 34, height: 34, borderRadius: "50%", border: "none", background: "#F3F3F3", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><HGeo.Icon name="Close" size={20} color="#666" /></button>
        </div>
        <div style={{ padding: "0 16px 10px", flexShrink: 0 }}>
          <HGeo.TextField placeholder={`Search ${title.toLowerCase()}`} value={q} onChange={(e) => setQ(e.target ? e.target.value : e)} startAdornment={<HGeo.Icon name="SearchOutlined" size={20} color="#8C8C8C" />} />
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "0 16px 10px", flexShrink: 0 }}>
          <span style={{ fontSize: 12.5, color: "#8C8C8C" }}>{list.length} {list.length === 1 ? "option" : "options"}{ql ? " matching" : ""}</span>
          <button type="button" onClick={toggleAll} style={{ border: "1px solid #E0D3BB", background: "#995A000D", color: "#995A00", borderRadius: 999, padding: "6px 12px", cursor: "pointer", fontFamily: "var(--font-family-base)", fontSize: 12.5, fontWeight: 800 }}>{allShown ? "Clear these" : ql ? "Select matching" : "Select all"}</button>
        </div>
        <div style={{ flex: 1, overflowY: "auto", borderTop: "1px solid #F0F0F0" }}>
          {list.length === 0 && <div style={{ padding: "36px 16px", textAlign: "center", fontSize: 13.5, color: "#8C8C8C" }}>No match for “{q}”.</div>}
          {sections.map(([head, items]) => (
            <React.Fragment key={head || "all"}>
              {head && <div style={{ position: "sticky", top: 0, zIndex: 1, background: "#FAF7F2", borderBottom: "1px solid #F0EAE0", padding: "7px 16px", fontSize: 11, fontWeight: 800, letterSpacing: ".5px", textTransform: "uppercase", color: "#9A8367" }}>{head}</div>}
              {items.map((o, i) => {
                const on = sel.includes(o[0]);
                return (
                  <div key={o[0]} onClick={() => toggle(o[0])} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 16px", cursor: "pointer", minHeight: 52, borderTop: i === 0 ? "none" : "1px solid #F5F5F5", background: on ? "#995A000A" : "#fff" }}>
                    <HGeo.Checkbox checked={on} onChange={() => toggle(o[0])} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 15, fontWeight: on ? 700 : 600, color: "#333" }}>{o[1]}</div>
                      {o[2] != null && <div style={{ fontSize: 12, color: "#9A9A9A" }}>{o[2]} outlets</div>}
                    </div>
                    {on && <HGeo.Icon name="Check" size={20} color="#995A00" />}
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
        <div style={{ borderTop: "1px solid #E5E5E5", padding: 12, display: "flex", alignItems: "center", gap: 10, flexShrink: 0, background: "#fff" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 800, color: "#333" }}>{sel.length} selected</div>
            <div style={{ fontSize: 12, color: "#8C8C8C", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sel.length ? options.filter((o) => sel.includes(o[0])).map((o) => o[1]).join(", ") : "Nothing selected yet"}</div>
          </div>
          <HGeo.Button variant="filled" color="primary" label="Apply" onClick={() => onApply(sel)} style={{ flexShrink: 0, minWidth: 108 }} />
        </div>
      </div>
    </div>
  );
}

/* ---------- Summary row per cluster level ---------- */
function GeoRow({ icon, label, hint, names, count, total, onOpen, disabled, readOnly, first }) {
  const shown = names.slice(0, 2), extra = names.length - shown.length;
  return (
    <div onClick={disabled || readOnly ? undefined : onOpen}
      style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "13px 14px", borderTop: first ? "none" : "1px solid #F2F2F2", cursor: disabled || readOnly ? "default" : "pointer", opacity: disabled ? 0.5 : 1, background: "#fff" }}>
      <div style={{ width: 36, height: 36, borderRadius: 10, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: count ? "#995A0014" : "#F5F5F5" }}>
        <HGeo.Icon name={icon} size={19} color={count ? "#995A00" : "#A8A8A8"} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 800, color: "#333" }}>{label}</span>
          {count > 0 && <span style={{ fontSize: 11, fontWeight: 800, color: "#995A00", background: "#995A0014", borderRadius: 999, padding: "2px 7px" }}>{count}{total ? ` / ${total}` : ""}</span>}
        </div>
        {count === 0 ? (
          <div style={{ fontSize: 12.5, color: "#A0A0A0", marginTop: 3 }}>{hint}</div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
            {shown.map((n) => <span key={n} style={{ fontSize: 12, fontWeight: 700, color: "#5C4423", background: "#F7F1E7", border: "1px solid #EDE1CE", borderRadius: 999, padding: "3px 9px", maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{n}</span>)}
            {extra > 0 && <span style={{ fontSize: 12, fontWeight: 800, color: "#995A00", padding: "3px 4px" }}>+{extra} more</span>}
          </div>
        )}
      </div>
      {!readOnly && <HGeo.Icon name="KeyboardArrowRight" size={20} color="#C4C4C4" />}
    </div>
  );
}

/* GeoScopePicker — single source of truth for geography scoping.
   `assigned` limits the pool to what Admin gave the SP; `readOnly` for manager view. */
function GeoScopePicker({ readOnly = false, assigned = null, initial = null, onScope }) {
  const seed = initial || { zones: ["south"], states: ["ka"], districts: ["blru"], cats: ["grocery", "wholesale"] };
  const [zones, setZones] = useStateGeo(seed.zones);
  const [states, setStates] = useStateGeo(seed.states);
  const [districts, setDistricts] = useStateGeo(seed.districts);
  const [cats, setCats] = useStateGeo(seed.cats);
  const [sheet, setSheet] = useStateGeo(null);

  const inPool = (kind, id) => !assigned || !assigned[kind] || assigned[kind].includes(id);
  const zoneOpts = GEO_ZONES.filter((z) => inPool("zones", z[0])).map((z) => [z[0], z[1], null]);
  const stateOpts = GEO_ZONES.filter((z) => zones.includes(z[0])).flatMap((z) => z[2].filter((s) => inPool("states", s)).map((s) => [s, GEO_STATES[s], null, z[1]]));
  const districtOpts = GEO_DISTRICTS.filter((d) => states.includes(d[2]) && inPool("districts", d[0])).map((d) => [d[0], d[1], d[3], GEO_STATES[d[2]]]);
  const catOpts = GEO_CATS.filter((c) => inPool("cats", c[0])).map((c) => [c[0], c[1], null]);

  const applyZones = (next) => {
    setZones(next);
    const keep = GEO_ZONES.filter((z) => next.includes(z[0])).flatMap((z) => z[2]);
    const ns = states.filter((s) => keep.includes(s));
    setStates(ns);
    setDistricts(districts.filter((d) => ns.includes((GEO_DISTRICTS.find((x) => x[0] === d) || [])[2])));
  };
  const applyStates = (next) => {
    setStates(next);
    setDistricts(districts.filter((d) => next.includes((GEO_DISTRICTS.find((x) => x[0] === d) || [])[2])));
  };

  const outlets = useMemoGeo(() => {
    const base = GEO_DISTRICTS.filter((d) => districts.includes(d[0])).reduce((s, d) => s + d[3], 0);
    const share = cats.length ? GEO_CATS.filter((c) => cats.includes(c[0])).reduce((s, c) => s + c[2], 0) : 1;
    return Math.round(base * share);
  }, [districts, cats]);
  React.useEffect(() => { if (onScope) onScope({ zones, states, districts, cats, outlets }); }, [zones, states, districts, cats, outlets]);

  const names = (opts, val) => opts.filter((o) => val.includes(o[0])).map((o) => o[1]);
  const LEVELS = [
    { id: "zone", icon: "Map", label: "Zone cluster", hint: "Select one or more zones", opts: zoneOpts, val: zones, apply: applyZones, sub: "Top of the geography hierarchy", grouped: false },
    { id: "state", icon: "LocationMarker", label: "State cluster", hint: zones.length ? "Select states inside the chosen zones" : "Choose a zone cluster first", opts: stateOpts, val: states, apply: applyStates, sub: "Grouped by zone", grouped: true, disabled: !zones.length },
    { id: "district", icon: "LocationPin", label: "District cluster", hint: states.length ? "Select districts inside the chosen states" : "Choose a state cluster first", opts: districtOpts, val: districts, apply: setDistricts, sub: "Grouped by state · outlet counts shown", grouped: true, disabled: !states.length },
    { id: "cat", icon: "InventoryOutlined", label: "Shop category", hint: "All categories if none selected", opts: catOpts, val: cats, apply: setCats, sub: "Filters which outlets enter the scope", grouped: false },
  ];
  const active = LEVELS.find((l) => l.id === sheet);
  const filled = LEVELS.filter((l) => l.val.length).length;
  return (
    <div>
      <style>{GEO_CSS}</style>
      {!readOnly && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <div style={{ flex: 1, height: 4, borderRadius: 2, background: "#EDEDED", overflow: "hidden" }}><div style={{ width: `${(filled / 4) * 100}%`, height: "100%", background: "#995A00", transition: "width .25s ease" }} /></div>
          <span style={{ fontSize: 11.5, fontWeight: 800, color: "#9A9A9A", flexShrink: 0 }}>{filled}/4 set</span>
        </div>
      )}
      <div style={{ background: "#fff", border: "1px solid #E8E8E8", borderRadius: 14, overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,.04)" }}>
        {LEVELS.map((l, i) => (
          <GeoRow key={l.id} first={i === 0} icon={l.icon} label={l.label} hint={l.hint} names={names(l.opts, l.val)}
            count={l.val.length} total={l.opts.length} disabled={l.disabled} readOnly={readOnly} onOpen={() => setSheet(l.id)} />
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12, background: "linear-gradient(135deg,#FBF6EE,#F6EEE1)", border: "1px solid #EADFCB", borderRadius: 14, padding: 14 }}>
        <div style={{ width: 42, height: 42, borderRadius: 12, background: "#995A0017", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><HGeo.Icon name="InventoryOutlined" size={22} color="#995A00" /></div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 19, fontWeight: 800, color: "#5C4423", lineHeight: 1.1 }}>{outlets.toLocaleString("en-IN")} outlets</div>
          <div style={{ fontSize: 12, color: "#8A7355", marginTop: 2 }}>in scope · {districts.length} district cluster{districts.length === 1 ? "" : "s"} · {cats.length ? `${cats.length} categor${cats.length === 1 ? "y" : "ies"}` : "all categories"}</div>
        </div>
      </div>
      {active && !readOnly && (
        <GeoSheet title={active.label} subtitle={active.sub} options={active.opts} value={active.val} grouped={active.grouped}
          onApply={(next) => { active.apply(next); setSheet(null); }} onClose={() => setSheet(null)} />
      )}
    </div>
  );
}

Object.assign(window, { GeoScopePicker, GEO_ZONES, GEO_STATES, GEO_DISTRICTS, GEO_CATS });
