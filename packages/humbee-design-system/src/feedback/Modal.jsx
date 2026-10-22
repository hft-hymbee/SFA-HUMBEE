import React from "react";
import { Icon } from "../core/Icon.jsx";

/* Humbee Modal — ported from Modal/CustomModal.js.
   Centred white panel, 16px radius, sticky header with title + close, optional subtitle. */
export function Modal({
  open,
  onClose,
  title = "",
  subtitle = "",
  children,
  maxWidth = 600,
  showHeader = true,
  style,
}) {
  if (!open) return null;
  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, fontFamily: "var(--font-family-base, Lato, sans-serif)" }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ background: "#fff", borderRadius: 16, width: "100%", maxWidth, maxHeight: "80vh", display: "flex", flexDirection: "column", boxShadow: "0px 11px 15px -7px rgba(0,0,0,0.2),0px 24px 38px 3px rgba(0,0,0,0.14),0px 9px 46px 8px rgba(0,0,0,0.12)", margin: 16, ...style }}
      >
        {showHeader && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: 16, borderBottom: "1px solid #D9D9D9", borderRadius: "16px 16px 0 0" }}>
            <span className="hb-heading" style={{ fontSize: 24, lineHeight: "40px", color: "#333333" }}>{title}</span>
            {onClose && (
              <button type="button" onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", display: "inline-flex", padding: 0 }}>
                <Icon name="Close" size={20} color="#333333" />
              </button>
            )}
          </div>
        )}
        {subtitle && <div style={{ padding: "8px 16px 0", fontSize: 16, color: "#333333" }}>{subtitle}</div>}
        <div style={{ padding: 16, overflowY: "auto", flex: 1 }}>{children}</div>
      </div>
    </div>
  );
}

export default Modal;
