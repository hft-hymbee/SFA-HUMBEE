import React from "react";

/* Humbee ToggleSwitch — ported from ToggleSwitch/index.js.
   Track neutral #D9D9D9 → green #008000 when on. Label sits at the start (space-between). */
const SIZES = {
  small:  { w: 34, h: 20, thumb: 16, pad: 2, travel: 14 },
  medium: { w: 42, h: 26, thumb: 22, pad: 2, travel: 16 },
  large:  { w: 54, h: 32, thumb: 24, pad: 4, travel: 22 },
};

export function ToggleSwitch({
  checked = false,
  onChange,
  label,
  disabled = false,
  size = "large",
  error = false,
  style,
  ...rest
}) {
  const s = SIZES[size] || SIZES.large;
  const trackColor = disabled ? "var(--color-neutral-300)" : checked ? (error ? "var(--color-error)" : "var(--color-success)") : "var(--color-neutral-300)";

  const sw = (
    <span
      role="switch"
      aria-checked={checked}
      onClick={() => !disabled && onChange?.({ target: { checked: !checked } })}
      style={{
        width: s.w, height: s.h, borderRadius: "var(--radius-pill)", background: trackColor,
        position: "relative", flexShrink: 0, cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.7 : 1,
        boxShadow: checked && !disabled ? "var(--shadow-depth-soft, 0 3px 8px rgb(0 128 0 / 14%))" : "inset 0 1px 2px color-mix(in srgb, var(--color-text-primary) 12%, transparent)",
        transition: "background-color var(--motion-duration-standard, 200ms) var(--motion-ease-standard, ease), box-shadow var(--motion-duration-standard, 200ms) var(--motion-ease-standard, ease)",
        display: "inline-block",
      }}
      {...rest}
    >
      <span style={{
        position: "absolute", top: s.pad, left: checked ? s.pad + s.travel : s.pad,
        width: s.thumb, height: s.thumb, borderRadius: "50%",
        background: disabled ? "var(--color-neutral-200)" : "var(--surface-card)",
        boxShadow: disabled ? "none" : "var(--hb-shadow-raised, 0 1px 3px rgba(0,0,0,0.18))",
        transition: "left var(--motion-duration-standard, 200ms) var(--motion-ease-emphasized, ease), box-shadow var(--motion-duration-standard, 200ms) var(--motion-ease-standard, ease)",
      }} />
    </span>
  );

  if (!label) return sw;
  return (
    <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", gap: "var(--space-md)", minHeight: 44, cursor: disabled ? "not-allowed" : "pointer", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      <span style={{ fontSize: "var(--text-body-size)", lineHeight: "var(--text-body-line)", fontWeight: 700, color: disabled ? "var(--color-text-placeholder)" : "var(--color-text-primary)", userSelect: "none" }}>{label}</span>
      {sw}
    </label>
  );
}

export default ToggleSwitch;
