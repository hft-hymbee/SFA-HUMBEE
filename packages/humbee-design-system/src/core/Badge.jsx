import React from "react";

/* Humbee Badge — ported from Badge/index.js.
   Absolutely-positioned corner badge for cards/list items. Parent must be position:relative. */
const STYLES = {
  card:    { background: "#CC00001F", border: "1px solid #c62828", borderRadius: 8, padding: "4px 8px", color: "#333" },
  list:    { background: "#CC00001F", border: "1px solid #CC0000", borderRadius: "0 0 8px 8px", padding: "4px 8px", color: "#333" },
  default: { background: "#e0e0e0", borderRadius: 8, padding: "2px 8px", color: "#333" },
};

export function Badge({
  badgeText = "",
  badgeType = "default",   // 'card' | 'list' | 'default'
  badgePosition = { top: 0, right: 0 },
  badgeSize = "small",
  style,
}) {
  if (!badgeText) return null;
  return (
    <span style={{
      position: "absolute", top: badgePosition.top, right: badgePosition.right, zIndex: 1,
      fontWeight: 700, fontSize: badgeSize === "small" ? "0.8rem" : "1rem",
      fontFamily: "var(--font-family-base, Lato, sans-serif)", ...STYLES[badgeType], ...style,
    }}>
      {badgeText}
    </span>
  );
}

export default Badge;
