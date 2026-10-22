import React from "react";
import { createPortal } from "react-dom";
import { Icon } from "../core/Icon.jsx";

/* Humbee mobile overlays — FAB and BottomSheet. */

/* FAB — floating action button, bottom-right, sits above the BottomNav. */
export function FAB({ iconName = "Add", label, onClick, color = "#995A00", style }) {
  const extended = !!label;
  const background = color === "#995A00"
    ? "var(--hb-surface-selected, linear-gradient(180deg, color-mix(in srgb, #995A00 86%, white), color-mix(in srgb, #995A00 94%, white)))"
    : color;
  return (
    <button type="button" onClick={onClick}
      style={{
        position: "absolute", right: 16, bottom: 76, height: 56, minWidth: 56,
        padding: extended ? "0 var(--space-lg) 0 var(--space-md)" : 0, borderRadius: "var(--radius-pill)", border: "1px solid color-mix(in srgb, white 18%, transparent)",
        background, color: "var(--color-text-inverse)", cursor: "pointer", display: "inline-flex",
        alignItems: "center", justifyContent: "center", gap: "var(--space-sm)",
        boxShadow: "var(--hb-shadow-selected, inset 0 1px 0 rgb(255 255 255 / 34%), inset 0 -1px 0 rgb(0 0 0 / 12%), 0 4px 10px rgb(153 90 0 / 18%))", fontFamily: "var(--font-family-base, Lato, sans-serif)",
        fontSize: "var(--text-body-size)", fontWeight: 700, zIndex: 20,
        transition: "var(--hb-transition-interactive, box-shadow var(--motion-duration-standard, 200ms) ease, transform var(--motion-duration-fast, 140ms) ease)",
        ...style,
      }}>
      <Icon name={iconName} size={24} color="var(--color-text-inverse)" />
      {extended && <span>{label}</span>}
    </button>
  );
}

/* BottomSheet — modal sheet sliding from the bottom; grabber + optional title + content. */
export function BottomSheet({ open, onClose, title, children, style }) {
  if (!open) return null;

  const sheet = (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "var(--surface-overlay)", display: "flex", alignItems: "flex-end", zIndex: 1000, fontFamily: "var(--font-family-base, Lato, sans-serif)" }}>
      <div className="sp-enter" onClick={(e) => e.stopPropagation()} style={{ width: "100%", background: "var(--surface-card-warm, var(--surface-card))", border: "1px solid color-mix(in srgb, var(--color-primary) 14%, var(--color-neutral-300))", borderBottom: 0, borderRadius: "var(--radius-lg) var(--radius-lg) 0 0", padding: "var(--space-sm) var(--space-md) calc(var(--space-lg) + env(safe-area-inset-bottom, 0px))", maxHeight: "85dvh", overflowY: "auto", boxSizing: "border-box", boxShadow: "var(--shadow-modal)", ...style }}>
        <div style={{ width: 36, height: 4, borderRadius: 2, background: "var(--color-neutral-400)", margin: "6px auto 12px" }} />
        {title && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <h3 className="hb-heading" style={{ margin: 0, fontSize: 18, color: "var(--color-text-primary)" }}>{title}</h3>
            {onClose && <button type="button" onClick={onClose} style={{ background: "var(--hb-surface-raised, var(--surface-card))", border: "1px solid var(--color-neutral-300)", borderRadius: "var(--radius-pill)", cursor: "pointer", padding: 0, width: 44, height: 44, display: "inline-flex", alignItems: "center", justifyContent: "center", boxShadow: "var(--hb-shadow-raised)" }}><Icon name="Close" size={22} color="var(--color-text-secondary)" /></button>}
          </div>
        )}
        {children}
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(sheet, document.body);
}

export const Overlays = FAB;
export default FAB;
