import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../core/Icon.jsx";

/* Humbee Select — ported from Select/CustomSelect.js.
   Outlined trigger + dropdown panel that attaches flush to the bottom edge (radius flattens when open). */
export function Select({
  label,
  placeholder = "Select an option",
  options = [],           // [{value,label}] or [string]
  value,
  onChange,
  searchable = false,
  searchPlaceholder = "Search options",
  emptyLabel = "No options found",
  error = false,
  helperText,
  disabled = false,
  width = 220,
  fullWidth = false,
  style,
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0, width: 0, maxHeight: 200, openUp: false });
  const ref = useRef(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  const norm = options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
  const visible = searchable && query.trim()
    ? norm.filter((option) => option.label.toLowerCase().includes(query.trim().toLowerCase()))
    : norm;
  const visibleOptions = visible.filter((option) => option.value !== value);
  const selected = norm.find((o) => o.value === value);
  const border = error ? "var(--color-error)" : open ? "var(--color-primary)" : "var(--color-border)";

  const updateMenuPosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const horizontalMargin = 8;
    const bottomMargin = 8;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const width = Math.min(rect.width, Math.max(180, viewportWidth - (horizontalMargin * 2)));
    const left = Math.min(
      Math.max(horizontalMargin, rect.left),
      viewportWidth - width - horizontalMargin,
    );
    const spaceBelow = viewportHeight - rect.bottom - bottomMargin;
    const spaceAbove = rect.top - bottomMargin;
    const openUp = spaceBelow < 140 && spaceAbove > spaceBelow;
    const maxHeight = Math.max(120, Math.min(280, openUp ? spaceAbove : spaceBelow));
    const top = openUp ? Math.max(bottomMargin, rect.top - maxHeight) : rect.bottom;

    setMenuPosition({ top, left, width, maxHeight, openUp });
  }, []);

  useEffect(() => {
    const h = (e) => {
      const target = e.target;
      if (ref.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    const syncPosition = () => updateMenuPosition();
    syncPosition();
    window.addEventListener("resize", syncPosition);
    window.addEventListener("scroll", syncPosition, true);
    return () => {
      window.removeEventListener("resize", syncPosition);
      window.removeEventListener("scroll", syncPosition, true);
    };
  }, [open, updateMenuPosition]);

  useEffect(() => {
    if (!open && query) setQuery("");
  }, [open, query]);

  return (
    <div ref={ref} style={{ position: "relative", width: fullWidth ? "100%" : width, fontFamily: "var(--font-family-base, Lato, sans-serif)", display: "flex", flexDirection: "column", gap: "var(--space-xs)", ...style }}>
      {label && <label style={{ color: error ? "var(--color-error)" : "var(--color-text-secondary)", fontWeight: 700, fontSize: "var(--text-label-sm-size)", lineHeight: "var(--text-label-sm-line)" }}>{label}</label>}
      <div ref={triggerRef} style={{ position: "relative", width: "100%" }}>
        <div
          onClick={() => !disabled && setOpen((o) => !o)}
          style={{
            minHeight: 44, display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "8px 12px", border: `1px solid ${border}`,
            borderRadius: open ? "var(--radius-md) var(--radius-md) 0 0" : "var(--radius-md)", cursor: disabled ? "not-allowed" : "pointer",
            background: disabled ? "var(--surface-muted)" : open ? "var(--hb-surface-selected, var(--color-primary))" : "var(--hb-surface-raised, var(--surface-card))",
            boxShadow: disabled ? "none" : open ? "var(--hb-shadow-selected)" : "var(--hb-shadow-raised)",
            color: open ? "var(--color-text-inverse)" : "var(--color-text-primary)",
            boxSizing: "border-box",
            transition: "var(--hb-transition-interactive, background-color var(--motion-duration-standard, 200ms) ease, border-color var(--motion-duration-standard, 200ms) ease, box-shadow var(--motion-duration-standard, 200ms) ease, color var(--motion-duration-standard, 200ms) ease)",
          }}
        >
          <span style={{ fontSize: "var(--text-body-size)", color: open ? "currentColor" : selected ? "var(--color-text-primary)" : "var(--color-text-placeholder)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {selected ? selected.label : placeholder}
          </span>
          <span style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform var(--motion-duration-fast, 140ms) var(--motion-ease-standard, ease)", display: "inline-flex" }}>
            <Icon name="KeyboardArrowDown" size={20} color="currentColor" />
          </span>
        </div>
      </div>
      {open && createPortal(
        <div
          ref={menuRef}
          style={{
            position: "fixed",
            top: menuPosition.top,
            left: menuPosition.left,
            width: menuPosition.width,
            boxSizing: "border-box",
            zIndex: 4000,
            maxHeight: menuPosition.maxHeight,
            overflowY: "auto",
            background: "var(--surface-card)",
            border: "1px solid var(--color-border)",
            borderTop: menuPosition.openUp ? "1px solid var(--color-border)" : "none",
            borderBottom: menuPosition.openUp ? "none" : "1px solid var(--color-border)",
            borderRadius: menuPosition.openUp
              ? "var(--radius-md) var(--radius-md) 0 0"
              : "0 0 var(--radius-md) var(--radius-md)",
            boxShadow: "var(--shadow-menu)",
          }}
        >
          {searchable ? (
            <div style={{ padding: "8px", borderBottom: "1px solid var(--color-border)", background: "var(--surface-card)", position: "sticky", top: 0 }}>
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={searchPlaceholder}
                style={{
                  width: "100%",
                  minHeight: 36,
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                  padding: "6px 8px",
                  fontSize: "var(--text-body-size)",
                  color: "var(--color-text-primary)",
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
            </div>
          ) : null}
          {visibleOptions.map((o) => (
            <div key={o.value} onClick={() => { onChange?.(o.value); setOpen(false); }}
              style={{ minHeight: 44, padding: "8px 12px", boxSizing: "border-box", display: "flex", alignItems: "center", fontSize: "var(--text-body-size)", color: "var(--color-text-primary)", cursor: "pointer", background: "transparent", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", transition: "background-color var(--motion-duration-fast, 140ms) var(--motion-ease-standard, ease)" }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--surface-hover-warm, var(--color-neutral-100))"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}>
              {o.label}
            </div>
          ))}
          {!visibleOptions.length ? (
            <div style={{ minHeight: 44, padding: "8px 12px", boxSizing: "border-box", display: "flex", alignItems: "center", fontSize: "var(--text-body-size)", color: "var(--color-text-secondary)" }}>
              {emptyLabel}
            </div>
          ) : null}
        </div>,
        document.body,
      )}
      {helperText && <span style={{ fontSize: "var(--text-caption-size)", color: error ? "var(--color-error)" : "var(--color-text-secondary)" }}>{helperText}</span>}
    </div>
  );
}

export default Select;
