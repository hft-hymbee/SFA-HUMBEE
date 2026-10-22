import React, { useState } from "react";
import { Icon } from "./Icon.jsx";

/* Humbee IconButton — ported from IconButtons/CustomIconButton.js.
   Circular, transparent; colour shifts on hover. */
const COLOR_MAP = {
  primary:   { icon: "var(--color-primary)", hover: "var(--color-primary-hover)" },
  secondary: { icon: "var(--color-accent)", hover: "var(--color-accent-hover)" },
  error:     { icon: "var(--color-error)", hover: "var(--color-error-hover)" },
  success:   { icon: "var(--color-success)", hover: "var(--color-success-hover)" },
  info:      { icon: "var(--color-info)", hover: "var(--color-info-hover)" },
  warning:   { icon: "var(--color-warning)", hover: "var(--color-accent-hover)" },
  neutral:   { icon: "var(--color-text-primary)", hover: "var(--color-text-placeholder)" },
};

export function IconButton({
  iconName,
  icon,           // pass a custom node instead of iconName
  color = "primary",
  size = 24,
  disabled = false,
  onClick,
  style,
  ...rest
}) {
  const [state, setState] = useState("default");
  const set = COLOR_MAP[color] || COLOR_MAP.primary;
  const clr = disabled ? "var(--color-text-disabled)" : state === "default" ? set.icon : set.hover;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => !disabled && setState("hover")}
      onMouseLeave={() => setState("default")}
      onMouseDown={() => !disabled && setState("active")}
      onMouseUp={() => !disabled && setState("hover")}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 44, height: 44, padding: 0, borderRadius: "var(--radius-pill)", border: "1px solid transparent",
        background: disabled ? "transparent" : state === "default" ? "transparent" : "var(--hb-surface-raised-hover, var(--color-primary-surface-hover))",
        boxShadow: disabled || state === "default" ? "none" : state === "active" ? "var(--hb-shadow-pressed)" : "var(--hb-shadow-raised)",
        color: clr, cursor: disabled ? "not-allowed" : "pointer",
        transform: state === "active" ? "translateY(1px)" : "translateY(0)",
        transition: "var(--hb-transition-interactive, background-color var(--motion-duration-standard, 200ms) ease, box-shadow var(--motion-duration-standard, 200ms) ease, color var(--motion-duration-standard, 200ms) ease, transform var(--motion-duration-fast, 140ms) ease)", ...style,
      }}
      {...rest}
    >
      {icon ? icon : <Icon name={iconName} size={size} color="currentColor" />}
    </button>
  );
}

export default IconButton;
