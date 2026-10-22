import React, { useState } from "react";

/* Humbee Tooltip — ported from Tooltip/index.js.
   Hover-triggered bubble with arrow. Variants: 'neutral' (#8C8C8C) | 'main' (#995A00). */
const COLORS = { neutral: "#8C8C8C", main: "#995A00" };
const SIZES = {
  small:  { fontSize: "var(--text-overline-size)", lineHeight: "var(--text-overline-line)", padding: "4px 8px", radius: "var(--radius-sm)" },
  medium: { fontSize: "var(--text-body-sm-size)", lineHeight: "var(--text-body-sm-line)", padding: "8px 12px", radius: "var(--radius-sm)" },
  large:  { fontSize: "var(--text-body-size)", lineHeight: "var(--text-body-line)", padding: "12px 16px", radius: "var(--radius-md)" },
};
const POS = {
  top:    { bottom: "100%", left: "50%", transform: "translateX(-50%)", mb: 6 },
  bottom: { top: "100%", left: "50%", transform: "translateX(-50%)", mt: 6 },
  left:   { right: "100%", top: "50%", transform: "translateY(-50%)", mr: 6 },
  right:  { left: "100%", top: "50%", transform: "translateY(-50%)", ml: 6 },
};

export function Tooltip({ children, title, variant = "neutral", size = "small", placement = "bottom", style }) {
  const [show, setShow] = useState(false);
  const bg = COLORS[variant] || COLORS.neutral;
  const sz = SIZES[size] || SIZES.small;
  const p = POS[placement] || POS.bottom;
  if (!title) return children;

  return (
    <span style={{ position: "relative", display: "inline-flex" }}
      onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span style={{
          position: "absolute", zIndex: 50, whiteSpace: "nowrap",
          top: p.top, bottom: p.bottom, left: p.left, right: p.right, transform: p.transform,
          marginTop: p.mt, marginBottom: p.mb, marginLeft: p.ml, marginRight: p.mr,
          background: bg, color: "#fff", border: `1px solid ${bg}`,
          fontSize: sz.fontSize, lineHeight: sz.lineHeight, padding: sz.padding, borderRadius: sz.radius,
          fontFamily: "var(--font-family-base, Lato, sans-serif)", pointerEvents: "none", ...style,
        }}>
          {title}
        </span>
      )}
    </span>
  );
}

export default Tooltip;
