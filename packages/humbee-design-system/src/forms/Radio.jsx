import React from "react";

/* Humbee Radio + RadioGroup — ported from Radio/index.js.
   Unchecked ring #8C8C8C; checked #995A00 with filled dot. */
const SIZES = { small: 18, medium: 20, large: 24 };

export function Radio({ label, checked = false, disabled = false, error = false, size = "medium", value, onChange, name, style, ...rest }) {
  const box = SIZES[size] || 20;
  const color = error ? "var(--color-error)" : disabled ? "var(--color-text-disabled)" : checked ? "var(--color-primary)" : "var(--color-border)";
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-sm)", minHeight: 44, cursor: disabled ? "not-allowed" : "pointer", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      <input type="radio" checked={checked} disabled={disabled} value={value} name={name} onChange={onChange} style={{ position: "absolute", opacity: 0, width: 0, height: 0 }} {...rest} />
      <span style={{ width: box, height: box, borderRadius: "50%", border: `2px solid ${color}`, boxSizing: "border-box", display: "flex", alignItems: "center", justifyContent: "center", transition: "border-color var(--motion-duration-fast, 140ms) var(--motion-ease-standard, ease), box-shadow var(--motion-duration-fast, 140ms) var(--motion-ease-standard, ease)", boxShadow: checked && !disabled ? "0 0 0 3px color-mix(in srgb, var(--color-primary) 10%, transparent)" : "none", flexShrink: 0 }}>
        {checked && <span style={{ width: box * 0.5, height: box * 0.5, borderRadius: "50%", background: color }} />}
      </span>
      {label && <span style={{ fontSize: size === "small" ? "var(--text-body-sm-size)" : "var(--text-body-size)", lineHeight: size === "small" ? "var(--text-body-sm-line)" : "var(--text-body-line)", color: disabled ? "var(--color-text-placeholder)" : error ? "var(--color-error)" : "var(--color-text-primary)", fontWeight: 700, userSelect: "none" }}>{label}</span>}
    </label>
  );
}

export function RadioGroup({ label, options = [], value, onChange, name = "hb-radio", row = false, disabled = false, size = "medium", helperText, error = false, style }) {
  const norm = options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
  return (
    <div style={{ fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      {label && <div style={{ fontSize: "var(--text-label-sm-size)", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: "var(--space-sm)" }}>{label}</div>}
      <div style={{ display: "flex", flexDirection: row ? "row" : "column", gap: row ? "var(--space-md)" : "var(--space-xs)" }}>
        {norm.map((o) => (
          <Radio key={o.value} name={name} value={o.value} label={o.label} size={size}
            checked={value === o.value} disabled={disabled || o.disabled} error={error}
            onChange={() => onChange?.(o.value)} />
        ))}
      </div>
      {helperText && <div style={{ fontSize: "var(--text-caption-size)", color: error ? "var(--color-error)" : "var(--color-text-secondary)", marginTop: "var(--space-xs)" }}>{helperText}</div>}
    </div>
  );
}

export default Radio;
