/* Humbee SFA — Manager: team overview + per-SP day view with an animated activity timeline.
   Answers "what did this SP do on this day" — date-scoped KPIs on top, chronological activity below. */
const HT = window.HumbeeDesignSystem_c38d59;
const MScreenT = window.MScreen, CardMgT = window.CardMg, secMgT = window.secMg, FooterMgT = window.FooterMg;
const { useState: useStateT, useEffect: useEffectT } = React;

const TL_CSS = `
@keyframes hbTlIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@keyframes hbTlPop{0%{transform:scale(.4);opacity:0}60%{transform:scale(1.15);opacity:1}100%{transform:scale(1)}}
@keyframes hbTlRail{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes hbPulse{0%{box-shadow:0 0 0 0 rgba(0,128,0,.45)}70%{box-shadow:0 0 0 14px rgba(0,128,0,0)}100%{box-shadow:0 0 0 0 rgba(0,128,0,0)}}
@keyframes hbBar{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes hbKpiIn{from{opacity:0;transform:translateY(8px) scale(.98)}to{opacity:1;transform:none}}
`;

/* Per-day activity feed for one sales person. Ordered, typed, and duration-aware. */
const DAYS = {
  today: {
    label: "Today · Fri, 14 Aug", live: true,
    kpi: [["Route coverage", "3 / 6", "50% of beat", "#995A00"], ["Productive visits", "2", "of 3 done", "#0081F2"], ["Orders", "₹ 17,940", "2 orders", "#995A00"], ["Official work", "45 m", "1 task", "#8C8C8C"]],
    events: [
      ["09:12", "punch", "Punched in", "MG Road, Bengaluru · ±8 m", null, null],
      ["09:22", "travel", "Travel to Metro Wholesale", "3.2 km · 18 min", null, null],
      ["09:40", "visit", "Metro Wholesale", "Physical visit · Distribution Partner", "22 min", "₹ 12,400"],
      ["10:06", "travel", "Travel to Krishna Stores", "1.4 km · 11 min", null, null],
      ["10:24", "visit", "Krishna Stores", "Physical visit · Dealer", "18 min", "₹ 5,540"],
      ["11:10", "call", "Sri Balaji Agency", "Telephonic visit · no order", "6 min", null],
      ["11:48", "outlet", "Sai Provision Store onboarded", "New outlet · pending verification", null, null],
      ["12:30", "official", "Bank deposit", "Official work · Yeshwanthpur branch", "45 min", null],
      ["13:35", "missed", "Gupta & Sons", "Missed visit · shop closed", null, null],
      ["14:20", "live", "Anand Distributors", "Visit in progress · checked in 14:20", "12 min", null],
    ],
  },
  yesterday: {
    label: "Yesterday · Thu, 13 Aug", live: false,
    kpi: [["Route coverage", "6 / 6", "100% of beat", "#008000"], ["Productive visits", "5", "of 6 done", "#0081F2"], ["Orders", "₹ 41,260", "5 orders", "#995A00"], ["On duty", "9h 08m", "9:04 AM – 6:12 PM", "#008000"]],
    events: [
      ["09:04", "punch", "Punched in", "Peenya Phase 1 · ±6 m", null, null],
      ["09:26", "visit", "Anand Distributors", "Physical visit · Distribution Partner", "26 min", "₹ 18,900"],
      ["10:18", "visit", "Sri Balaji Agency", "Physical visit · Dealer", "19 min", "₹ 7,150"],
      ["11:40", "visit", "Krishna Stores", "Physical visit · Dealer", "16 min", "₹ 4,820"],
      ["13:10", "lead", "Lead captured — ITC", "Aashirvaad · Atta 10 kg · hot", null, null],
      ["14:05", "visit", "Metro Wholesale", "Physical visit · Distribution Partner", "24 min", "₹ 10,390"],
      ["16:30", "visit", "Gupta & Sons", "Physical visit · Dealer", "14 min", null],
      ["18:12", "punchout", "Punched out", "Yeshwanthpur · day closed", "9h 08m", null],
    ],
  },
  pick: {
    label: "Mon, 4 Aug", live: false,
    kpi: [["Route coverage", "2 / 5", "40% of beat", "#CC0000"], ["Productive visits", "1", "of 2 done", "#0081F2"], ["Orders", "₹ 6,300", "1 order", "#995A00"], ["Official work", "1h 20m", "2 tasks", "#8C8C8C"]],
    events: [
      ["09:30", "punch", "Punched in", "Malleshwaram · ±11 m", null, null],
      ["09:58", "visit", "Krishna Stores", "Physical visit · Dealer", "21 min", "₹ 6,300"],
      ["11:15", "official", "Distributor collection", "Official work", "1h 20m", null],
      ["13:40", "missed", "Metro Wholesale", "Missed visit · owner unavailable", null, null],
      ["14:05", "leave", "Half day approved", "Personal · approved by you", null, null],
    ],
  },
};

