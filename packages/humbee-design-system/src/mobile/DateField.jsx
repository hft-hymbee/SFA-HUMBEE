import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../core/Icon.jsx";

const WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"];
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function pad(value) {
  return String(value).padStart(2, "0");
}

function todayIstIso() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
}

function parseIso(value) {
  if (!ISO_DATE.test(value ?? "")) return null;
  const [year, month, day] = value.split("-").map(Number);
  return { year, month, day };
}

function isoDate(year, month, day) {
  return `${year}-${pad(month)}-${pad(day)}`;
}

function weekdayOffsetIst(year, month) {
  const weekday = new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(`${isoDate(year, month, 1)}T12:00:00+05:30`));
  return Math.max(0, ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(weekday));
}

function shiftMonth(year, month, delta) {
  const date = new Date(year, month - 1 + delta, 1);
  return { year: date.getFullYear(), month: date.getMonth() + 1 };
}

function monthLabel(year, month) {
  return new Intl.DateTimeFormat("en-IN", {
    month: "long",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(new Date(`${isoDate(year, month, 15)}T12:00:00+05:30`));
}

function monthFromValue(value) {
  return parseIso(value) ?? parseIso(todayIstIso()) ?? { year: new Date().getFullYear(), month: new Date().getMonth() + 1 };
}

function isOutOfRange(iso, min, max) {
  return Boolean((min && iso < min) || (max && iso > max));
}

const navButtonStyle = {
  alignItems: "center",
  background: "transparent",
  border: "none",
  borderRadius: 8,
  color: "var(--color-text-primary, #333)",
  cursor: "pointer",
  display: "flex",
  flex: "0 0 auto",
  height: 32,
  justifyContent: "center",
  padding: 0,
  width: 32,
};

function DateCalendar({ dateValue, min, max, isDateEnabled, year, month, onMonthChange, onSelect }) {
  const today = todayIstIso();
  const offset = weekdayOffsetIst(year, month);
  const days = new Date(year, month, 0).getDate();

  return (
    <div>
      <div style={{ alignItems: "center", display: "flex", gap: 4, justifyContent: "space-between", marginBottom: 8 }}>
        <button type="button" aria-label="Previous month" onClick={() => onMonthChange(shiftMonth(year, month, -1))} style={navButtonStyle}>
          <Icon name="KeyboardArrowLeft" size={20} color="currentColor" />
        </button>
        <span style={{ color: "var(--color-text-primary, #333)", fontSize: 14, fontWeight: 700, minWidth: 0, overflow: "hidden", textAlign: "center", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {monthLabel(year, month)}
        </span>
        <button type="button" aria-label="Next month" onClick={() => onMonthChange(shiftMonth(year, month, 1))} style={navButtonStyle}>
          <Icon name="KeyboardArrowRight" size={20} color="currentColor" />
        </button>
      </div>
      <div style={{ display: "grid", gap: 2, gridTemplateColumns: "repeat(7, minmax(0, 1fr))", marginBottom: 4 }}>
        {WEEKDAYS.map((day, index) => (
          <span key={`${day}-${index}`} style={{ color: "var(--color-text-secondary, #666)", fontSize: 11, fontWeight: 700, lineHeight: "20px", textAlign: "center" }}>{day}</span>
        ))}
      </div>
      <div style={{ display: "grid", gap: 2, gridTemplateColumns: "repeat(7, minmax(0, 1fr))" }}>
        {Array.from({ length: offset }, (_, index) => <span key={`pad-${index}`} />)}
        {Array.from({ length: days }, (_, index) => {
          const day = index + 1;
          const iso = isoDate(year, month, day);
          const selected = iso === dateValue;
          const isToday = iso === today;
          const disabled = isOutOfRange(iso, min, max) || (isDateEnabled ? !isDateEnabled(iso) : false);
          return (
            <button
              key={iso}
              type="button"
              disabled={disabled}
              aria-label={iso}
              aria-pressed={selected}
              onClick={() => { if (!disabled) onSelect(iso); }}
              style={{
                background: selected ? "var(--color-primary, #995A00)" : "transparent",
                border: `1px solid ${selected || isToday ? "var(--color-primary, #995A00)" : "transparent"}`,
                borderRadius: 8,
                color: selected
                  ? "var(--color-text-inverse, #fff)"
                  : disabled
                    ? "var(--color-text-disabled, #B3B3B3)"
                    : isToday
                      ? "var(--color-primary, #995A00)"
                      : "var(--color-text-primary, #333)",
                cursor: disabled ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                fontSize: 13,
                fontWeight: selected || isToday ? 700 : 400,
                height: 36,
                minWidth: 0,
                overflow: "hidden",
                padding: 0,
                width: "100%",
              }}
            >
              {day}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function DateField({
  label,
  value,
  dateValue,
  placeholder = "Select date",
  onClick,
  onChange,
  min,
  max,
  isDateEnabled,
  inline = false,
  error = false,
  disabled = false,
  fullWidth = true,
  compact = false,
  style,
}) {
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(() => monthFromValue(dateValue));
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0, width: 0, openUp: false });
  const border = error ? "#CC0000" : open ? "var(--color-primary, #995A00)" : "#8C8C8C";

  const updateMenuPosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const panelHeight = menuRef.current?.offsetHeight ?? 0;
    const spaceBelow = window.innerHeight - rect.bottom - 8;
    const spaceAbove = rect.top - 8;
    const estimatedHeight = panelHeight || 280;
    const openUp = spaceBelow < estimatedHeight && spaceAbove > spaceBelow;
    setMenuPosition({
      top: openUp ? Math.max(8, rect.top - estimatedHeight) : rect.bottom,
      left: rect.left,
      width: rect.width,
      openUp,
    });
  }, []);

  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event) => {
      const target = event.target;
      if (rootRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

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
  }, [open, cursor, updateMenuPosition]);

  const toggleOpen = () => {
    if (disabled) return;
    if (!onChange) {
      onClick?.();
      return;
    }
    if (open) {
      setOpen(false);
      return;
    }
    setCursor(monthFromValue(dateValue));
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setMenuPosition({ top: rect.bottom, left: rect.left, width: rect.width, openUp: false });
    }
    setOpen(true);
  };

  const radius = open
    ? (menuPosition.openUp ? "0 0 8px 8px" : "8px 8px 0 0")
    : 8;

  const calendar = (
    <DateCalendar
      dateValue={dateValue}
      min={min}
      max={max}
      isDateEnabled={isDateEnabled}
      year={cursor.year}
      month={cursor.month}
      onMonthChange={setCursor}
      onSelect={(iso) => {
        onChange?.(iso);
        if (!inline) setOpen(false);
      }}
    />
  );

  if (inline) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8, width: fullWidth ? "100%" : "auto", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
        {label && <label style={{ color: error ? "#CC0000" : "#666666", fontSize: 13, lineHeight: "20px", fontWeight: 700 }}>{label}</label>}
        {calendar}
      </div>
    );
  }

  if (compact) {
    return (
      <div ref={rootRef} style={{ display: "flex", flexDirection: "column", gap: 4, fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
        {label && <label style={{ color: error ? "#CC0000" : "#666666", fontSize: 13, lineHeight: "20px", fontWeight: 700 }}>{label}</label>}
        <div ref={triggerRef} style={{ position: "relative" }}>
          <button
            type="button"
            onClick={toggleOpen}
            disabled={disabled}
            aria-expanded={onChange ? open : undefined}
            aria-haspopup={onChange ? "dialog" : undefined}
            style={{
              alignItems: "center",
              background: disabled ? "var(--surface-muted)" : "var(--color-primary-surface, #F2D8BC)",
              border: `1.5px solid ${border}`,
              borderRadius: 999,
              color: disabled ? "var(--color-text-disabled, #B3B3B3)" : "var(--color-primary, #995A00)",
              cursor: disabled ? "not-allowed" : "pointer",
              display: "flex",
              fontFamily: "inherit",
              fontSize: 14,
              fontWeight: 700,
              gap: 6,
              height: 40,
              padding: "0 14px",
              whiteSpace: "nowrap",
            }}
          >
            <Icon name="Calendar" size={18} color="currentColor" />
            <span>{value || placeholder}</span>
          </button>
        </div>
        {open && onChange && typeof document !== "undefined" && createPortal(
          <div
            ref={menuRef}
            role="dialog"
            aria-label="Choose date"
            style={{
              position: "fixed",
              top: menuPosition.top,
              left: Math.max(8, Math.min(menuPosition.left, window.innerWidth - Math.max(menuPosition.width, 260) - 8)),
              width: Math.max(menuPosition.width, 260),
              boxSizing: "border-box",
              zIndex: 4000,
              background: "var(--surface-card, #fff)",
              border: "1px solid var(--color-border, #8C8C8C)",
              borderRadius: 8,
              boxShadow: "var(--shadow-menu, 0 8px 24px rgba(0, 0, 0, 0.12))",
              padding: 8,
            }}
          >
            {calendar}
          </div>,
          document.body,
        )}
      </div>
    );
  }

  return (
    <div ref={rootRef} style={{ display: "flex", flexDirection: "column", gap: 4, width: fullWidth ? "100%" : "auto", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      {label && <label style={{ color: error ? "#CC0000" : "#666666", fontSize: 13, lineHeight: "20px", fontWeight: 700 }}>{label}</label>}
      <div ref={triggerRef} style={{ position: "relative" }}>
        <button
          type="button"
          onClick={toggleOpen}
          disabled={disabled}
          aria-expanded={onChange ? open : undefined}
          aria-haspopup={onChange ? "dialog" : undefined}
          style={{
            height: 40,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 8,
            padding: "8px 12px",
            border: `1px solid ${border}`,
            borderRadius: radius,
            background: disabled ? "var(--surface-muted)" : "var(--hb-surface-raised, var(--surface-card))",
            boxShadow: disabled ? "none" : "var(--hb-shadow-raised)",
            cursor: disabled ? "not-allowed" : "pointer",
            fontFamily: "inherit",
            boxSizing: "border-box",
            width: "100%",
          }}
        >
          <span style={{ fontSize: 16, color: value ? "#333" : "#8C8C8C" }}>{value || placeholder}</span>
          <Icon name="Calendar" size={20} color="#666666" />
        </button>
      </div>
      {open && onChange && typeof document !== "undefined" && createPortal(
        <div
          ref={menuRef}
          role="dialog"
          aria-label="Choose date"
          style={{
            position: "fixed",
            top: menuPosition.top,
            left: menuPosition.left,
            width: menuPosition.width,
            boxSizing: "border-box",
            zIndex: 4000,
            background: "var(--surface-card, #fff)",
            border: "1px solid var(--color-border, #8C8C8C)",
            borderTop: menuPosition.openUp ? "1px solid var(--color-border, #8C8C8C)" : "none",
            borderBottom: menuPosition.openUp ? "none" : "1px solid var(--color-border, #8C8C8C)",
            borderRadius: menuPosition.openUp ? "8px 8px 0 0" : "0 0 8px 8px",
            boxShadow: "var(--shadow-menu, 0 8px 24px rgba(0, 0, 0, 0.12))",
            padding: 8,
          }}
        >
          {calendar}
        </div>,
        document.body,
      )}
    </div>
  );
}

export default DateField;
