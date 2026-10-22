/* Humbee SFA — Sales Person screens, part 3 (rebuilt): Outlet visit, Order flow, Status.
   Association-level aware: Dealer buys only from its Distribution Partner (direct, no approval); DP buys direct from a Manufacturer against an open PO (needs approval). */
const H3 = window.HumbeeDesignSystem_c38d59;
const Screen3 = window.SFA_Screen, Card3 = window.SFA_Card;
const { useState: useState3, useEffect: useEffect3 } = React;
const sec3 = { fontSize: 12, fontWeight: 700, letterSpacing: ".3px", textTransform: "uppercase", color: "#8C8C8C", margin: "0 0 8px" };
const FooterBar = ({ children }) => <div style={{ position: "sticky", bottom: 0, background: "#fff", borderTop: "1px solid #E5E5E5", padding: 12 }}>{children}</div>;

function useElapsed(start = 742) {
  const [s, setS] = useState3(start);
  useEffect3(() => { const t = setInterval(() => setS((v) => v + 1), 1000); return () => clearInterval(t); }, []);
  const mm = String(Math.floor(s / 60)).padStart(2, "0"), ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

/* Compact inline quantity stepper — replaces the bulky QuantityHandler in dense lists. */
function MiniStepper({ value, onInc, onDec, tone = "#995A00" }) {
  const btn = { width: 34, height: 34, border: "none", background: "transparent", color: tone, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 };
  return (
    <div style={{ display: "inline-flex", alignItems: "center", border: `1px solid ${tone}`, borderRadius: 8, height: 34, overflow: "hidden", background: "#fff" }}>
      <button type="button" style={btn} onClick={onDec}><H3.Icon name="Minus" size={18} color={tone} /></button>
      <span style={{ minWidth: 26, textAlign: "center", fontSize: 15, fontWeight: 700, color: "#333" }}>{value}</span>
      <button type="button" style={btn} onClick={onInc}><H3.Icon name="Add" size={18} color={tone} /></button>
    </div>
  );
}

const LEVEL = {
  dealer: { label: "Dealer", tone: "#0081F2" },
  dp: { label: "Distribution Partner", tone: "#995A00" },
};

/* ---------- S-ROUTE4 Outlet visit (visit type + association-level aware) ---------- */
function OutletVisitScreen({ level = "dp", hasDirections = true, visitType = "physical", planned = true }) {
  const [vt, setVt] = useState3(visitType);
  const elapsed = useElapsed(level === "dealer" ? 128 : 742);
  const lv = LEVEL[level];
  const isDealer = level === "dealer";
  const tele = vt === "telephonic";
  return (
    <Screen3 title="Krishna Stores" back tab="route" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
        {/* Visit type — every visit is recorded as physical or telephonic */}
        <div>
          <p style={sec3}>Visit type</p>
          <div style={{ display: "flex", gap: 10 }}>
            {[["physical", "Physical visit", "LocationMarker"], ["telephonic", "Telephonic call", "Call"]].map((t) => {
              const on = vt === t[0];
              return (
                <button key={t[0]} type="button" onClick={() => setVt(t[0])}
                  style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "12px 10px", borderRadius: 10, cursor: "pointer", background: on ? "#995A001F" : "#fff", border: `1.5px solid ${on ? "#995A00" : "#E5E5E5"}`, fontFamily: "var(--font-family-base)", fontSize: 14, fontWeight: 700, color: on ? "#995A00" : "#333" }}>
                  <H3.Icon name={t[2]} size={20} color={on ? "#995A00" : "#8C8C8C"} /> {t[1]}
                </button>
              );
            })}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
            <H3.StatusChip status={planned ? "verified" : "pending"} label={planned ? "Planned visit" : "Unplanned visit"} type="outlined" />
            <span style={{ fontSize: 12, color: "#8C8C8C" }}>{planned ? "From today's beat route" : "Added outside the planned route"}</span>
          </div>
        </div>

        {/* Visit timer — check-in / live duration / end visit */}
        <div style={{ background: "#0080000D", border: "1px solid #B7E0B7", borderRadius: 12, padding: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#008000", flexShrink: 0, boxShadow: "0 0 0 4px #0080001A" }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, color: "#448044", fontWeight: 700 }}>{tele ? "Call in progress" : "Visit in progress"}</div>
              <div style={{ fontSize: 12, color: "#5B865B" }}>{tele ? "Started 10:24 AM · no GPS capture on calls" : "Check-in 10:24 AM · check-out on end"}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: "#008000", fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>{elapsed}</div>
              <div style={{ fontSize: 11, color: "#5B865B" }}>{tele ? "call duration" : "time on outlet"}</div>
            </div>
          </div>
          <H3.Button variant="outlined" color="neutral" size="small" label={tele ? "End call & log" : "End visit & check out"} leftIcon={<H3.Icon name="LogoutOutlined" size={18} color="#333" />} onClick={() => {}} style={{ width: "100%", marginTop: 12 }} />
        </div>

        {/* Outlet header */}
        <Card3 style={{ padding: 16 }}>
          <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
            <div style={{ width: 48, height: 48, borderRadius: 10, background: lv.tone + "1A", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><H3.Icon name="InventoryOutlined" size={26} color={lv.tone} /></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 17, fontWeight: 700, color: "#333" }}>Krishna Stores</div>
              <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, color: "#666", marginTop: 4 }}><H3.Icon name="LocationPin" size={16} color="#8C8C8C" /> Yeshwanthpur · 1.4 km</div>
            </div>
            <H3.StatusBadge label={lv.label} color={lv.tone} variant="soft" size="small" />
          </div>
          {/* Directions OR capture location — physical visits only */}
          {tele ? (
            <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
              <H3.Button variant="filled" color="primary" size="small" label="Call outlet" leftIcon={<H3.Icon name="Call" size={18} color="#fff" />} onClick={() => {}} style={{ width: "100%" }} />
            </div>
          ) : hasDirections ? (
            <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
              <H3.Button variant="outlined" color="neutral" size="small" label="Call" leftIcon={<H3.Icon name="Call" size={18} color="#333" />} onClick={() => {}} style={{ flex: 1 }} />
              <H3.Button variant="outlined" color="primary" size="small" label="Directions" leftIcon={<H3.Icon name="Map" size={18} color="#995A00" />} onClick={() => {}} style={{ flex: 1 }} />
            </div>
          ) : (
            <div style={{ marginTop: 14, background: "#FFF6E5", border: "1px solid #FFD98A", borderRadius: 10, padding: 12, display: "flex", gap: 10, alignItems: "center" }}>
              <H3.Icon name="GpsFixed" size={22} color="#995A00" />
              <div style={{ flex: 1 }}><div style={{ fontSize: 13, fontWeight: 700, color: "#663C00" }}>No saved location</div><div style={{ fontSize: 12, color: "#8A6D3B" }}>Save this shop's GPS for next visit</div></div>
              <H3.Button variant="filled" color="primary" size="small" label="Save" onClick={() => {}} />
            </div>
          )}
        </Card3>

        {/* Outlet snapshot — identity + visit/commercial history, informational only */}
        <Card3 style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "12px 16px 10px", borderBottom: "1px solid #F0F0F0" }}>
            <p style={{ ...sec3, margin: 0 }}>Outlet snapshot</p>
          </div>
          <div style={{ padding: "10px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
            {[["Contact", "Ramesh Kumar"], ["GST", "29ABCDE1234F1Z5"]].map((r) => (
              <div key={r[0]} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, fontSize: 14 }}>
                <span style={{ color: "#8C8C8C", flexShrink: 0 }}>{r[0]}</span>
                <span style={{ color: "#333", fontWeight: 600, textAlign: "right", minWidth: 0, overflowWrap: "anywhere" }}>{r[1]}</span>
              </div>
            ))}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, fontSize: 14, minHeight: 44 }}>
              <span style={{ color: "#8C8C8C", flexShrink: 0 }}>Mobile</span>
              <a href="tel:+919800043210" style={{ display: "flex", alignItems: "center", gap: 6, color: "#995A00", fontWeight: 700, textDecoration: "none" }}><H3.Icon name="Call" size={18} color="#995A00" /> +91 98··· 43210</a>
            </div>
          </div>
          <div style={{ borderTop: "1px solid #F0F0F0", padding: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {[["Last visit", "28 Jul 2026"], ["Visits this month", "4"], ["Orders this month", "3"], ["Order value", "₹ 34,800"]].map((s) => (
              <div key={s[0]} style={{ background: "#F7F7F7", borderRadius: 10, padding: "10px 12px", minWidth: 0 }}>
                <div style={{ fontSize: 11, color: "#8C8C8C", fontWeight: 600 }}>{s[0]}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#333", overflowWrap: "anywhere" }}>{s[1]}</div>
              </div>
            ))}
          </div>
          <div style={{ borderTop: "1px solid #F0F0F0", padding: "10px 16px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
            <span style={{ fontSize: 13, color: "#8C8C8C" }}>Last order</span>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}><H3.StatusChip status="approved" label="Approved" type="outlined" /><span style={{ fontSize: 13, color: "#666" }}>28 Jul</span></span>
          </div>
          {/* Full outlet insight — opens an external web view rendered by the insights API */}
          <div style={{ borderTop: "1px solid #F0F0F0", padding: 12 }}>
            <H3.Button variant="outlined" color="primary" label="Open full outlet insights" leftIcon={<H3.Icon name="Dashboard" size={18} color="#995A00" />} onClick={() => {}} style={{ width: "100%" }} />
            <div style={{ fontSize: 11.5, color: "#8C8C8C", marginTop: 6, textAlign: "center" }}>Opens the Humbee insight web view · credit, trend, top SKUs</div>
          </div>
        </Card3>

        {/* Order section — outlet classification drives the path (from Humbee API) */}
        <div>
          <p style={sec3}>{isDealer ? "Order from its distribution partner — no approval needed" : "Order direct from a manufacturer — needs manager approval"}</p>
          {isDealer ? (
            <button style={supplierBtn("#995A00")}>
              <div style={{ width: 44, height: 44, borderRadius: 10, background: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, color: "#995A00", fontSize: 16, flexShrink: 0 }}>SD</div>
              <div style={{ flex: 1, textAlign: "left", minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#fff" }}>Shakti Distributors</div>
                <div style={{ fontSize: 12, color: "#FFE9C7" }}>Aashirvaad (ITC) · Fortune · Tata Consumer</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 4, color: "#fff", fontWeight: 700, fontSize: 14 }}>Order <H3.Icon name="KeyboardArrowRight" size={22} color="#fff" /></div>
            </button>
          ) : (
            <Card3 style={{ padding: 0, overflow: "hidden" }}>
              {[["Aashirvaad (ITC)", "AI", "₹ 1.2L credit", "42 SKUs"], ["Fortune (Adani)", "FA", "₹ 80k credit", "28 SKUs"], ["Tata Consumer", "TC", "₹ 60k credit", "35 SKUs"]].map((m, i) => (
                <React.Fragment key={m[0]}>
                  {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                  <H3.ListRow leading={<span style={{ width: 40, height: 40, borderRadius: 10, background: "#995A001F", color: "#995A00", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 14 }}>{m[1]}</span>}
                    title={m[0]} subtitle={`${m[3]} · ${m[2]}`} showChevron onClick={() => {}} />
                </React.Fragment>
              ))}
            </Card3>
          )}
        </div>

        {/* Secondary path + notes */}
        <button style={outcomeBtn}>
          <div style={{ width: 40, height: 40, borderRadius: "50%", background: "#F5F5F5", display: "flex", alignItems: "center", justifyContent: "center" }}><H3.Icon name="Edit" size={20} color="#995A00" /></div>
          <div style={{ flex: 1, textAlign: "left" }}><div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>Log visit outcome</div><div style={{ fontSize: 13, color: "#666" }}>No order — record a reason</div></div>
          <H3.Icon name="KeyboardArrowRight" size={24} color="#8C8C8C" />
        </button>
        <H3.TextField placeholder="Add a note about this visit (optional)" multiline rows={2} value="" onChange={() => {}} />
      </div>
    </Screen3>
  );
}
const supplierBtn = (bg) => ({ display: "flex", alignItems: "center", gap: 12, width: "100%", padding: 14, borderRadius: 12, border: "none", background: bg, cursor: "pointer", fontFamily: "var(--font-family-base)", boxShadow: "0 6px 16px rgba(153,90,0,0.28)" });
const outcomeBtn = { display: "flex", alignItems: "center", gap: 12, width: "100%", padding: 14, borderRadius: 12, border: "1px solid #E5E5E5", background: "#fff", cursor: "pointer", fontFamily: "var(--font-family-base)" };

/* ---------- S-ORD1 Start order ---------- */
function StartOrderScreen({ level = "dp" }) {
  const isDealer = level === "dealer";
  return (
    <Screen3 title="Start order" back tab="orders" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <p style={sec3}>Ordering for</p>
          <Card3 style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 44, height: 44, borderRadius: 10, background: "#995A001F", display: "flex", alignItems: "center", justifyContent: "center" }}><H3.Icon name="InventoryOutlined" size={24} color="#995A00" /></div>
            <div style={{ flex: 1 }}><div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>Krishna Stores</div><div style={{ fontSize: 13, color: "#666" }}>Yeshwanthpur · {LEVEL[level].label}</div></div>
          </Card3>
        </div>
        <div>
          <p style={sec3}>{isDealer ? "Supplying distribution partner" : "Manufacturer"}</p>
          <Card3 style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ width: 40, height: 40, borderRadius: 10, background: "#995A001F", color: "#995A00", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 14 }}>{isDealer ? "SD" : "AI"}</span>
            <div style={{ flex: 1 }}><div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>{isDealer ? "Shakti Distributors" : "Aashirvaad (ITC)"}</div><div style={{ fontSize: 13, color: "#666" }}>{isDealer ? "Aashirvaad (ITC) · Fortune · Tata Consumer" : "Credit ₹ 1,20,000 available"}</div></div>
          </Card3>
        </div>
        {!isDealer && (
          <div>
            <p style={sec3}>Source PO</p>
            <Card3 style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
              <H3.Icon name="InvoiceOutlined" size={24} color="#995A00" />
              <div style={{ flex: 1 }}><div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>PO-91204</div><div style={{ fontSize: 13, color: "#008000" }}>₹ 1,24,000 open</div></div>
              <a href="#" style={{ fontSize: 13, color: "#995A00", fontWeight: 700 }}>Change</a>
            </Card3>
          </div>
        )}
        {!isDealer && (
          <div>
            <p style={sec3}>Ship to</p>
            <H3.Select label="Ship-to partner" fullWidth value="self" onChange={() => {}} options={[{ value: "self", label: "Krishna Stores (self · own godown)" }, { value: "d1", label: "Gupta & Sons — dealer, Peenya" }, { value: "d2", label: "New Vaishnavi Mart — dealer, Peenya" }, { value: "d3", label: "Sri Balaji Agency — dealer, Yeshwanthpur" }]} />
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginTop: 8 }}>
              <H3.Icon name="InfoFilled" size={16} color="#8C8C8C" />
              <span style={{ fontSize: 12, color: "#8C8C8C", lineHeight: 1.45 }}>A distribution partner can have the manufacturer ship straight to one of its dealers.</span>
            </div>
          </div>
        )}
        <div>
          <p style={sec3}>Shipping address <span style={{ fontWeight: 600, textTransform: "none", letterSpacing: 0, color: "#8C8C8C" }}>· optional</span></p>
          <Card3 style={{ padding: 16, display: "flex", alignItems: "flex-start", gap: 12 }}>
            <H3.Icon name="LocationPin" size={22} color="#995A00" />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#333" }}>Registered address</div>
              <div style={{ fontSize: 13, color: "#666", lineHeight: 1.45 }}>#42, 3rd Cross, Yeshwanthpur Industrial Area, Bengaluru 560022</div>
            </div>
          </Card3>
          <H3.TextField placeholder="Add a different shipping address (optional)" multiline rows={2} value="" onChange={() => {}} style={{ marginTop: 10 }} />
        </div>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: isDealer ? "#0080000D" : "#FFF6E5", border: `1px solid ${isDealer ? "#B7E0B7" : "#FFD98A"}`, borderRadius: 10, padding: 12 }}>
          <H3.Icon name="InfoFilled" size={18} color={isDealer ? "#008000" : "#995A00"} />
          <span style={{ fontSize: 13, color: isDealer ? "#448044" : "#8A6D3B", lineHeight: 1.45 }}>{isDealer
            ? "Dealer outlet — a dealer buys only from its distribution partner. The order is created directly, no manager approval needed."
            : "Distribution-partner outlet — a DP buys direct from the manufacturer against an open PO. Goes to your manager for approval; the order is created within one hour of approval."}</span>
        </div>
      </div>
      <FooterBar><H3.Button variant="filled" color="primary" label="Add products" onClick={() => {}} style={{ width: "100%" }} /></FooterBar>
    </Screen3>
  );
}