const EV = {
  punch: ["GpsFixed", "#008000", "Attendance"],
  punchout: ["LogoutOutlined", "#008000", "Attendance"],
  visit: ["LocationMarker", "#995A00", "Visit"],
  call: ["Call", "#0081F2", "Telephonic"],
  official: ["Schedule", "#7A5CD6", "Official work"],
  missed: ["Close", "#CC0000", "Missed"],
  live: ["LocationMarker", "#008000", "Live"],
  outlet: ["InventoryOutlined", "#0081F2", "Onboarding"],
  lead: ["RewardsOutlined", "#995A00", "Lead"],
  leave: ["Calendar", "#FFBF40", "Leave"],
};

function TravelLeg({ title, sub, delay }) {
  return (
    <div style={{ display: "flex", gap: 14, animation: `hbTlIn .45s ease both`, animationDelay: `${delay}ms` }}>
      <div style={{ width: 34, display: "flex", justifyContent: "center" }}>
        <div style={{ width: 2, height: 34, background: "repeating-linear-gradient(180deg,#C9C9C9 0 5px,transparent 5px 12px)" }} />
      </div>
      <div style={{ flex: 1, paddingBottom: 10, display: "flex", alignItems: "center", gap: 8, minHeight: 34 }}>
        <HT.Icon name="Map" size={15} color="#A8A8A8" />
        <span style={{ fontSize: 12, color: "#9A9A9A" }}>{title.replace("Travel to ", "Travel · ")} — {sub}</span>
      </div>
    </div>
  );
}

