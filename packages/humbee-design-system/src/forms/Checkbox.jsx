import React from "react";

/* Humbee Checkbox — ported from Checkbox/index.js.
   Unchecked border #8C8C8C; checked/indeterminate fill #995A00. Label 13/600 #333. */
const SIZES = { small: 18, medium: 20, large: 24 };

export function Checkbox({
  label,
  checked = false,
  indeterminate = false,
  disabled = false,
  error = false,
  size = "medium",
  onChange,
  labelPlacement = "end",   // 'end' | 'start'
  style,
  ...rest
}) {
  const box = SIZES[size] || 20;
  const on = checked || indeterminate;
  const color = error ? "var(--color-error)" : disabled ? "var(--color-text-disabled)" : "var(--color-primary)";
  const borderColor = on ? color : (error ? "var(--color-error)" : "var(--color-border)");

  const control = (
    <span style={{ position: "relative", width: box, height: box, flexShrink: 0, display: "inline-flex" }}>
      <span style={{
        width: box, height: box, borderRadius: 4, boxSizing: "border-box",
        border: `2px solid ${borderColor}`, background: on ? color : "var(--hb-surface-raised, var(--surface-card))",
        display: "flex", alignItems: "center", justifyContent: "center",
        boxShadow: on && !disabled ? "0 0 0 3px color-mix(in srgb, var(--color-primary) 10%, transparent)" : "none",
        transition: "background-color var(--motion-duration-fast, 140ms) var(--motion-ease-standard, ease), border-color var(--motion-duration-fast, 140ms) var(--motion-ease-standard, ease), box-shadow var(--motion-duration-fast, 140ms) var(--motion-ease-standard, ease)",
      }}>
        {indeterminate ? (
          <span style={{ width: box * 0.55, height: 2, background: "var(--color-text-inverse)", borderRadius: 1 }} />
        ) : checked ? (
          <svg width={box * 0.7} height={box * 0.7} viewBox="0 0 24 24" fill="none"><path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z" fill="var(--color-text-inverse)" /></svg>
        ) : null}
      </span>
    </span>
  );

  const text = label && (
    <span style={{ fontSize: "var(--text-body-sm-size)", lineHeight: "var(--text-body-sm-line)", color: disabled ? "var(--color-text-placeholder)" : error ? "var(--color-error)" : "var(--color-text-primary)", fontWeight: 700, userSelect: "none" }}>{label}</span>
  );

  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-sm)", minHeight: 44, cursor: disabled ? "not-allowed" : "pointer", fontFamily: "var(--font-family-base, Lato, sans-serif)", flexDirection: labelPlacement === "start" ? "row-reverse" : "row", ...style }}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={onChange} style={{ position: "absolute", opacity: 0, width: 0, height: 0 }} {...rest} />
      {control}{text}
    </label>
  );
}

export default Checkbox;
