import React from "react";
import { Icon, IconSurface } from "../core/Icon.jsx";

/* Humbee StatCard — compact metric card for the SP dashboard & targets.
   Icon chip · label · value · optional delta (colored) · optional drill chevron. */
export function StatCard({
  icon = "Dashboard",
  iconColor = "var(--color-primary)",
  label,
  value,
  sub,
  delta,                  // e.g. "+12%" or "-3"
  deltaTone = "up",       // 'up' | 'down' | 'flat'
  onClick,
  style,
}) {
  const dColor = deltaTone === "up" ? "var(--color-success)" : deltaTone === "down" ? "var(--color-error)" : "var(--color-text-placeholder)";
  const clickable = !!onClick;
  return (
    <div onClick={onClick} style={{
      background: "var(--hb-surface-raised, var(--surface-card))", border: "1px solid var(--color-neutral-300)", borderRadius: "var(--radius-md)", padding: "var(--space-md)",
      boxShadow: "var(--hb-shadow-raised)",
      display: "flex", flexDirection: "column", gap: 8, cursor: clickable ? "pointer" : "default",
      fontFamily: "var(--font-family-base, Lato, sans-serif)", minWidth: 0, boxSizing: "border-box",
      transition: clickable ? "var(--hb-transition-interactive, border-color var(--motion-duration-standard, 200ms) ease, box-shadow var(--motion-duration-standard, 200ms) ease, transform var(--motion-duration-fast, 140ms) ease)" : undefined,
      ...style,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <IconSurface name={icon} size="metric" shape="soft-square" tone="primary" color={iconColor} />
        {clickable && <Icon name="KeyboardArrowRight" size={20} color="var(--color-text-placeholder)" />}
      </div>
      <div>
        <div style={{ fontSize: "var(--text-body-sm-size)", color: "var(--color-text-secondary)", lineHeight: "var(--text-body-sm-line)" }}>{label}</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 2 }}>
          <span style={{ fontSize: "var(--text-h2-size)", fontWeight: 700, color: "var(--color-text-primary)", lineHeight: 1.1 }}>{value}</span>
          {delta && <span style={{ fontSize: "var(--text-body-sm-size)", fontWeight: 700, color: dColor }}>{delta}</span>}
        </div>
        {sub && <div style={{ fontSize: "var(--text-caption-size)", color: "var(--color-text-secondary)", marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  );
}

export default StatCard;
