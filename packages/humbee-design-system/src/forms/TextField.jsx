import React, { useState } from "react";

/* Humbee TextField — ported from TextField/index.js.
   Label sits above the field (static, 13/700 #666). Outlined + standard variants. */
export function TextField({
  label,
  helperText,
  placeholder,
  value,
  onChange,
  variant = "outlined",   // 'outlined' | 'standard'
  multiline = false,
  rows = 4,
  error = false,
  disabled = false,
  required = false,
  startAdornment,
  endAdornment,
  fullWidth = true,
  style,
  inputProps,
  ...props
}) {
  const [focus, setFocus] = useState(false);
  const border = error ? "var(--color-error)" : focus ? "var(--color-primary)" : "var(--color-border)";

  const fieldBase = {
    display: "flex", alignItems: "center", gap: "var(--space-sm)",
    fontFamily: "var(--font-family-base, Lato, sans-serif)",
    fontSize: "var(--text-body-size)", fontWeight: 400, lineHeight: "var(--text-body-line)", color: "var(--color-text-primary)",
    padding: "var(--space-sm)", minHeight: multiline ? 88 : 44, boxSizing: "border-box",
    background: disabled ? "var(--surface-muted)" : "var(--hb-surface-raised, var(--surface-card))",
    boxShadow: focus && !disabled ? "0 0 0 3px color-mix(in srgb, var(--color-primary) 10%, transparent)" : "var(--hb-shadow-raised, none)",
    transition: "var(--hb-transition-interactive, border-color var(--motion-duration-standard, 200ms) ease, box-shadow var(--motion-duration-standard, 200ms) ease, background-color var(--motion-duration-standard, 200ms) ease)",
  };
  const variantStyle = variant === "standard"
    ? { border: "none", borderBottom: `1px solid ${border}`, borderRadius: 0, padding: "2px 0" }
    : { border: `1px solid ${border}`, borderRadius: "var(--radius-md)" };

  const inputReset = {
    border: "none", outline: "none", background: "transparent", flex: 1,
    font: "inherit", color: "inherit", padding: 0, resize: "none", width: "100%",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2xs, 2px)", width: fullWidth ? "100%" : "auto", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      {label && (
        <label style={{ color: error ? "var(--color-error)" : "var(--color-text-secondary)", fontSize: "var(--text-label-sm-size)", lineHeight: "var(--text-label-sm-line)", fontWeight: 700 }}>
          {label}{required ? "*" : ""}
        </label>
      )}
      <div style={{ ...fieldBase, ...variantStyle }}>
        {startAdornment}
        {multiline ? (
          <textarea rows={rows} placeholder={placeholder} value={value} onChange={onChange} disabled={disabled}
            onFocus={() => setFocus(true)} onBlur={() => setFocus(false)} style={inputReset} {...inputProps} {...props} />
        ) : (
          <input placeholder={placeholder} value={value} onChange={onChange} disabled={disabled}
            onFocus={() => setFocus(true)} onBlur={() => setFocus(false)} style={inputReset} {...inputProps} {...props} />
        )}
        {endAdornment}
      </div>
      {helperText && (
        <span style={{ fontSize: "var(--text-caption-size)", lineHeight: "var(--text-caption-line)", color: error ? "var(--color-error)" : "var(--color-text-secondary)", marginTop: 2 }}>{helperText}</span>
      )}
    </div>
  );
}

export default TextField;
