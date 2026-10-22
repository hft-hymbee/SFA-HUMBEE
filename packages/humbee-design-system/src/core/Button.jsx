import React, { useState } from "react";

/* Humbee CustomButton — ported from Button/CustomButton.js.
   Colour maps + sizing lifted verbatim; MUI replaced with a plain button. */
const COLORS = {
  primary:   { main: "var(--color-primary)", hover: "var(--color-primary-hover)", active: "var(--color-primary-active)", outlined: "color-mix(in srgb, var(--color-primary) 50%, transparent)", label: "var(--color-text-inverse)", hoverbg: "var(--color-primary-surface-hover)", activebg: "var(--color-primary-surface)" },
  secondary: { main: "var(--color-accent)", hover: "var(--color-accent-hover)", active: "var(--color-accent-active)", outlined: "var(--color-accent-hover)", label: "var(--color-text-inverse)", hoverbg: "var(--color-accent-surface)", activebg: "var(--color-accent-surface)" },
  error:     { main: "var(--color-error)", hover: "var(--color-error-hover)", active: "color-mix(in srgb, var(--color-error) 86%, black)", outlined: "var(--color-error)", label: "var(--color-text-inverse)", hoverbg: "var(--color-error-surface)", activebg: "var(--color-error-surface)" },
  success:   { main: "var(--color-success)", hover: "var(--color-success-hover)", active: "color-mix(in srgb, var(--color-success) 86%, black)", outlined: "var(--color-success)", label: "var(--color-text-inverse)", hoverbg: "var(--color-success-surface)", activebg: "var(--color-success-surface)" },
  neutral:   { main: "var(--color-neutral-400)", hover: "var(--color-neutral-300)", active: "var(--color-neutral-500)", outlined: "var(--color-primary)", label: "var(--color-text-primary)", textColor: "var(--color-text-primary)", hoverbg: "var(--color-primary-surface-hover)", activebg: "var(--color-primary-surface)" },
};

export function Button({
  variant = "filled",     // 'filled' | 'outlined' | 'text'
  color = "primary",      // primary | secondary | error | success | neutral
  label,
  children,
  size = "medium",        // 'small' | 'medium'
  disabled = false,
  loading = false,
  leftIcon,
  rightIcon,
  onClick,
  style,
  ...rest
}) {
  const [state, setState] = useState("default"); // default | hover | active
  const c = COLORS[color] || COLORS.primary;
  const isDisabled = disabled || loading;
  const small = size === "small";
  const raised = variant !== "text";
  const tone = color === "primary"
    ? {
        main: "color-mix(in srgb, var(--color-primary) 86%, white)",
        hover: "color-mix(in srgb, var(--color-primary-hover) 86%, white)",
        active: "color-mix(in srgb, var(--color-primary-active) 90%, white)",
      }
    : c;

  const base = {
    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "var(--space-sm)",
    fontFamily: "var(--font-family-base, Lato, sans-serif)", fontWeight: 700,
    fontSize: small ? "var(--text-body-sm-size)" : "var(--text-body-size)", lineHeight: small ? "var(--text-body-sm-line)" : "var(--text-body-line)",
    minHeight: 44, padding: small ? "var(--space-xs) var(--space-md)" : "var(--space-sm) var(--space-lg)",
    borderRadius: "var(--radius-md)", border: "1px solid transparent", textTransform: "none",
    cursor: isDisabled ? "not-allowed" : "pointer",
    transition: "var(--hb-transition-interactive, background-color var(--motion-duration-standard, 200ms) ease, border-color var(--motion-duration-standard, 200ms) ease, box-shadow var(--motion-duration-standard, 200ms) ease, color var(--motion-duration-standard, 200ms) ease, transform var(--motion-duration-fast, 140ms) ease)", boxSizing: "border-box", whiteSpace: "nowrap",
    transform: raised && state === "active" ? "translateY(1px)" : raised && state === "hover" ? "translateY(-1px)" : "translateY(0)",
  };

  let skin;
  if (isDisabled) {
    skin = { background: "var(--color-neutral-300)", color: "var(--color-text-placeholder)", border: variant === "outlined" ? "1px solid var(--color-neutral-400)" : "1px solid transparent", boxShadow: "none" };
  } else if (variant === "filled") {
    skin = {
      background: state === "active"
        ? tone.active
        : `linear-gradient(180deg, color-mix(in srgb, ${state === "hover" ? tone.hover : tone.main} 92%, white), ${state === "hover" ? tone.hover : tone.main})`,
      color: c.label,
      boxShadow: state === "active"
        ? "var(--hb-shadow-pressed, 0 1px 3px rgb(153 90 0 / 12%))"
        : "var(--hb-shadow-selected, inset 0 1px 0 rgb(255 255 255 / 34%), inset 0 -1px 0 rgb(0 0 0 / 12%), 0 4px 10px rgb(153 90 0 / 18%))",
    };
  } else if (variant === "outlined") {
    skin = {
      background: state === "active" ? c.activebg : state === "hover" ? c.hoverbg : "var(--hb-surface-raised, var(--surface-card))",
      border: `1px solid ${c.outlined}`,
      color: color === "neutral" ? c.outlined : c.main,
      boxShadow: state === "active"
        ? "var(--hb-shadow-pressed, 0 1px 3px rgb(153 90 0 / 12%))"
        : "var(--hb-shadow-raised, 0 1px 2px rgb(0 0 0 / 8%))",
    };
  } else { // text
    skin = { background: state === "active" ? c.activebg : state === "hover" ? c.hoverbg : "transparent", color: c.textColor || c.main, boxShadow: "none" };
  }

  const iconEl = (ic) => ic ? <span style={{ display: "inline-flex", width: 20, height: 20, alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{ic}</span> : null;

  return (
    <button
      type="button"
      disabled={isDisabled}
      onClick={isDisabled ? undefined : onClick}
      onMouseEnter={() => !isDisabled && setState("hover")}
      onMouseLeave={() => setState("default")}
      onMouseDown={() => !isDisabled && setState("active")}
      onMouseUp={() => !isDisabled && setState("hover")}
      style={{ ...base, ...skin, ...style }}
      {...rest}
    >
      {loading ? <Spinner /> : iconEl(leftIcon)}
      {loading ? "Loading..." : (label ?? children)}
      {!loading && iconEl(rightIcon)}
    </button>
  );
}

function Spinner() {
  return (
    <span style={{ width: 16, height: 16, display: "inline-block", border: "2px solid currentColor", borderTopColor: "transparent", borderRadius: "50%", animation: "hb-spin 0.7s linear infinite" }}>
      <style>{"@keyframes hb-spin{to{transform:rotate(360deg)}}"}</style>
    </span>
  );
}

export default Button;
