import React, { useState } from "react";

/* Humbee Tabs — ported from Tab/CustomTab.js.
   Active label turns brown (#995A00); 'boxed' type adds a 12%-tint pill behind the active tab. */
export function Tabs({
  tabs = [],               // [{label, value}] or [string]
  value,
  onChange,
  variant = "primary",     // 'primary' | 'secondary'
  type = "boxed",          // 'boxed' | 'standard'
  size = "medium",
  style,
}) {
  const norm = tabs.map((t, i) => (typeof t === "string" ? { label: t, value: i } : t));
  const [internal, setInternal] = useState(norm[0]?.value);
  const active = value !== undefined ? value : internal;
  const small = size === "small";

  const select = (v) => { if (value === undefined) setInternal(v); onChange?.(v); };
  const selectedBg = variant === "secondary"
    ? "var(--hb-surface-raised, var(--surface-card))"
    : "var(--hb-surface-selected, var(--color-primary))";

  return (
    <div style={{ display: "flex", gap: "var(--space-xs)", borderBottom: type === "standard" ? "1px solid var(--color-neutral-300)" : "none", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      {norm.map((t) => {
        const on = t.value === active;
        return (
          <button key={t.value} type="button" onClick={() => select(t.value)}
            style={{
              borderTop: type === "boxed" && on ? "1px solid var(--color-primary)" : "1px solid transparent",
              borderRight: type === "boxed" && on ? "1px solid var(--color-primary)" : "1px solid transparent",
              borderBottom: type === "standard" ? `2px solid ${on ? "var(--color-primary)" : "transparent"}` : type === "boxed" && on ? "1px solid var(--color-primary)" : "1px solid transparent",
              borderLeft: type === "boxed" && on ? "1px solid var(--color-primary)" : "1px solid transparent",
              cursor: "pointer", fontWeight: 700,
              fontSize: small ? "var(--text-body-sm-size)" : "var(--text-body-size)", lineHeight: small ? "var(--text-body-sm-line)" : "var(--text-body-line)",
              padding: small ? "var(--space-xs) var(--space-md)" : "var(--space-sm) var(--space-lg)", minHeight: 44,
              borderRadius: type === "boxed" ? "var(--radius-md)" : 0, textTransform: "none",
              background: type === "boxed" && on ? selectedBg : "transparent",
              color: on ? (variant === "secondary" ? "var(--color-primary)" : "var(--color-text-inverse)") : "var(--color-text-primary)",
              boxShadow: type === "boxed" && on
                ? (variant === "secondary" ? "var(--hb-shadow-raised, 0 1px 2px rgb(0 0 0 / 8%))" : "var(--hb-shadow-selected, 0 4px 12px rgb(153 90 0 / 18%))")
                : "none",
              marginBottom: type === "standard" ? -1 : 0,
              transform: type === "boxed" && on ? "translateY(-1px)" : "translateY(0)",
              transition: "var(--hb-transition-interactive, background-color var(--motion-duration-standard, 200ms) ease, border-color var(--motion-duration-standard, 200ms) ease, box-shadow var(--motion-duration-standard, 200ms) ease, color var(--motion-duration-standard, 200ms) ease, transform var(--motion-duration-fast, 140ms) ease)",
            }}>
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

export default Tabs;
