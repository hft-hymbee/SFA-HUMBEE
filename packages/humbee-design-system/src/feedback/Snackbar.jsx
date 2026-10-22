import React from "react";
import { Icon } from "../core/Icon.jsx";

/* Humbee Snackbar — ported from SnackBar/index.js.
   Dark #333 toast, 16px severity-coloured left border, message + optional action + close. */
const BORDERS = { success: "#008000", error: "#CC0000", warning: "#FFBF40" };

export function Snackbar({
  open = true,
  onClose,
  message,
  severity,               // 'success' | 'error' | 'warning'
  action,                 // { label, onClick }
  style,
}) {
  if (!open) return null;
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 8, minWidth: 300, maxWidth: 480,
      background: "#333333", color: "#fff", padding: "8px 16px", borderRadius: 4,
      borderLeft: severity ? `16px solid ${BORDERS[severity]}` : "none",
      boxShadow: "0px 2px 6px 1px rgba(0,0,0,0.15), 0px 1px 2px 0px rgba(0,0,0,0.30)",
      fontFamily: "var(--font-family-base, Lato, sans-serif)", fontSize: 14, ...style,
    }}>
      <span style={{ flex: 1 }}>{message}</span>
      {action && (
        <button type="button" onClick={action.onClick}
          style={{ background: "none", border: "none", color: "#FFA525", fontWeight: 700, fontSize: 14, cursor: "pointer", fontFamily: "inherit", padding: "0 4px" }}>
          {action.label}
        </button>
      )}
      {onClose && (
        <button type="button" onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", display: "inline-flex", padding: 0 }}>
          <Icon name="Close" size={18} color="#fff" />
        </button>
      )}
    </div>
  );
}

export default Snackbar;
