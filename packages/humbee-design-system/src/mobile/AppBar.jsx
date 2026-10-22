import React from "react";
import { Icon, IconSurface } from "../core/Icon.jsx";

const insightsSlotStyle = {
  alignItems: "center",
  background: "transparent",
  border: "none",
  borderRadius: 20,
  boxShadow: "none",
  cursor: "pointer",
  display: "flex",
  flexShrink: 0,
  height: 40,
  justifyContent: "center",
  padding: 0,
  position: "relative",
  width: 40,
};

function InsightsAppBar({ title, onBack, onBell, bellCount = 0, action, style }) {
  const hasNotifications = bellCount > 0;
  let trailing = null;
  if (action) {
    trailing = action;
  } else if (onBell) {
    trailing = (
      <button type="button" onClick={onBell} aria-label="Notifications" style={insightsSlotStyle}>
        <span
          aria-hidden="true"
          className={`hb-notification-bell${hasNotifications ? " hb-notification-bell--active" : ""}`}
        >
          <Icon name="NotificationsOutlined" size={24} color="var(--color-text-primary)" />
        </span>
        {hasNotifications ? (
          <span style={{ position: "absolute", top: 4, right: 2, minWidth: 16, height: 16, padding: "0 4px", borderRadius: 8, background: "var(--color-error)", color: "var(--color-text-inverse)", fontSize: "var(--text-badge-size)", lineHeight: "var(--text-badge-line)", fontWeight: "var(--text-badge-weight)", display: "flex", alignItems: "center", justifyContent: "center", boxSizing: "border-box" }}>{bellCount > 9 ? "9+" : bellCount}</span>
        ) : null}
      </button>
    );
  }

  return (
    <header style={{
      alignSelf: "center",
      background: "transparent",
      boxSizing: "border-box",
      flexShrink: 0,
      fontFamily: "var(--font-family-base, Lato, sans-serif)",
      minWidth: 0,
      padding: "16px 16px 0",
      width: "min(100%, 480px)",
      ...style,
    }}>
      <div style={{
        background: "var(--surface-card)",
        border: "none",
        borderRadius: 16,
        boxShadow: "none",
        padding: 8,
      }}>
        <div style={{ alignItems: "center", display: "flex", gap: 8, height: 48, minWidth: 0 }}>
          {onBack ? (
            <button type="button" onClick={onBack} aria-label="Back" style={insightsSlotStyle}>
              <Icon name="ArrowBack" size={24} color="var(--color-text-primary)" />
            </button>
          ) : null}
          <h1 className="hb-heading" style={{
            color: "var(--color-text-primary)",
            flex: 1,
            fontSize: 20,
            fontWeight: 700,
            lineHeight: "32px",
            margin: 0,
            minWidth: 0,
            overflow: "hidden",
            padding: 0,
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}>{title}</h1>
          {trailing}
        </div>
      </div>
    </header>
  );
}

/* Humbee mobile app shell — TopAppBar + BottomNav.
   Mobile-first (375px). Reused on every SFA screen so the whole app reads as one product. */

export function TopAppBar({
  title,
  onBack,                 // if provided, shows a back chevron
  onBell,                 // notifications bell handler
  bellCount = 0,          // >0 shows a badge dot
  action,                 // optional trailing custom node (replaces bell)
  variant = "default",
  style,
}) {
  if (variant === "insights") {
    return (
      <InsightsAppBar
        title={title}
        onBack={onBack}
        onBell={onBell}
        bellCount={bellCount}
        action={action}
        style={style}
      />
    );
  }
  const hasNotifications = bellCount > 0;
  const isOrderFlow = variant === "order-flow";
  const appBarStyle = isOrderFlow
    ? {
      minHeight: 80,
      borderBottom: "0",
      gap: 12,
      padding: "20px 20px 16px",
    }
    : {
      minHeight: 56,
      borderBottom: "1px solid color-mix(in srgb, var(--color-primary) 24%, transparent)",
      gap: "var(--space-xs)",
      padding: "0 var(--space-sm)",
    };
  const iconButtonStyle = isOrderFlow
    ? {
      background: "var(--surface-card)",
      border: "1px solid var(--color-neutral-300)",
      boxShadow: "var(--hb-shadow-raised, 0 1px 2px rgb(0 0 0 / 8%))",
    }
    : {
      background: "transparent",
      border: "none",
      boxShadow: "none",
    };
  const titleStyle = isOrderFlow
    ? {
      fontSize: 18,
      lineHeight: "24px",
      fontWeight: 400,
    }
    : {
      fontSize: "var(--text-app-title-size)",
      lineHeight: "var(--text-app-title-line)",
      fontWeight: "var(--text-app-title-weight)",
    };

  return (
    <header style={{
      flexShrink: 0, background: "transparent",
      display: "flex", alignItems: "center",
      fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style,
      ...appBarStyle,
    }}>
      {onBack ? (
        <button type="button" onClick={onBack} aria-label="Back"
          style={{ width: 44, height: 44, borderRadius: 12, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, ...iconButtonStyle }}>
          <Icon name="ArrowBack" size={24} color="var(--color-text-primary)" />
        </button>
      ) : <span style={{ width: 8 }} />}
      <h1 className="hb-heading" style={{ margin: 0, flex: 1, color: "var(--color-text-primary)", padding: onBack ? 0 : "0 8px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", ...titleStyle }}>{title}</h1>
      {action ? action : onBell ? (
        <button type="button" onClick={onBell} aria-label="Notifications"
          style={{ width: 44, height: 44, borderRadius: 12, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", position: "relative", flexShrink: 0, ...iconButtonStyle }}>
          <span
            aria-hidden="true"
            className={`hb-notification-bell${hasNotifications ? " hb-notification-bell--active" : ""}`}
          >
            <Icon name="NotificationsOutlined" size={28} color="var(--color-text-primary)" />
          </span>
          {hasNotifications && (
            <span style={{ position: "absolute", top: 8, right: 9, minWidth: 16, height: 16, padding: "0 4px", borderRadius: 8, background: "var(--color-error)", color: "var(--color-text-inverse)", fontSize: "var(--text-badge-size)", lineHeight: "var(--text-badge-line)", fontWeight: "var(--text-badge-weight)", display: "flex", alignItems: "center", justifyContent: "center", boxSizing: "border-box" }}>{bellCount > 9 ? "9+" : bellCount}</span>
          )}
        </button>
      ) : <span style={{ width: 44 }} />}
    </header>
  );
}

/* Sales-Person bottom nav (5 tabs). active = one of the tab ids. */
export const SP_TABS = [
  { id: "today", label: "Today", icon: "HomeOutlined", activeIcon: "HomeFilled" },
  { id: "beats", label: "Beats", icon: "Calendar", activeIcon: "Calendar" },
  { id: "route", label: "Route", icon: "LocationMarker", activeIcon: "LocationMarker" },
  { id: "orders", label: "Orders", icon: "ShoppingCartOutlined", activeIcon: "ShoppingCartOutlined" },
  { id: "more", label: "More", icon: "Menu", activeIcon: "Menu" },
];

export function BottomNav({ active = "today", tabs = SP_TABS, onNav, style }) {
  return (
    <nav className="hb-bottom-nav" style={{
      flexShrink: 0,
      background: "linear-gradient(180deg, color-mix(in srgb, var(--surface-card) 92%, var(--color-accent) 8%), var(--surface-card-warm, var(--surface-card)))",
      borderTop: "1px solid color-mix(in srgb, var(--color-primary) 18%, var(--color-neutral-300))",
      boxShadow: "0 -8px 18px color-mix(in srgb, var(--color-primary) 9%, transparent)",
      display: "flex", alignItems: "stretch", minHeight: 68, padding: "6px 6px env(safe-area-inset-bottom)",
      fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style,
    }}>
      {tabs.map((t) => {
        const on = t.id === active;
        return (
          <button key={t.id} type="button" className="hb-bottom-nav__item" onClick={() => onNav?.(t.id)}
            style={{ flex: 1, border: "none", background: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", padding: "0 2px", minHeight: 44, minWidth: 0 }}>
            <span
              style={{
                alignItems: "center",
                background: on ? "linear-gradient(180deg, color-mix(in srgb, var(--color-primary) 16%, white), color-mix(in srgb, var(--color-primary) 10%, var(--surface-card)))" : "transparent",
                border: on ? "1px solid color-mix(in srgb, var(--color-primary) 24%, transparent)" : "1px solid transparent",
                borderRadius: "var(--radius-lg)",
                boxShadow: on ? "var(--hb-shadow-raised, 0 4px 12px rgb(153 90 0 / 12%))" : "none",
                color: on ? "var(--color-primary)" : "var(--color-text-placeholder)",
                display: "flex",
                flexDirection: "column",
                gap: 4,
                justifyContent: "center",
                minHeight: 54,
                padding: "5px 6px",
                transform: on ? "translateY(-1px)" : "translateY(0)",
                transition: "var(--hb-transition-interactive, background-color var(--motion-duration-standard, 200ms) ease, box-shadow var(--motion-duration-standard, 200ms) ease, color var(--motion-duration-standard, 200ms) ease, transform var(--motion-duration-fast, 140ms) ease)",
                width: "100%",
              }}
            >
              <IconSurface
                name={on ? t.activeIcon : t.icon}
                size={38}
                glyphSize={24}
                shape="circle"
                tone={on ? "accent" : "neutral"}
                color={on ? "var(--color-primary)" : "var(--color-primary)"}
                style={on
                  ? { background: "color-mix(in srgb, var(--color-accent) 18%, white)", borderColor: "color-mix(in srgb, var(--color-primary) 14%, transparent)", boxShadow: "var(--shadow-icon-depth, none)" }
                  : { background: "color-mix(in srgb, var(--color-primary-surface) 58%, transparent)", borderColor: "color-mix(in srgb, var(--color-primary) 10%, transparent)", boxShadow: "none" }}
              />
              <span style={{ fontSize: "var(--text-overline-size)", fontWeight: on ? 700 : 600, color: "currentColor", lineHeight: 1 }}>{t.label}</span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}

export const AppBar = TopAppBar;
export default TopAppBar;