function TimelineEvent({ e, i, last }) {
  const [time, kind, title, sub, dur, value] = e;
  const [icon, tone, tag] = EV[kind] || EV.visit;
  const live = kind === "live";
  const delay = i * 80;
  return (
    <div style={{ display: "flex", gap: 14, position: "relative" }}>
      <div style={{ width: 34, display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
        <div style={{ width: 34, height: 34, borderRadius: "50%", background: live ? "#008000" : tone + "14", border: `1.5px solid ${live ? "#008000" : tone + "40"}`, display: "flex", alignItems: "center", justifyContent: "center", animation: `hbTlPop .5s cubic-bezier(.34,1.56,.64,1) both${live ? ", hbPulse 2s ease-out infinite 700ms" : ""}`, animationDelay: `${delay}ms`, flexShrink: 0 }}>
          <HT.Icon name={icon} size={18} color={live ? "#fff" : tone} />
        </div>
        {!last && <div style={{ flex: 1, width: 2, background: "linear-gradient(180deg,#E0E0E0,#EFEFEF)", transformOrigin: "top", animation: "hbTlRail .6s ease both", animationDelay: `${delay + 120}ms`, minHeight: 12 }} />}
      </div>
      <div style={{ flex: 1, minWidth: 0, paddingBottom: last ? 0 : 14, animation: "hbTlIn .5s ease both", animationDelay: `${delay + 40}ms` }}>
        <div style={{ background: "#fff", border: `1px solid ${live ? "#B7E0B7" : "#EAEAEA"}`, borderRadius: 12, padding: "11px 13px", boxShadow: live ? "0 2px 10px rgba(0,128,0,.10)" : "0 1px 3px rgba(0,0,0,.04)" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 3 }}>
            <span style={{ fontSize: 12, fontWeight: 800, color: tone, fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>{time}</span>
            <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: ".4px", textTransform: "uppercase", color: "#A0A0A0" }}>{tag}</span>
            {live && <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 800, color: "#008000" }}><span style={{ width: 7, height: 7, borderRadius: "50%", background: "#008000", animation: "hbPulse 1.8s ease-out infinite" }} />LIVE</span>}
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#333", lineHeight: 1.25 }}>{title}</div>
          <div style={{ fontSize: 12.5, color: "#777", marginTop: 2 }}>{sub}</div>
          {(dur || value) && (
            <div style={{ display: "flex", gap: 8, marginTop: 9, flexWrap: "wrap" }}>
              {dur && <span style={{ display: "inline-flex", alignItems: "center", gap: 5, background: "#F5F5F5", borderRadius: 999, padding: "4px 9px", fontSize: 11.5, fontWeight: 700, color: "#666" }}><HT.Icon name="Schedule" size={13} color="#8C8C8C" />{dur}</span>}
              {value && <span style={{ display: "inline-flex", alignItems: "center", gap: 4, background: "#995A0014", borderRadius: 999, padding: "4px 9px", fontSize: 11.5, fontWeight: 800, color: "#995A00" }}><HT.Icon name="ShoppingCartOutlined" size={13} color="#995A00" />{value}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------- S-TEAM2 SP day view (date-scoped KPIs + animated activity timeline) ---------- */
function SpDayScreen({ role = "mgr", scope = "today" }) {
  const [day, setDay] = useStateT(scope);
  const [replay, setReplay] = useStateT(0);
  const d = DAYS[day];
  const rows = d.events.filter((e) => e[1] !== "travel");
  const pick = (label) => { const row = d.kpi.find((k) => k[0] === label); return row ? row[1] : "—"; };
  const done = pick("Route coverage");
  useEffectT(() => { setReplay((r) => r + 1); }, [day]);
  const SCOPES = [["today", "Today"], ["yesterday", "Yesterday"], ["pick", "Pick date"]];
  return (
    <MScreenT role={role} title="R. Kumar" back tab={role === "adm" ? "org" : "team"} noNav bodyBg="#F4F4F4">
      <style>{TL_CSS}</style>
      {/* Premium identity header */}
      <div style={{ background: "linear-gradient(135deg,#663C00 0%,#995A00 62%,#B87514 100%)", padding: "16px 16px 18px", color: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 13 }}>
          <span style={{ width: 50, height: 50, borderRadius: "50%", background: "#ffffff26", border: "1.5px solid #ffffff59", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 17, flexShrink: 0 }}>RK</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-.2px" }}>Rahul Kumar</div>
            <div style={{ fontSize: 12.5, color: "#F2E2CB" }}>Sales Person · North BLR–West · HB-SP-2048</div>
          </div>
          <a href="tel:+919800043210" style={{ width: 40, height: 40, borderRadius: "50%", background: "#ffffff26", border: "1px solid #ffffff59", display: "flex", alignItems: "center", justifyContent: "center", textDecoration: "none", flexShrink: 0 }}><HT.Icon name="Call" size={20} color="#fff" /></a>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 13 }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, background: d.live ? "#0080004D" : "#ffffff1F", border: `1px solid ${d.live ? "#9BD79B" : "#ffffff40"}`, borderRadius: 999, padding: "5px 11px", fontSize: 12, fontWeight: 800 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: d.live ? "#8CE68C" : "#E3D3BC" }} />{d.live ? "On duty now" : "Day closed"}
          </span>
          <span style={{ fontSize: 12, color: "#F2E2CB" }}>{done} visits · {pick("Orders")}</span>
        </div>
      </div>
      {/* Date scope */}
      <div style={{ position: "sticky", top: 0, zIndex: 2, background: "#fff", borderBottom: "1px solid #E5E5E5", padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ display: "flex", gap: 6, background: "#F0F0F0", borderRadius: 10, padding: 4 }}>
          {SCOPES.map((s) => {
            const on = day === s[0];
            return <button key={s[0]} type="button" onClick={() => setDay(s[0])} style={{ flex: 1, minHeight: 40, border: "none", borderRadius: 8, cursor: "pointer", background: on ? "#fff" : "transparent", color: on ? "#995A00" : "#666", fontFamily: "var(--font-family-base)", fontSize: 13.5, fontWeight: 800, boxShadow: on ? "0 1px 3px rgba(0,0,0,.12)" : "none" }}>{s[1]}</button>;
          })}
        </div>
        {day === "pick" && <HT.DateField label="" value="Mon, 4 Aug 2026" onClick={() => {}} />}
        <div style={{ fontSize: 12.5, color: "#8C8C8C" }}>{d.label}</div>
      </div>
      {/* Day KPIs */}
      <div style={{ padding: 16 }} key={`kpi-${replay}`}>
        <p style={secMgT}>Day performance</p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {d.kpi.map((k, i) => (
            <div key={k[0]} style={{ background: "#fff", border: "1px solid #EAEAEA", borderRadius: 12, padding: "12px 13px", animation: "hbKpiIn .4s ease both", animationDelay: `${i * 55}ms` }}>
              <div style={{ fontSize: 11.5, color: "#8C8C8C", fontWeight: 700 }}>{k[0]}</div>
              <div style={{ fontSize: 21, fontWeight: 800, color: k[3], lineHeight: 1.15, marginTop: 2 }}>{k[1]}</div>
              <div style={{ fontSize: 11.5, color: "#9A9A9A" }}>{k[2]}</div>
            </div>
          ))}
        </div>
      </div>
      {/* Animated activity timeline */}
      <div style={{ padding: "0 16px 20px" }} key={`tl-${replay}`}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 12 }}>
          <p style={{ ...secMgT, margin: 0 }}>Activity timeline</p>
          <button type="button" onClick={() => setReplay((r) => r + 1)} style={{ display: "inline-flex", alignItems: "center", gap: 5, border: "1px solid #E0E0E0", background: "#fff", borderRadius: 999, padding: "5px 10px", cursor: "pointer", fontFamily: "var(--font-family-base)", fontSize: 11.5, fontWeight: 700, color: "#666" }}><HT.Icon name="Autorenew" size={14} color="#995A00" />Replay</button>
        </div>
        <div>
          {rows.map((e, i) => {
            const src = d.events.indexOf(e);
            const leg = d.events[src - 1] && d.events[src - 1][1] === "travel" ? d.events[src - 1] : null;
            return (
              <React.Fragment key={`${e[0]}-${e[2]}`}>
                {leg && <TravelLeg title={leg[2]} sub={leg[3]} delay={i * 80} />}
                <TimelineEvent e={e} i={i} last={i === rows.length - 1} />
              </React.Fragment>
            );
          })}
        </div>
        {/* Day roll-up */}
        <div style={{ marginTop: 6, background: "#fff", border: "1px solid #EAEAEA", borderRadius: 12, padding: 14, animation: "hbKpiIn .5s ease both", animationDelay: `${rows.length * 80 + 120}ms` }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 800, color: "#333" }}>Time on outlets vs travel</span>
            <span style={{ fontSize: 12, color: "#8C8C8C" }}>{day === "yesterday" ? "9h 08m" : "5h 12m"} on duty</span>
          </div>
          <div style={{ display: "flex", height: 10, borderRadius: 999, overflow: "hidden", background: "#F0F0F0" }}>
            {[["#995A00", 46, "Outlets"], ["#C9A063", 24, "Travel"], ["#7A5CD6", 14, "Official"], ["#E0E0E0", 16, "Idle"]].map((b, i) => (
              <div key={b[2]} style={{ width: `${b[1]}%`, background: b[0], transformOrigin: "left", animation: "hbBar .6s ease both", animationDelay: `${rows.length * 80 + 200 + i * 90}ms` }} />
            ))}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 9 }}>
            {[["#995A00", "Outlets 46%"], ["#C9A063", "Travel 24%"], ["#7A5CD6", "Official 14%"], ["#E0E0E0", "Idle 16%"]].map((l) => (
              <span key={l[1]} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11.5, color: "#666", fontWeight: 600 }}><span style={{ width: 9, height: 9, borderRadius: 3, background: l[0] }} />{l[1]}</span>
            ))}
          </div>
        </div>
      </div>
      <FooterMgT>
        <div style={{ display: "flex", gap: 8 }}>
          <HT.Button variant="outlined" color="neutral" label="Month view" onClick={() => {}} style={{ flex: 1 }} />
          <HT.Button variant="filled" color="primary" label="Schedule combined visit" onClick={() => {}} style={{ flex: 1.5 }} />
        </div>
      </FooterMgT>
    </MScreenT>
  );
}

