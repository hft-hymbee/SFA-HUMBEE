import React from "react";

/* Humbee Menu — ported from Menu/index.js.
   Rounded 8px panel, 1px #8C8C8C border, soft shadow. Selected item = brown text on #F7F7F7. */
export function Menu({ items = [], selectedValue = null, onSelect, width = 220, style }) {
  return (
    <div style={{
      width, borderRadius: 8, border: "1px solid #8C8C8C",
      boxShadow: "0px 2px 8px 0px rgba(0,0,0,0.10)", padding: 8, background: "#fff",
      fontFamily: "var(--font-family-base, Lato, sans-serif)", boxSizing: "border-box", ...style,
    }}>
      {items.map((item, i) => {
        const sel = selectedValue !== null && item.value === selectedValue;
        return (
          <div key={i} onClick={() => { item.onClick?.(); onSelect?.(item.value); }}
            style={{
              display: "flex", alignItems: "center", gap: 8, minHeight: 32,
              padding: "6px 8px", borderRadius: 8, cursor: "pointer",
              color: sel ? "#995A00" : "#333333", background: sel ? "#F7F7F7" : "transparent",
              fontSize: 14, transition: "background 0.12s",
            }}
            onMouseEnter={(e) => { if (!sel) e.currentTarget.style.background = "#f5f5f5"; }}
            onMouseLeave={(e) => { if (!sel) e.currentTarget.style.background = "transparent"; }}>
            {item.icon && <span style={{ display: "inline-flex", minWidth: 24, color: sel ? "#995A00" : "#333333" }}>{item.icon}</span>}
            <span style={{ padding: "0 4px" }}>{item.label}</span>
          </div>
        );
      })}
    </div>
  );
}

export default Menu;
