import React from "react";

/* Humbee StatusBadge — ported from Badge/StatusBadge.js.
   A soft/outlined/filled label pill. Colour is explicit (color) or derived from the label text. */
const PATTERNS = [
  { c: "#CC0000", words: ["danger","error","failed","rejected","denied","cancelled","canceled","inactive","disabled","blocked","expired","overdue","notverified","not_verified","unverified","invalid","returned","reject"] },
  { c: "#FFBF40", words: ["pending","inprogress","progress","waiting","scheduled","processing","review"] },
  { c: "#995A00", words: ["announced","new","approved"] },
  { c: "#0081F2", words: ["info","information","updated","available","featured","notice","partially","beta","preview","draft","staging"] },
  { c: "#008000", words: ["active","completed","done","finished","success","verified","confirmed","published","live","online","paid","delivered","shipped","fulfilled","accepted"] },
];

function deriveColor(label = "") {
  const n = String(label).toLowerCase().replace(/\s+/g, "");
  for (const p of PATTERNS) if (p.words.some((w) => n.includes(w))) return p.c;
  return "#8C8C8C";
}
function hexA(hex, a) {
  const h = hex.replace("#", "");
  return `rgba(${parseInt(h.slice(0,2),16)},${parseInt(h.slice(2,4),16)},${parseInt(h.slice(4,6),16)},${a})`;
}

const SIZE = {
  small:  { fontSize: 11, lineHeight: "20px", height: 24, pad: "2px 8px" },
  medium: { fontSize: 13, lineHeight: "24px", height: 28, pad: "4px 12px" },
  large:  { fontSize: 16, lineHeight: "24px", height: 32, pad: "4px 12px" },
};

export function StatusBadge({
  label = "",
  status,
  color,                 // explicit hex overrides derivation
  variant = "soft",      // 'soft' | 'outlined' | 'filled' | 'text'
  size = "small",
  style,
  ...rest
}) {
  const c = color || deriveColor(label || status);
  const sz = SIZE[size] || SIZE.medium;
  let skin;
  if (variant === "filled")   skin = { backgroundColor: c, color: "#fff", outline: `1px solid ${c}`, outlineOffset: "-1px" };
  else if (variant === "outlined") skin = { backgroundColor: hexA(c, 0.12), color: "#333333", outline: `1px solid ${c}`, outlineOffset: "-1px" };
  else if (variant === "text") skin = { backgroundColor: "transparent", color: c };
  else skin = { backgroundColor: hexA(c, 0.12), color: c };  // soft

  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        fontFamily: "var(--font-family-base, Lato, sans-serif)", fontWeight: 700,
        fontSize: sz.fontSize, lineHeight: sz.lineHeight, height: sz.height,
        padding: sz.pad, borderRadius: 16, whiteSpace: "nowrap", ...skin, ...style,
      }}
      {...rest}
    >
      {(label || status || "").replace(/_/g, " ")}
    </span>
  );
}

export default StatusBadge;
