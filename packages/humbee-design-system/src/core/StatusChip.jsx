import React from "react";

/* Humbee StatusChip — ported from chips/StatusChip.js.
   Status-driven pill. Colours come from the theme palette (warning/error/success/info). */
const STATUS = {
  pending:               "#E3B35C",
  "not-verified":        "#F9485A",
  verified:              "#1A7A32",
  approved:              "#1A7A32",
  completed:             "#1A7A32",
  success:               "#1A7A32",
  "partially-completed": "#2A6FA8",
  cancelled:             "#F9485A",
  default:               "#D3C4B2",
};

const STATUS_CHIP_MOTION = `
  @keyframes hb-status-chip-enter {
    0% { opacity: 0; transform: scale(0.88); }
    65% { opacity: 1; transform: scale(1.04); }
    100% { opacity: 1; transform: scale(1); }
  }
  .hb-status-chip {
    animation: hb-status-chip-enter 280ms cubic-bezier(0.2, 0, 0, 1) both;
    transition:
      background-color 200ms ease,
      border-color 200ms ease,
      color 200ms ease;
  }
  @media (prefers-reduced-motion: reduce) {
    .hb-status-chip {
      animation: none;
      transition: none;
    }
  }
`;

function hexA(hex, a) {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}

export function StatusChip({ status = "default", label, type = "outlined", className = "", style, ...rest }) {
  const c = STATUS[status] || STATUS.default;
  const isFilled = type === "filled";
  const isText = type === "text";
  return (
    <>
      <span
        key={`${status}-${label}-${type}`}
        style={{
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0, whiteSpace: "nowrap",
          fontFamily: "var(--font-family-base, Lato, sans-serif)",
          fontWeight: 700, fontSize: 13, lineHeight: "24px", padding: "0 12px",
          borderRadius: 16,
          color: isFilled ? "var(--color-text-inverse)" : "var(--color-text-primary)",
          backgroundColor: isText ? "transparent" : isFilled ? c : hexA(c, 0.1),
          border: isText || isFilled ? "none" : `1px solid ${c}`,
          ...style,
        }}
        {...rest}
        className={`hb-status-chip${className ? ` ${className}` : ""}`}
      >
        {label}
      </span>
      <style>{STATUS_CHIP_MOTION}</style>
    </>
  );
}

export default StatusChip;
