import React from "react";
import { Icon, IconSurface } from "../core/Icon.jsx";
import { Button } from "../core/Button.jsx";

/* Humbee mobile feedback/state components — the mandatory states every data screen ships with. */

/* Skeleton — shimmer placeholder block. */
export function Skeleton({ width = "100%", height = 16, radius = 8, style }) {
  return (
    <div className="hb-skeleton-motion" style={{ width, height, borderRadius: radius, background: "linear-gradient(90deg,color-mix(in srgb, var(--color-neutral-200) 82%, white) 25%,var(--surface-card) 37%,color-mix(in srgb, var(--color-neutral-200) 82%, white) 63%)", backgroundSize: "400% 100%", animation: "hb-shimmer 1.4s var(--motion-ease-standard, ease) infinite", boxShadow: "inset 0 1px 0 color-mix(in srgb, white 70%, transparent)", ...style }}>
      <style>{"@keyframes hb-shimmer{0%{background-position:100% 50%}100%{background-position:0 50%}}@media (prefers-reduced-motion: reduce){.hb-skeleton-motion{animation:none!important}}"}</style>
    </div>
  );
}

/* SkeletonRow — a list-row-shaped skeleton. */
export function SkeletonRow({ style }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", padding: "var(--space-sm) var(--space-md)", background: "var(--hb-surface-raised, var(--surface-card))", borderBottom: "1px solid var(--color-neutral-200)", ...style }}>
      <Skeleton width={40} height={40} radius={8} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
        <Skeleton width="60%" height={14} />
        <Skeleton width="40%" height={12} />
      </div>
      <Skeleton width={60} height={24} radius={16} />
    </div>
  );
}

/* EmptyState — centred illustration slot + message + recovery CTA (never a dead end). */
export function EmptyState({ icon = "InventoryOutlined", title, message, actionLabel, onAction, style }) {
  return (
    <div className="sp-enter" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "var(--space-2xl) var(--space-lg)", gap: "var(--space-sm)", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      <IconSurface name={icon} size="empty" tone="primary" />
      <h3 className="hb-heading" style={{ margin: 0, fontSize: "var(--text-h3-size)", color: "var(--color-text-primary)" }}>{title}</h3>
      {message && <p style={{ margin: 0, fontSize: "var(--text-body-sm-size)", color: "var(--color-text-secondary)", maxWidth: 260, lineHeight: "var(--text-body-sm-line)" }}>{message}</p>}
      {actionLabel && <div style={{ marginTop: "var(--space-sm)" }}><Button variant="outlined" color="primary" label={actionLabel} onClick={onAction} /></div>}
    </div>
  );
}

/* ErrorState — problem + retry. */
export function ErrorState({ title = "Something went wrong", message = "We couldn't load this. Check your connection and try again.", onRetry, retryLabel = "Retry", style }) {
  return (
    <div className="sp-enter" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "var(--space-2xl) var(--space-lg)", gap: "var(--space-sm)", fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      <IconSurface name="Warning" size="empty" tone="error" />
      <h3 className="hb-heading" style={{ margin: 0, fontSize: "var(--text-h3-size)", color: "var(--color-text-primary)" }}>{title}</h3>
      <p style={{ margin: 0, fontSize: "var(--text-body-sm-size)", color: "var(--color-text-secondary)", maxWidth: 260, lineHeight: "var(--text-body-sm-line)" }}>{message}</p>
      {onRetry && <div style={{ marginTop: "var(--space-sm)" }}><Button variant="filled" color="primary" label={retryLabel} leftIcon={<Icon name="Autorenew" size={20} color="var(--color-text-inverse)" />} onClick={onRetry} /></div>}
    </div>
  );
}

/* OfflineBanner — sticky strip shown when connectivity drops (online-only app). */
export function OfflineBanner({ message = "You're offline. Some actions are paused.", onRetry, style }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", padding: "var(--space-sm) var(--space-md)", background: "linear-gradient(180deg, var(--color-neutral-900), color-mix(in srgb, var(--color-neutral-900) 88%, var(--color-primary)))", color: "var(--color-text-inverse)", fontSize: "var(--text-body-sm-size)", fontFamily: "var(--font-family-base, Lato, sans-serif)", boxShadow: "var(--hb-shadow-raised)", ...style }}>
      <Icon name="Warning" size={18} color="var(--color-warning)" />
      <span style={{ flex: 1 }}>{message}</span>
      {onRetry && <button type="button" onClick={onRetry} style={{ background: "none", border: "none", color: "var(--color-accent)", fontWeight: 700, fontSize: "var(--text-body-sm-size)", cursor: "pointer", fontFamily: "inherit", minHeight: 44 }}>Retry</button>}
    </div>
  );
}

export const Feedback = EmptyState;
export default EmptyState;
