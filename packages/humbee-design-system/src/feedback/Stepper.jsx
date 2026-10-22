import React from "react";
import { Icon } from "../core/Icon.jsx";

/* Humbee Stepper — ported from Stepper/index.js.
   Amber (#FFA525) active/completed circles; completed shows a check. Horizontal or vertical. */
const SIZE = { small: 24, medium: 32, large: 40 };
const AMBER = "#FFA525", INACTIVE = "#8C8C8C";

export function Stepper({
  steps = [],              // [{label, subLabel}]
  activeStep = 0,
  orientation = "horizontal",
  size = "medium",
  showSubLabels = false,
  style,
}) {
  const dim = SIZE[size] || 32;
  const horizontal = orientation === "horizontal";

  const statusOf = (i) => (i < activeStep ? "completed" : i === activeStep ? "active" : "inactive");
  const circleBg = (st) => (st === "inactive" ? INACTIVE : AMBER);

  return (
    <div style={{ display: "flex", flexDirection: horizontal ? "row" : "column", alignItems: horizontal ? "center" : "stretch", gap: horizontal ? 16 : 8, width: "100%", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      {steps.map((step, i) => {
        const st = statusOf(i);
        const last = i === steps.length - 1;
        return (
          <React.Fragment key={i}>
            <div style={{ display: "flex", flexDirection: horizontal ? "column" : "row", alignItems: "center", gap: horizontal ? 8 : 12, flex: horizontal ? 1 : "none" }}>
              <div style={{ width: dim, height: dim, borderRadius: "50%", background: circleBg(st), color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: size === "small" ? 12 : size === "large" ? 16 : 14, flexShrink: 0 }}>
                {st === "completed" ? <Icon name="CheckCircle" size={dim * 0.6} color="#fff" /> : i + 1}
              </div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: horizontal ? "center" : "flex-start", gap: 2 }}>
                <span style={{ fontSize: size === "small" ? 12 : size === "large" ? 16 : 14, color: st === "inactive" ? "#666666" : "#333333", fontWeight: st === "inactive" ? 400 : 700, textAlign: horizontal ? "center" : "left" }}>{step.label}</span>
                {showSubLabels && step.subLabel && <span style={{ fontSize: 12, color: "#666666" }}>{step.subLabel}</span>}
              </div>
            </div>
            {!last && (
              <div style={horizontal
                ? { flex: 1, height: 2, minWidth: 24, borderRadius: 2, background: i < activeStep ? AMBER : INACTIVE }
                : { width: 2, minHeight: 32, marginLeft: dim / 2, borderRadius: 2, background: i < activeStep ? AMBER : INACTIVE }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

export default Stepper;
