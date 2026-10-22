import React from "react";
import { Icon } from "../core/Icon.jsx";

/* Humbee ListRow — the workhorse tappable row for mobile lists (outlets, orders, requests, menu items).
   Leading icon/avatar · title + subtitle · trailing (chip, chevron, or custom). Min height 56 for touch. */
export function ListRow({
  leading,                // node (icon, avatar, index badge)
  title,
  subtitle,
  meta,                   // small right-aligned text above trailing
  trailing,               // node (StatusChip, chevron, button)
  onClick,
  disabled = false,
  showChevron = false,
  style,
}) {
  const clickable = !!onClick && !disabled;
  return (
    <div
      className={clickable ? "hb-list-row hb-list-row--press" : "hb-list-row"}
      onClick={clickable ? onClick : undefined}
      style={{
        display: "flex", alignItems: "center", gap: "var(--space-sm)", minHeight: 56, padding: "var(--space-sm) var(--space-md)",
        background: clickable ? "var(--hb-surface-raised, var(--surface-card))" : "var(--surface-card)", borderRadius: clickable ? "var(--radius-sm)" : 0, cursor: clickable ? "pointer" : "default", opacity: disabled ? 0.55 : 1,
        boxShadow: clickable ? "var(--hb-shadow-raised, 0 1px 2px rgb(0 0 0 / 8%))" : "none",
        fontFamily: "var(--font-family-base, Lato, sans-serif)", boxSizing: "border-box", transition: "var(--hb-transition-interactive, background-color var(--motion-duration-standard, 200ms) ease, box-shadow var(--motion-duration-standard, 200ms) ease, transform var(--motion-duration-fast, 140ms) ease)", ...style,
      }}
    >
      {leading && <div style={{ flexShrink: 0, display: "flex", alignItems: "center" }}>{leading}</div>}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="hb-heading" title={typeof title === "string" ? title : undefined} style={{ color: "var(--color-text-primary)", fontSize: "var(--text-list-title-size)", fontWeight: "var(--text-list-title-weight)", lineHeight: "var(--text-list-title-line)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{title}</div>
        {subtitle && <div style={{ color: "var(--color-text-secondary)", fontSize: "var(--text-list-subtitle-size)", fontWeight: "var(--text-list-subtitle-weight)", lineHeight: "var(--text-list-subtitle-line)", marginTop: 2, overflowWrap: "anywhere" }}>{subtitle}</div>}
      </div>
      {(meta || trailing || showChevron) && (
        <div style={{ flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
          {meta && <span style={{ color: "var(--color-text-secondary)", fontSize: "var(--text-list-meta-size)", fontWeight: "var(--text-list-meta-weight)", lineHeight: "var(--text-list-meta-line)" }}>{meta}</span>}
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            {trailing}
            {showChevron && <Icon name="KeyboardArrowRight" size={22} color="var(--color-text-placeholder)" />}
          </div>
        </div>
      )}
    </div>
  );
}

export default ListRow;
