import React, { useState } from "react";
import { Icon } from "../core/Icon.jsx";

/* Humbee InlineEditField — ported from InlineEditField/index.js.
   View mode shows label + value + pencil; edit mode swaps to an input with confirm/cancel. */
export function InlineEditField({ label, value = "", onSave, style }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const start = () => { setDraft(value); setEditing(true); };
  const confirm = () => { onSave?.(draft); setEditing(false); };
  const cancel = () => { setDraft(value); setEditing(false); };

  return (
    <div style={{ fontFamily: "var(--font-family-base, Lato, sans-serif)", display: "flex", flexDirection: "column", gap: 4, ...style }}>
      {label && <span style={{ color: "var(--color-text-secondary)", fontSize: "var(--text-form-label-size)", fontWeight: "var(--text-form-label-weight)", lineHeight: "var(--text-form-label-line)" }}>{label}</span>}
      {editing ? (
        <div style={{ display: "flex", alignItems: "center", gap: 8, borderBottom: "1px solid #8C8C8C", paddingBottom: 4 }}>
          <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") confirm(); if (e.key === "Escape") cancel(); }}
            style={{ background: "transparent", border: "none", color: "var(--color-text-primary)", flex: 1, fontSize: "var(--text-form-input-size)", fontWeight: "var(--text-form-input-weight)", lineHeight: "var(--text-form-input-line)", outline: "none" }} />
          <button type="button" onClick={confirm} style={{ background: "none", border: "none", padding: 0, cursor: "pointer", display: "inline-flex" }}><Icon name="CheckCircle" size={20} color="#008000" /></button>
          <button type="button" onClick={cancel} style={{ background: "none", border: "none", padding: 0, cursor: "pointer", display: "inline-flex" }}><Icon name="Close" size={20} color="#CC0000" /></button>
        </div>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: "var(--color-text-primary)", fontSize: "var(--text-body-size)", lineHeight: "var(--text-body-line)" }}>{value || "—"}</span>
          <button type="button" onClick={start} style={{ background: "none", border: "none", padding: 0, cursor: "pointer", display: "inline-flex" }}><Icon name="Edit" size={18} color="#995A00" /></button>
        </div>
      )}
    </div>
  );
}

export default InlineEditField;
