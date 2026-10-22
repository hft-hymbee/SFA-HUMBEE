import React, { useState } from "react";

/* Humbee DatePicker — single-date field aligned with TextField/Select styles.
   Uses native date input semantics so consumers get keyboard/mobile pickers by default. */
export function DatePicker({
  label,
  helperText,
  value,
  defaultValue,
  onChange,
  minDate,
  maxDate,
  placeholder,
  id,
  name,
  required = false,
  disabled = false,
  error = false,
  fullWidth = true,
  style,
  ...props
}) {
  const [focus, setFocus] = useState(false);
  const border = error ? "var(--color-error)" : focus ? "var(--color-primary)" : "var(--color-border)";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-2xs, 2px)",
        width: fullWidth ? "100%" : "auto",
        fontFamily: "var(--font-family-base, Lato, sans-serif)",
        ...style,
      }}
    >
      {label && (
        <label htmlFor={id} style={{ color: error ? "var(--color-error)" : "var(--color-text-secondary)", fontSize: "var(--text-label-sm-size)", lineHeight: "var(--text-label-sm-line)", fontWeight: 700 }}>
          {label}
          {required ? "*" : ""}
        </label>
      )}
      <input
        id={id}
        name={name}
        type="date"
        value={value}
        defaultValue={defaultValue}
        onChange={onChange}
        min={minDate}
        max={maxDate}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        onFocus={() => setFocus(true)}
        onBlur={() => setFocus(false)}
        style={{
          minHeight: 44,
          display: "block",
          width: "100%",
          boxSizing: "border-box",
          padding: "8px 12px",
          border: `1px solid ${border}`,
          borderRadius: "var(--radius-md)",
          fontFamily: "inherit",
          fontSize: "var(--text-body-size)",
          fontWeight: 400,
          lineHeight: "var(--text-body-line)",
          color: "var(--color-text-primary)",
          background: disabled ? "var(--surface-muted)" : "var(--hb-surface-raised, var(--surface-card))",
          boxShadow: focus && !disabled ? "0 0 0 3px color-mix(in srgb, var(--color-primary) 10%, transparent)" : "var(--hb-shadow-raised, none)",
          outline: "none",
          transition: "var(--hb-transition-interactive, border-color var(--motion-duration-standard, 200ms) ease, box-shadow var(--motion-duration-standard, 200ms) ease, background-color var(--motion-duration-standard, 200ms) ease)",
        }}
        {...props}
      />
      {helperText && (
        <span style={{ fontSize: "var(--text-caption-size)", lineHeight: "var(--text-caption-line)", color: error ? "var(--color-error)" : "var(--color-text-secondary)", marginTop: 2 }}>
          {helperText}
        </span>
      )}
    </div>
  );
}

export default DatePicker;
