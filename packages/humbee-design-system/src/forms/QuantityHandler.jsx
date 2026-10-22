import React from "react";
import { Icon } from "../core/Icon.jsx";

/* Humbee QuantityHandler — ported from QuantityHandler/QuantityHandler.js.
   Bordered stepper: minus / centred value / plus. */
export function QuantityHandler({
  value = 0,
  onIncrease,
  onDecrease,
  onChange,
  variant = "medium",     // 'small' | 'medium'
  disabled = false,
  min = 0,
  increaseDisabled = false,
  style,
}) {
  const small = variant === "small";
  const iconBtn = (name, action, dis) => (
    <button type="button" disabled={dis} onClick={dis ? undefined : action}
      style={{ background: "none", border: "none", padding: 0, display: "inline-flex", cursor: dis ? "not-allowed" : "pointer", opacity: dis ? 0.4 : 1 }}>
      <Icon name={name} size={small ? 16 : 24} color="#666666" />
    </button>
  );
  const num = value === undefined || value === null ? "" : String(value);
  return (
    <div style={{
      border: "1px solid #ccc", borderRadius: 8, height: small ? 32 : 40,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: small ? "0 8px" : "0 12px", gap: small ? 8 : 16,
      minWidth: small ? 110 : 165, boxSizing: "border-box",
      fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style,
    }}>
      {iconBtn("Minus", onDecrease, disabled || parseFloat(num || "0") <= min)}
      <input value={num} disabled={disabled} onChange={onChange}
        style={{ border: "none", outline: "none", textAlign: "center", width: `${Math.max(2, num.length) * (small ? 8 : 10)}px`, font: "inherit", fontSize: small ? 13 : 16, color: "#333", background: "transparent" }} />
      {iconBtn("Add", onIncrease, disabled || increaseDisabled)}
    </div>
  );
}

export default QuantityHandler;
