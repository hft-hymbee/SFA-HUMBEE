import React from "react";

/* Humbee PhoneFrame — an iPhone-class 375px device bezel for presenting mobile screens
   in a gallery. Children render inside a 375×812 viewport with a status bar. */
export function PhoneFrame({ label, sublabel, children, statusColor = "#fff", height = 812, style }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-start", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      {label && (
        <div style={{ paddingLeft: 4 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#333" }}>{label}</div>
          {sublabel && <div style={{ fontSize: 12, color: "#8C8C8C" }}>{sublabel}</div>}
        </div>
      )}
      <div style={{ width: 375, height, background: "#000", borderRadius: 44, padding: 10, boxShadow: "0 12px 40px rgba(0,0,0,0.22)", flexShrink: 0 }}>
        <div style={{ width: "100%", height: "100%", background: "#fff", borderRadius: 34, overflow: "hidden", position: "relative", display: "flex", flexDirection: "column" }}>
          <div style={{ height: 44, flexShrink: 0, background: statusColor, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 22px", fontSize: 13, fontWeight: 700, color: statusColor === "#995A00" ? "#fff" : "#333" }}>
            <span>9:41</span>
            <span style={{ width: 120, height: 26, background: "#000", borderRadius: 14, alignSelf: "center", marginTop: 2 }} />
            <span style={{ display: "flex", gap: 4, alignItems: "center", fontSize: 12 }}>●●● ▮</span>
          </div>
          <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>{children}</div>
        </div>
      </div>
    </div>
  );
}

export default PhoneFrame;
