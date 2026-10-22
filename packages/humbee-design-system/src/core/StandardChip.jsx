import React, { useState } from "react";
import { Icon } from "./Icon.jsx";

/* Humbee StandardChip — ported from chips/StandardChip.js.
   Selectable/toggleable chip. Active = brown outline + brown text; optional delete cross. */
export function StandardChip({
  label = "",
  selected,
  defaultSelected = false,
  showDelete = false,
  size = "medium",       // 'small' | 'medium'
  onChange,
  capitalise = true,
  style,
  ...rest
}) {
  const controlled = selected !== undefined;
  const [internal, setInternal] = useState(defaultSelected);
  const active = controlled ? selected : internal;
  const brown = "#995A00", gray = "#BDBDBD", black = "#333333";
  const small = size === "small";

  const toggle = () => { if (!controlled) setInternal((p) => !p); onChange?.(!active); };
  const text = capitalise ? label.replace(/\b\w/g, (m) => m.toUpperCase()) : label;

  return (
    <span
      onClick={toggle}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8,
        fontFamily: "var(--font-family-base, Lato, sans-serif)",
        color: active ? brown : black, backgroundColor: "transparent",
        outline: `1px solid ${active ? brown : gray}`, outlineOffset: "-1px",
        border: "none", borderRadius: 8, cursor: "pointer",
        height: small ? 28 : 32, padding: small ? "2px 8px" : "4px 12px",
        fontSize: small ? 11 : 13, lineHeight: "20px", fontWeight: 700,
        transition: "all 0.2s ease-in-out", userSelect: "none", ...style,
      }}
      {...rest}
    >
      {text}
      {active && showDelete && (
        <span onClick={(e) => { e.stopPropagation(); toggle(); }} style={{ display: "inline-flex" }}>
          <Icon name="Close" size={small ? 12 : 14} color={brown} />
        </span>
      )}
    </span>
  );
}

export default StandardChip;
