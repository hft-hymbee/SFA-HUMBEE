import React from "react";
import { Icon } from "../core/Icon.jsx";

/* Humbee MapPreview — a lightweight, non-interactive map placeholder tile (grid + pin).
   Stands in for an embedded map; swap for a real tile provider when wired. */
export function MapPreview({ height = 140, pin = true, label, style }) {
  return (
    <div style={{
      position: "relative", height, borderRadius: "var(--radius-md)", overflow: "hidden", background: "color-mix(in srgb, var(--color-success-surface) 72%, var(--surface-card))",
      backgroundImage: "linear-gradient(color-mix(in srgb, var(--color-success) 12%, transparent) 1px,transparent 1px),linear-gradient(90deg,color-mix(in srgb, var(--color-success) 12%, transparent) 1px,transparent 1px)",
      backgroundSize: "22px 22px", border: "1px solid var(--color-neutral-300)", ...style,
    }}>
      <div style={{ position: "absolute", top: "38%", left: 0, right: 0, height: 10, background: "color-mix(in srgb, var(--color-success) 12%, var(--surface-card))" }} />
      <div style={{ position: "absolute", top: 0, bottom: 0, left: "62%", width: 12, background: "color-mix(in srgb, var(--color-accent) 12%, var(--surface-card))" }} />
      {pin && (
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-100%)" }}>
          <Icon name="LocationPin" size={40} color="var(--color-error)" />
        </div>
      )}
      {label && <div style={{ position: "absolute", left: 8, bottom: 8, background: "color-mix(in srgb, var(--surface-card) 92%, transparent)", borderRadius: 6, padding: "3px 8px", fontSize: 11, fontWeight: 700, color: "var(--color-text-primary)", fontFamily: "var(--font-family-base, Lato, sans-serif)" }}>{label}</div>}
    </div>
  );
}

/* LocationCaptureCard — live GPS capture card used on Punch in/out.
   status: 'locating' | 'captured' | 'error'. Shows coords, accuracy, timestamp, map preview. */
export function LocationCaptureCard({
  status = "captured",
  address = "MG Road, Bengaluru",
  coords = "12.9758° N, 77.6096° E",
  accuracy = "±8 m",
  time,
  preview,
  style,
}) {
  const map = { locating: { c: "var(--color-info)", t: "Locating you…" }, captured: { c: "var(--color-success)", t: "Location captured" }, error: { c: "var(--color-error)", t: "Couldn't get location" } };
  const s = map[status] || map.captured;
  return (
    <div style={{ border: "1px solid var(--color-neutral-300)", borderRadius: "var(--radius-md)", overflow: "hidden", background: "var(--hb-surface-raised, var(--surface-card))", boxShadow: "var(--hb-shadow-raised)", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      {preview ?? <MapPreview height={128} pin={status === "captured"} style={{ borderRadius: 0, border: "none", borderBottom: "1px solid var(--color-neutral-300)" }} />}
      <div style={{ padding: 12, display: "flex", gap: 10, alignItems: "flex-start" }}>
        <Icon name="LocationMarker" size={22} color={s.c} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span className="hb-heading" style={{ fontSize: 14, color: s.c }}>{s.t}</span>
            {status === "locating" && <Spinner c={s.c} />}
          </div>
          <div style={{ fontSize: 14, color: "var(--color-text-primary)", marginTop: 2 }}>{address}</div>
          <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 2 }}>{coords} · accuracy {accuracy}</div>
          {time && <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 2 }}>Captured at {time}</div>}
        </div>
      </div>
    </div>
  );
}

function Spinner({ c }) {
  return <span className="hb-spin-motion" style={{ width: 12, height: 12, display: "inline-block", border: `2px solid ${c}`, borderTopColor: "transparent", borderRadius: "50%", animation: "hb-spin 0.7s linear infinite" }}><style>{"@keyframes hb-spin{to{transform:rotate(360deg)}}@media (prefers-reduced-motion: reduce){.hb-spin-motion{animation:none!important}}"}</style></span>;
}

export default LocationCaptureCard;
