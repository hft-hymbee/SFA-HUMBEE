import React from "react";

/* Humbee PaperElevation — ported from PaperElevation/index.js.
   The base card surface. Humbee leans on a hairline border with a very soft shadow. */
export function PaperElevation({
  children,
  padding = 16,
  radius = 8,
  bordered = true,
  elevation = "card",       // 'none' | 'card' | 'menu'
  style,
  ...rest
}) {
  const SHADOW = {
    none: "none",
    card: "0px 1px 3px rgba(0,0,0,0.08)",
    menu: "0px 2px 8px 0px rgba(0,0,0,0.10)",
  };
  return (
    <div style={{
      background: "#fff", borderRadius: radius, padding,
      border: bordered ? "1px solid #E5E5E5" : "none", boxShadow: SHADOW[elevation] || SHADOW.card,
      fontFamily: "var(--font-family-base, Lato, sans-serif)", boxSizing: "border-box", ...style,
    }} {...rest}>
      {children}
    </div>
  );
}

export default PaperElevation;
