import React, { useRef } from "react";

/* Humbee OTPInput — fixed-length one-time-code entry (boxes). Mobile numeric keypad. */
export function OTPInput({ length = 6, value = "", onChange, error = false, style }) {
  const refs = useRef([]);
  const chars = value.padEnd(length).slice(0, length).split("");

  const setAt = (i, ch) => {
    const next = value.split("");
    next[i] = ch;
    const joined = next.join("").slice(0, length);
    onChange?.(joined.replace(/\s/g, ""));
  };

  return (
    <div style={{ display: "flex", gap: 8, justifyContent: "space-between", ...style }}>
      {Array.from({ length }).map((_, i) => (
        <input
          key={i}
          ref={(el) => (refs.current[i] = el)}
          inputMode="numeric"
          maxLength={1}
          value={(chars[i] || "").trim()}
          onChange={(e) => {
            const ch = e.target.value.replace(/\D/g, "").slice(-1);
            setAt(i, ch || " ");
            if (ch && i < length - 1) refs.current[i + 1]?.focus();
          }}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && !(chars[i] || "").trim() && i > 0) refs.current[i - 1]?.focus();
          }}
          style={{
            width: 44, height: 52, textAlign: "center", fontSize: 22, fontWeight: 700,
            color: "#333", border: `2px solid ${error ? "#CC0000" : (chars[i] || "").trim() ? "#995A00" : "#D9D9D9"}`,
            borderRadius: 8, outline: "none", fontFamily: "var(--font-family-base, Lato, sans-serif)",
            background: "var(--surface-card)", boxSizing: "border-box", flex: 1, minWidth: 0,
          }}
        />
      ))}
    </div>
  );
}

export default OTPInput;