/* ---------- S-TEAM1 Team overview (manager) — one premium card per SP, today at a glance ---------- */
function TeamOverviewScreen({ role = "mgr", variant = "default" }) {
  const [f, setF] = useStateT("all");
  const TEAM = [
    ["R. Kumar", "RK", "North BLR–West", "on", "9:12 AM", 3, 6, "₹ 17.9K", 68],
    ["S. Iyer", "SI", "Peenya", "on", "9:04 AM", 2, 5, "₹ 9.2K", 91],
    ["M. Das", "MD", "Yeshwanthpur", "late", "10:46 AM", 5, 5, "₹ 22.4K", 45],
    ["A. Rao", "AR", "Malleshwaram", "off", "—", 0, 6, "—", 24],
  ];
  if (variant === "loading") return <MScreenT role={role} title="Team" bell tab="team"><div>{[0, 1, 2, 3].map((i) => <HT.SkeletonRow key={i} />)}</div></MScreenT>;
  const FILTERS = [["all", "All 4"], ["on", "On duty 2"], ["late", "Late 1"], ["off", "No punch-in 1"]];
  const STATE = { on: ["#008000", "On duty"], late: ["#FFBF40", "Late punch-in"], off: ["#8C8C8C", "No punch-in"] };
  return (
    <MScreenT role={role} title="Team" bell tab="team" bodyBg="#F4F4F4" offline={variant === "offline"}>
      <style>{TL_CSS}</style>
      <div style={{ background: "#fff", borderBottom: "1px solid #E5E5E5", padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
        <HT.TextField placeholder="Search your team" value="" onChange={() => {}} startAdornment={<HT.Icon name="SearchOutlined" size={20} color="#8C8C8C" />} />
        <div style={{ display: "flex", gap: 8, overflowX: "auto" }}>
          {FILTERS.map((x) => { const on = f === x[0]; return <span key={x[0]} onClick={() => setF(x[0])} style={{ flexShrink: 0, padding: "7px 14px", borderRadius: 999, fontSize: 13, fontWeight: 700, cursor: "pointer", border: `1px solid ${on ? "#995A00" : "#D9D9D9"}`, color: on ? "#995A00" : "#666", background: on ? "#995A001F" : "#fff" }}>{x[1]}</span>; })}
        </div>
      </div>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", gap: 10 }}>
          {[["2/4", "On route", "#008000"], ["10/22", "Visited", "#995A00"], ["₹ 49.5K", "Orders", "#0081F2"]].map((s, i) => (
            <div key={s[1]} style={{ flex: 1, background: "#fff", border: "1px solid #EAEAEA", borderRadius: 12, padding: "11px 8px", textAlign: "center", animation: "hbKpiIn .4s ease both", animationDelay: `${i * 60}ms` }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: s[2] }}>{s[0]}</div><div style={{ fontSize: 11, color: "#8C8C8C", fontWeight: 600 }}>{s[1]}</div>
            </div>
          ))}
        </div>
        {TEAM.map((t, i) => {
          const st = STATE[t[3]];
          const pct = Math.round((t[5] / t[6]) * 100);
          return (
            <div key={t[0]} onClick={() => {}} style={{ background: "#fff", border: "1px solid #EAEAEA", borderRadius: 14, padding: 14, cursor: "pointer", boxShadow: "0 1px 3px rgba(0,0,0,.04)", animation: "hbKpiIn .45s ease both", animationDelay: `${180 + i * 70}ms` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ position: "relative", width: 44, height: 44, borderRadius: "50%", background: t[3] === "off" ? "#BDBDBD" : "#995A00", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 14, flexShrink: 0 }}>{t[1]}
                  <span style={{ position: "absolute", right: -1, bottom: -1, width: 13, height: 13, borderRadius: "50%", background: st[0], border: "2px solid #fff" }} />
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15.5, fontWeight: 800, color: "#333" }}>{t[0]}</div>
                  <div style={{ fontSize: 12, color: "#8C8C8C" }}>{t[2]} · in {t[4]}</div>
                </div>
                <span style={{ fontSize: 11.5, fontWeight: 800, color: st[0], background: st[0] + "14", borderRadius: 999, padding: "4px 9px", flexShrink: 0 }}>{st[1]}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
                {[["Visits", `${t[5]}/${t[6]}`], ["Orders", t[7]], ["MTD target", `${t[8]}%`]].map((m) => (
                  <div key={m[0]} style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 11, color: "#9A9A9A", fontWeight: 600 }}>{m[0]}</div>
                    <div style={{ fontSize: 14.5, fontWeight: 800, color: "#333" }}>{m[1]}</div>
                  </div>
                ))}
                <HT.Icon name="KeyboardArrowRight" size={22} color="#C4C4C4" />
              </div>
              <div style={{ marginTop: 10, height: 6, borderRadius: 3, background: "#F0F0F0", overflow: "hidden" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: pct >= 80 ? "#008000" : pct >= 50 ? "#995A00" : "#CC0000", transformOrigin: "left", animation: "hbBar .7s ease both", animationDelay: `${300 + i * 70}ms` }} />
              </div>
              <div style={{ fontSize: 11, color: "#9A9A9A", marginTop: 6 }}>Beat coverage today · tap for full day timeline</div>
            </div>
          );
        })}
      </div>
    </MScreenT>
  );
}

Object.assign(window, { SpDayScreen, TeamOverviewScreen });