/* ---------- S-ORD2 Product picker (cleaner add/stepper) ---------- */
const PRODUCTS = [
  { id: 1, cat: "Staples", name: "Aashirvaad Atta 10kg", pack: "1 bag", price: 545, stock: "In stock", qty: 4 },
  { id: 2, cat: "Staples", name: "Tata Salt 1kg", pack: "Pack of 24", price: 620, stock: "In stock", qty: 0 },
  { id: 3, cat: "Oils", name: "Fortune Sunflower Oil 5L", pack: "1 can", price: 1180, stock: "Low stock", qty: 2 },
  { id: 4, cat: "Home care", name: "Surf Excel 4kg", pack: "1 pack", price: 890, stock: "Out of stock", qty: 0 },
];
const stockTone = { "In stock": "#008000", "Low stock": "#FFBF40", "Out of stock": "#CC0000" };
function ProductPickerScreen() {
  const lines = PRODUCTS.filter((p) => p.qty > 0);
  const total = lines.reduce((s, p) => s + p.qty * p.price, 0);
  const cats = ["All", "Staples", "Oils", "Home care", "Beverages"];
  return (
    <Screen3 title="Add products" back tab="orders" noNav>
      <div style={{ padding: 12, background: "#fff", borderBottom: "1px solid #E5E5E5", display: "flex", flexDirection: "column", gap: 10 }}>
        <H3.TextField placeholder="Search products or scan" value="" onChange={() => {}} startAdornment={<H3.Icon name="SearchOutlined" size={20} color="#8C8C8C" />} />
        <div style={{ display: "flex", gap: 8, overflowX: "auto" }}>
          {cats.map((c, i) => (
            <span key={c} style={{ flexShrink: 0, padding: "6px 14px", borderRadius: 999, fontSize: 13, fontWeight: 600, cursor: "pointer", border: `1px solid ${i === 0 ? "#995A00" : "#D9D9D9"}`, color: i === 0 ? "#995A00" : "#666", background: i === 0 ? "#995A001F" : "#fff" }}>{c}</span>
          ))}
        </div>
      </div>
      <div style={{ background: "#fff" }}>
        {PRODUCTS.map((p, i) => {
          const out = p.stock === "Out of stock";
          return (
            <React.Fragment key={p.id}>
              {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
              <div style={{ display: "flex", gap: 12, padding: "12px 16px", alignItems: "center", opacity: out ? 0.6 : 1 }}>
                <div style={{ width: 48, height: 48, borderRadius: 10, background: "#F5F5F5", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><H3.Icon name="Image" size={22} color="#B0B0B0" /></div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "#333" }}>{p.name}</div>
                  <div style={{ fontSize: 13, color: "#666" }}>{p.pack} · <strong style={{ color: "#333" }}>₹ {p.price.toLocaleString("en-IN")}</strong></div>
                  <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, marginTop: 2, color: stockTone[p.stock] }}><span style={{ width: 7, height: 7, borderRadius: "50%", background: stockTone[p.stock] }} /> {p.stock}</div>
                </div>
                {out ? <span style={{ fontSize: 12, color: "#8C8C8C", fontWeight: 700 }}>Unavailable</span>
                  : p.qty > 0 ? <MiniStepper value={p.qty} onInc={() => {}} onDec={() => {}} />
                    : <button type="button" style={{ height: 34, padding: "0 16px", borderRadius: 8, border: "1px solid #995A00", background: "#fff", color: "#995A00", fontWeight: 700, fontSize: 14, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4 }}><H3.Icon name="Add" size={16} color="#995A00" /> Add</button>}
              </div>
            </React.Fragment>
          );
        })}
      </div>
      <FooterBar>
        <button type="button" style={{ width: "100%", height: 48, borderRadius: 8, border: "none", background: "#995A00", color: "#fff", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", fontFamily: "var(--font-family-base)" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700, fontSize: 14 }}><H3.Icon name="ShoppingCartOutlined" size={20} color="#fff" /> {lines.length} items</span>
          <span style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700, fontSize: 15 }}>₹ {total.toLocaleString("en-IN")} · View cart <H3.Icon name="KeyboardArrowRight" size={20} color="#fff" /></span>
        </button>
      </FooterBar>
    </Screen3>
  );
}

