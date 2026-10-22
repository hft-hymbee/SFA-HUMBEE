import React from "react";

/* Humbee Gauge — semicircular achievement gauge for targets snapshots.
   value/max drive the sweep; brand amber fill on a neutral track. */
export function Gauge({ value = 0, max = 100, label, unit = "%", size = 160, color = "var(--color-primary)", style }) {
  const pct = Math.max(0, Math.min(1, max ? value / max : 0));
  const r = size / 2 - 10;
  const cx = size / 2, cy = size / 2;
  const circ = Math.PI * r;                 // half-circle length
  const dash = circ * pct;
  const display = unit === "%" ? Math.round(pct * 100) : value;
  return (
    <div style={{ width: size, textAlign: "center", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      <svg width={size} height={size / 2 + 12} viewBox={`0 0 ${size} ${size / 2 + 12}`}>
        <path d={`M10 ${cy} A ${r} ${r} 0 0 1 ${size - 10} ${cy}`} fill="none" stroke="color-mix(in srgb, var(--color-neutral-200) 74%, white)" strokeWidth={12} strokeLinecap="round" />
        <path d={`M10 ${cy} A ${r} ${r} 0 0 1 ${size - 10} ${cy}`} fill="none" stroke={color} strokeWidth={12} strokeLinecap="round" strokeDasharray={`${dash} ${circ}`} />
      </svg>
      <div style={{ marginTop: -size / 2 + 14, fontSize: "var(--text-h1-size)", fontWeight: 700, color: "var(--color-text-primary)", lineHeight: 1 }}>{display}{unit === "%" ? <span style={{ fontSize: "var(--text-body-size)" }}>%</span> : null}</div>
      {label && <div style={{ fontSize: "var(--text-body-sm-size)", color: "var(--color-text-secondary)", marginTop: 6 }}>{label}</div>}
    </div>
  );
}

export default Gauge;