/* ---------- S-ORD3 Cart (cleaner line items) ---------- */
function CartScreen() {
  const lines = PRODUCTS.filter((p) => p.qty > 0);
  const sub = lines.reduce((s, p) => s + p.qty * p.price, 0);
  const scheme = 220;
  const gst = Math.round((sub - scheme) * 0.18);
  return (
    <Screen3 title="Cart" back tab="orders" noNav>
      <div style={{ padding: "12px 16px", fontSize: 13, color: "#666", background: "#fff", borderBottom: "1px solid #E5E5E5", display: "flex", alignItems: "center", gap: 6 }}>
        <H3.Icon name="InventoryOutlined" size={16} color="#8C8C8C" /> Krishna Stores · Aashirvaad (ITC)
      </div>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        {lines.map((p) => (
          <Card3 key={p.id} style={{ padding: 12 }}>
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              <div style={{ width: 44, height: 44, borderRadius: 8, background: "#F5F5F5", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><H3.Icon name="Image" size={20} color="#B0B0B0" /></div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: "#333" }}>{p.name}</div>
                <div style={{ fontSize: 13, color: "#666" }}>₹ {p.price.toLocaleString("en-IN")} · {p.pack}</div>
              </div>
              <button style={{ background: "none", border: "none", cursor: "pointer", padding: 2, display: "inline-flex" }}><H3.Icon name="Close" size={18} color="#8C8C8C" /></button>
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 10 }}>
              <MiniStepper value={p.qty} onInc={() => {}} onDec={() => {}} />
              <span style={{ fontSize: 16, fontWeight: 700, color: "#333", fontVariantNumeric: "tabular-nums" }}>₹ {(p.price * p.qty).toLocaleString("en-IN")}</span>
            </div>
          </Card3>
        ))}
        <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#0080000D", border: "1px solid #B7E0B7", borderRadius: 10, padding: 12 }}>
          <H3.Icon name="RewardsOutlined" size={20} color="#008000" /><span style={{ fontSize: 13, color: "#448044", fontWeight: 600 }}>Scheme applied: Atta 10kg — ₹ 220 off</span>
        </div>
        <Card3 style={{ padding: 16 }}>
          <Row label="Subtotal" value={`₹ ${sub.toLocaleString("en-IN")}`} />
          <Row label="Scheme discount" value={`− ₹ ${scheme}`} tone="#008000" />
          <Row label="GST (18%)" value={`₹ ${gst.toLocaleString("en-IN")}`} />
          <div style={{ borderTop: "1px solid #E5E5E5", marginTop: 8, paddingTop: 8 }}><Row label="Total" value={`₹ ${(sub - scheme + gst).toLocaleString("en-IN")}`} bold /></div>
        </Card3>
      </div>
      <FooterBar><H3.Button variant="filled" color="primary" label="Review order" onClick={() => {}} style={{ width: "100%" }} /></FooterBar>
    </Screen3>
  );
}
function Row({ label, value, bold, tone }) {
  return <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", fontSize: bold ? 16 : 14, fontWeight: bold ? 700 : 400, color: bold ? "#333" : "#666" }}><span>{label}</span><span style={{ color: tone || (bold ? "#995A00" : "#333"), fontVariantNumeric: "tabular-nums", fontWeight: bold ? 700 : 600 }}>{value}</span></div>;
}

/* ---------- S-ORD4 Order review & submit (conditional on outlet classification) ---------- */
function OrderReviewScreen({ level = "dp" }) {
  const isDealer = level === "dealer";
  const lines = PRODUCTS.filter((p) => p.qty > 0);
  const sub = lines.reduce((s, p) => s + p.qty * p.price, 0);
  const total = sub - 220 + Math.round((sub - 220) * 0.18);
  return (
    <Screen3 title="Review order" back tab="orders" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <H3.Stepper steps={[{ label: "Products" }, { label: "Review" }, { label: "Submitted" }]} activeStep={1} size="small" />
        <Card3 style={{ padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>{isDealer ? "Anand Distributors" : "Metro Wholesale"}</div>
              <div style={{ fontSize: 13, color: "#666", marginTop: 2 }}>{isDealer ? "DP order · Shakti Distributors" : "DP order from PO-91204 · Aashirvaad (ITC) → Shakti Distributors"}</div>
            </div>
            <H3.StatusBadge label={isDealer ? "Dealer" : "Distribution Partner"} color={isDealer ? "#0081F2" : "#995A00"} variant="soft" size="small" />
          </div>
        </Card3>
        <div>
          <p style={sec3}>{lines.length} line items</p>
          <Card3 style={{ padding: 0, overflow: "hidden" }}>
            {lines.map((p, i) => (
              <React.Fragment key={p.id}>
                {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
                <div style={{ display: "flex", justifyContent: "space-between", padding: "12px 16px", fontSize: 14 }}>
                  <span style={{ color: "#333" }}>{p.name} <span style={{ color: "#8C8C8C" }}>× {p.qty}</span></span>
                  <span style={{ color: "#333", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>₹ {(p.price * p.qty).toLocaleString("en-IN")}</span>
                </div>
              </React.Fragment>
            ))}
          </Card3>
        </div>
        <Card3 style={{ padding: 16 }}><Row label="Total (incl. GST, after scheme)" value={`₹ ${total.toLocaleString("en-IN")}`} bold /></Card3>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, background: isDealer ? "#0080000D" : "#FFF6E5", border: `1px solid ${isDealer ? "#B7E0B7" : "#FFD98A"}`, borderRadius: 10, padding: 12 }}>
          <H3.Icon name="InfoFilled" size={18} color={isDealer ? "#008000" : "#995A00"} />
          <span style={{ fontSize: 13, color: isDealer ? "#448044" : "#8A6D3B", lineHeight: 1.45 }}>{isDealer
            ? "Dealer outlet — submits straight to the distribution partner. No approval step."
            : "Goes to P. Nair (your manager) for approval. The DP order is created within one hour of approval."}</span>
        </div>
      </div>
      <FooterBar><H3.Button variant="filled" color="primary" label={isDealer ? "Submit DP order" : "Submit for approval"} onClick={() => {}} style={{ width: "100%" }} /></FooterBar>
    </Screen3>
  );
}

/* ---------- S-VISIT1 Visit outcome (reason tiles) ---------- */
function VisitOutcomeScreen() {
  const [reason, setReason] = useState3("closed");
  const REASONS = [
    ["closed", "Close", "Shop closed"],
    ["norequirement", "InventoryOutlined", "No requirement"],
    ["stockfull", "CheckCircle", "Stock full"],
    ["revisit", "Autorenew", "Revisit later"],
    ["credit", "CurrencyRupee", "Credit issue"],
    ["other", "Edit", "Other"],
  ];
  return (
    <Screen3 title="Log visit outcome" back tab="route" noNav bodyBg="#F5F5F5">
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        <Card3 style={{ padding: 14, display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 40, height: 40, borderRadius: 10, background: "#995A001F", display: "flex", alignItems: "center", justifyContent: "center" }}><H3.Icon name="InventoryOutlined" size={22} color="#995A00" /></div>
          <div style={{ flex: 1 }}><div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>Krishna Stores</div><div style={{ fontSize: 13, color: "#666" }}>No order this visit</div></div>
        </Card3>
        <div>
          <p style={sec3}>Select a reason</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {REASONS.map((r) => {
              const on = reason === r[0];
              return (
                <button key={r[0]} type="button" onClick={() => setReason(r[0])}
                  style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 8, padding: 14, borderRadius: 12, cursor: "pointer", background: on ? "#995A001F" : "#fff", border: `1.5px solid ${on ? "#995A00" : "#E5E5E5"}`, fontFamily: "var(--font-family-base)" }}>
                  <H3.Icon name={r[1]} size={22} color={on ? "#995A00" : "#8C8C8C"} />
                  <span style={{ fontSize: 14, fontWeight: 700, color: on ? "#995A00" : "#333" }}>{r[2]}</span>
                </button>
              );
            })}
          </div>
        </div>
        <div>
          <p style={sec3}>Add detail</p>
          <H3.TextField placeholder="Optional note" multiline rows={2} value="" onChange={() => {}} />
        </div>
      </div>
      <FooterBar><H3.Button variant="filled" color="primary" label="Mark visited — no order" onClick={() => {}} style={{ width: "100%" }} /></FooterBar>
    </Screen3>
  );
}

/* ---------- S-ORD6 My orders (summary + cards) ---------- */
const ORDERS = [
  ["PO-24817", "Krishna Stores", "Aashirvaad (ITC)", "₹ 5,540", "pending", "Pending", "15 Jul"],
  ["PO-24816", "Metro Wholesale", "Shakti Distributors", "₹ 84,000", "approved", "Approved", "15 Jul"],
  ["PO-24815", "Sri Balaji Agency", "Fortune (Adani)", "₹ 12,360", "partially-completed", "Edited", "14 Jul"],
  ["PO-24814", "Anand Distributors", "Tata Consumer", "₹ 46,200", "cancelled", "Rejected", "14 Jul"],
  ["PO-24810", "Gupta & Sons", "Aashirvaad (ITC)", "₹ 9,800", "not-verified", "PO failed", "13 Jul"],
];
function MyOrdersScreen({ variant = "list" }) {
  if (variant === "empty") return <Screen3 title="Orders" bell tab="orders"><H3.EmptyState icon="ShoppingCartOutlined" title="No orders yet" message="Start an order from an outlet visit on your route." actionLabel="Go to route" onAction={() => {}} /></Screen3>;
  return (
    <Screen3 title="Orders" bell tab="orders">
      <div style={{ display: "flex", gap: 10, padding: 16, background: "#fff", borderBottom: "1px solid #E5E5E5" }}>
        {[["7", "Pending", "#FFBF40"], ["28", "Approved", "#008000"], ["2", "Failed", "#CC0000"]].map((s) => (
          <div key={s[1]} style={{ flex: 1, border: "1px solid #E5E5E5", borderRadius: 10, padding: "10px 12px" }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: s[2] }}>{s[0]}</div>
            <div style={{ fontSize: 12, color: "#666" }}>{s[1]}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, padding: 12, overflowX: "auto", background: "#fff", borderBottom: "1px solid #E5E5E5" }}>
        {["All", "Pending", "Approved", "Rejected", "Failed"].map((c, i) => (
          <span key={c} style={{ flexShrink: 0, padding: "6px 14px", borderRadius: 999, fontSize: 13, fontWeight: 600, cursor: "pointer", border: `1px solid ${i === 0 ? "#995A00" : "#D9D9D9"}`, color: i === 0 ? "#995A00" : "#666", background: i === 0 ? "#995A001F" : "#fff" }}>{c}</span>
        ))}
      </div>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        {ORDERS.map((o) => (
          <Card3 key={o[0]} style={{ padding: 14, cursor: "pointer" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#333" }}>{o[1]}</div>
                <div style={{ fontSize: 12, color: "#8C8C8C", marginTop: 2 }}>{o[0]} · {o[2]}</div>
              </div>
              <H3.StatusChip status={o[4]} label={o[5]} type="outlined" />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginTop: 12 }}>
              <span style={{ fontSize: 12, color: "#8C8C8C" }}>{o[6]}</span>
              <span style={{ fontSize: 18, fontWeight: 700, color: "#333", fontVariantNumeric: "tabular-nums" }}>{o[3]}</span>
            </div>
          </Card3>
        ))}
      </div>
    </Screen3>
  );
}

/* ---------- S-ORD7 Order detail ---------- */
function OrderDetailScreen({ variant = "edited" }) {
  const failed = variant === "failed";
  const sla = variant === "sla";
  return (
    <Screen3 title={sla ? "PO-24817" : "PO-24810"} back tab="orders" noNav>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        {sla && (
          <div style={{ display: "flex", gap: 10, alignItems: "flex-start", background: "#FFF6E5", border: "1px solid #FFD98A", borderRadius: 10, padding: 12 }}>
            <H3.Icon name="Schedule" size={20} color="#995A00" />
            <div style={{ flex: 1 }}><div style={{ fontSize: 14, fontWeight: 700, color: "#663C00" }}>Approved · DP order being created</div><div style={{ fontSize: 13, color: "#8A6D3B", marginTop: 2 }}>Creation SLA is one hour from approval · <strong>38 min left</strong></div></div>
          </div>
        )}
        {failed && (
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start", background: "#CC00000D", border: "1px solid #F3B0B0", borderRadius: 8, padding: 12 }}>
            <H3.Icon name="Warning" size={20} color="#CC0000" />
            <div style={{ flex: 1 }}><div style={{ fontSize: 14, fontWeight: 700, color: "#CC0000" }}>PO/DP submission failed</div><div style={{ fontSize: 13, color: "#8A3B3B", marginTop: 2 }}>Approved in Humbee, but the downstream PO service rejected it (duplicate reference).</div></div>
          </div>
        )}
        <Card3 style={{ padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div><div style={{ fontSize: 16, fontWeight: 700, color: "#333" }}>{sla ? "Metro Wholesale" : "Gupta & Sons"}</div><div style={{ fontSize: 13, color: "#666" }}>{sla ? "DP order from PO-91204 · Aashirvaad (ITC)" : "PO · Aashirvaad (ITC)"} · 15 Jul</div></div>
            <H3.StatusChip status={failed ? "not-verified" : sla ? "approved" : "partially-completed"} label={failed ? "PO failed" : sla ? "Approved" : "Edited"} type="filled" />
          </div>
        </Card3>
        <div>
          <p style={sec3}>Status</p>
          <Card3 style={{ padding: 16 }}>
            <H3.ApprovalTimeline steps={failed ? [
              { label: "Submitted", time: "10:24 AM", state: "done" },
              { label: "Approved", time: "11:02 AM", state: "done" },
              { label: "PO/DP submission failed", detail: "Duplicate reference", time: "11:05 AM", state: "rejected" },
            ] : sla ? [
              { label: "Submitted", time: "10:24 AM", state: "done" },
              { label: "Approved by P. Nair", detail: "No edits", time: "11:02 AM", state: "done" },
              { label: "Creating DP order", detail: "Within one hour of approval", state: "current" },
            ] : [
              { label: "Submitted", time: "10:24 AM", state: "done" },
              { label: "Approved with edits", detail: "Manager reduced Atta 4→3", time: "11:02 AM", state: "edited" },
              { label: "Sent to PO/DP", time: "11:03 AM", state: "current" },
            ]} />
          </Card3>
        </div>
        {variant === "edited" && (
          <div>
            <p style={sec3}>What changed</p>
            <Card3 style={{ padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, color: "#333" }}><span>Aashirvaad Atta 10kg</span><span><s style={{ color: "#8C8C8C" }}>4</s> → <strong>3</strong></span></div>
            </Card3>
          </div>
        )}
      </div>
      <FooterBar>
        {failed
          ? <H3.Button variant="filled" color="primary" label="Retry submission" leftIcon={<H3.Icon name="Autorenew" size={20} color="#fff" />} onClick={() => {}} style={{ width: "100%" }} />
          : <H3.Button variant="outlined" color="neutral" label="Back to orders" onClick={() => {}} style={{ width: "100%" }} />}
      </FooterBar>
    </Screen3>
  );
}

/* ---------- S-AP3 My requests ---------- */
function MyRequestsScreen() {
  const reqs = [
    ["Beat: North BLR–West", "Beat plan · 24 outlets", "pending", "Pending"],
    ["Order PO-24816", "Metro Wholesale · ₹ 84,000", "approved", "Approved"],
    ["Leave: 22–23 Jul", "Casual leave", "cancelled", "Rejected"],
    ["Order PO-24815", "Sri Balaji · ₹ 12,360", "partially-completed", "Edited"],
  ];
  return (
    <Screen3 title="My requests" bell tab="more">
      <div style={{ background: "#fff" }}>
        {reqs.map((r, i) => (
          <React.Fragment key={i}>
            {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
            <H3.ListRow title={r[0]} subtitle={r[1]} trailing={<H3.StatusChip status={r[2]} label={r[3]} type="outlined" />} showChevron onClick={() => {}} />
          </React.Fragment>
        ))}
      </div>
    </Screen3>
  );
}

/* ---------- S-NOTIF Notifications ---------- */
function NotificationsScreen() {
  const items = [
    ["approved", "#008000", "CheckCircle", "Order PO-24816 approved", "Metro Wholesale · sent to PO/DP", "11:02 AM"],
    ["edited", "#0081F2", "Edit", "Order PO-24815 approved with edits", "1 line quantity was reduced", "10:40 AM"],
    ["rejected", "#CC0000", "Close", "Leave request rejected", "22–23 Jul · see comment", "Yesterday"],
    ["beat", "#995A00", "RewardsOutlined", "Beat 'North BLR–West' approved", "You can now plan its route", "Yesterday"],
  ];
  return (
    <Screen3 title="Notifications" back tab="more" noNav bodyBg="#fff">
      {items.map((n, i) => (
        <React.Fragment key={i}>
          {i > 0 && <div style={{ borderTop: "1px solid #F0F0F0" }} />}
          <div style={{ display: "flex", gap: 12, padding: 16, cursor: "pointer" }}>
            <div style={{ width: 36, height: 36, borderRadius: "50%", background: n[1] + "1A", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><H3.Icon name={n[2]} size={20} color={n[1]} /></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 600, color: "#333" }}>{n[3]}</div>
              <div style={{ fontSize: 13, color: "#666", marginTop: 2 }}>{n[4]}</div>
              <div style={{ fontSize: 12, color: "#8C8C8C", marginTop: 2 }}>{n[5]}</div>
            </div>
          </div>
        </React.Fragment>
      ))}
    </Screen3>
  );
}

Object.assign(window, { OutletVisitScreen, StartOrderScreen, ProductPickerScreen, CartScreen, OrderReviewScreen, VisitOutcomeScreen, MyOrdersScreen, OrderDetailScreen, MyRequestsScreen, NotificationsScreen });
