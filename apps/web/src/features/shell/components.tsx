"use client";

import { ApprovalTimeline, BottomNav, Icon, IconSurface, OfflineBanner, TopAppBar } from "humbee-design-system";
import { usePathname, useRouter } from "next/navigation";
import { Children, isValidElement } from "react";
import type { CSSProperties, ReactNode } from "react";
import { useUnreadNotificationCount } from "@/src/features/approvals/hooks";

const SHOW_MOBILE_DEVELOPMENT_FRAME = false;

const TAB_ROUTES: Record<string, string> = {
  today: "/sp",
  beats: "/sp/beats",
  route: "/sp/route",
  orders: "/sp/orders",
  more: "/sp/more",
};

const SP_TAB_ROOTS = new Set(Object.values(TAB_ROUTES));

function activeTab(pathname: string) {
  if (pathname.startsWith("/sp/beats")) return "beats";
  if (pathname.startsWith("/sp/route") || pathname.startsWith("/sp/visits")) return "route";
  if (pathname.startsWith("/sp/orders")) return "orders";
  if (pathname.startsWith("/sp/more")) return "more";
  return "today";
}

export type StatusHistoryStep = {
  label: string;
  detail?: string;
  time?: string;
  state: "done" | "edited" | "rejected" | "pending" | "current" | "future";
};

export function SpMobileFrame({ children }: { children: ReactNode }) {
  return (
    <div
      className={`sp-page-background${SHOW_MOBILE_DEVELOPMENT_FRAME ? " sp-page-background--framed" : ""}`}
    >
      <div className="sp-shell role-shell">{children}</div>
    </div>
  );
}

interface SpScreenProps {
  title: string;
  children: ReactNode;
  back?: boolean;
  bell?: boolean;
  bellCount?: number;
  action?: ReactNode;
  toolbar?: ReactNode;
  bottomAction?: ReactNode;
  offline?: boolean;
  appBarVariant?: "default" | "order-flow" | "insights";
}

export function SpScreen({
  title,
  children,
  back,
  bell,
  bellCount,
  action,
  toolbar,
  bottomAction,
  offline,
  appBarVariant,
}: SpScreenProps) {
  const router = useRouter();
  const pathname = usePathname();
  const unread = useUnreadNotificationCount();
  const isTabRoot = SP_TAB_ROOTS.has(pathname);
  const showBack = back ?? !isTabRoot;
  const showBell = action ? false : (bell ?? isTabRoot);
  const resolvedBellCount = bellCount ?? unread.data?.count ?? 0;
  const isOrdersRootScreen = pathname === "/sp/orders";
  const screenClassName = pathname.startsWith("/sp/orders") && !isOrdersRootScreen
    ? "sp-screen sp-screen--orders"
    : "sp-screen";
  const screenChildren = Children.toArray(children);
  const footerActions = screenChildren.filter((child) => isValidElement(child) && child.type === SpStickyFooter);
  const scrollChildren = screenChildren.filter((child) => !isValidElement(child) || child.type !== SpStickyFooter);

  return (
    <section className={screenClassName}>
      <TopAppBar
        title={title}
        onBack={showBack ? () => router.back() : undefined}
        onBell={showBell ? () => router.push("/sp/notifications") : undefined}
        bellCount={showBell ? resolvedBellCount : undefined}
        action={action}
        variant={appBarVariant}
      />
      {offline ? <OfflineBanner onRetry={() => router.refresh()} /> : null}
      {toolbar}
      <div className="sp-scroll">{scrollChildren}</div>
      {footerActions}
      {bottomAction ? <div className="sp-bottom-action">{bottomAction}</div> : null}
    </section>
  );
}

export function SpBottomNavigation() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <BottomNav
      active={activeTab(pathname)}
      onNav={(tab) => router.push(TAB_ROUTES[tab] ?? "/sp")}
    />
  );
}

export function SpSectionLabel({ children }: { children: ReactNode }) {
  return <p className="sp-section-label hb-heading">{children}</p>;
}

export function SpCard({
  children,
  padded = true,
  style,
}: {
  children: ReactNode;
  padded?: boolean;
  style?: CSSProperties;
}) {
  return (
    <div className="sp-card sp-enter" style={style}>
      {padded ? <div className="sp-card-body">{children}</div> : children}
    </div>
  );
}

export function StatusHistory({
  steps,
  historyKey,
}: {
  steps: StatusHistoryStep[];
  historyKey?: string | number;
}) {
  return (
    <div>
      <SpSectionLabel>Status history</SpSectionLabel>
      <SpCard>
        <ApprovalTimeline key={historyKey} steps={steps} />
      </SpCard>
    </div>
  );
}

export function SpStickyFooter({ children }: { children: ReactNode }) {
  return <div className="sp-sticky-footer">{children}</div>;
}

export function SpProgressBar({ value }: { value: number }) {
  return (
    <div className="sp-progress" aria-label={`${value}% complete`}>
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function SpProcessProgress({
  steps,
  activeStep,
  layout = "inline",
  showCurrentLabel = true,
  onStepSelect,
  canSelectStep,
}: {
  steps: string[];
  activeStep: number;
  layout?: "inline" | "toolbar";
  showCurrentLabel?: boolean;
  onStepSelect?: (step: number) => void;
  canSelectStep?: (step: number) => boolean;
}) {
  if (!steps.length) return null;
  const currentIndex = Math.min(Math.max(activeStep, 0), steps.length - 1);
  const summaryLabel = steps[currentIndex] ?? "Progress";
  const percent = ((currentIndex + 1) / steps.length) * 100;

  return (
    <div className={`sp-process-progress${layout === "toolbar" ? " sp-process-progress--toolbar" : ""}`}>
      <div className="sp-process-progress__head">
        <span className="sp-process-progress__step">
          Step {currentIndex + 1} of {steps.length}{showCurrentLabel ? ` · ${summaryLabel}` : ""}
        </span>
      </div>
      <div className="sp-process-progress__segments" aria-label={`${percent.toFixed(0)}% complete`}>
        {steps.map((label, index) => {
          const reached = index <= currentIndex;
          const key = `${label}-${index}`;
          if (!onStepSelect) {
            return (
              <span
                key={key}
                className="sp-process-progress__segment"
                data-active={reached}
                aria-current={index === currentIndex ? "step" : undefined}
              />
            );
          }
          const disabled = canSelectStep ? !canSelectStep(index) : false;
          return (
            <button
              key={key}
              type="button"
              className="sp-process-progress__segment sp-process-progress__segment-button"
              data-active={reached}
              aria-current={index === currentIndex ? "step" : undefined}
              aria-label={`Step ${index + 1}: ${label}`}
              disabled={disabled}
              onClick={() => {
                if (!disabled) onStepSelect(index);
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

export function SpStatusRow({
  label,
  value,
  tone,
  labelClassName = "sp-copy",
  valueClassName = "sp-body-strong--sm",
  valueAlign = "left",
  columns = "minmax(calc(var(--space-sm) * 11), 40%) minmax(0, 1fr)",
}: {
  label: ReactNode;
  value: ReactNode;
  tone?: string;
  labelClassName?: string;
  valueClassName?: string;
  valueAlign?: CSSProperties["textAlign"];
  columns?: CSSProperties["gridTemplateColumns"];
}) {
  return (
    <div
      className="sp-row"
      style={{
        alignItems: "flex-start",
        display: "grid",
        gridTemplateColumns: columns,
      }}
    >
      <span className={labelClassName} style={{ overflowWrap: "anywhere" }}>{label}</span>
      <strong className={valueClassName} style={{ color: tone ?? "var(--color-text-primary)", overflowWrap: "anywhere", textAlign: valueAlign }}>
        {value}
      </strong>
    </div>
  );
}

export function SpMetricStat({
  value,
  label,
  tone,
  emphasis = "h2",
  align = "center",
}: {
  value: ReactNode;
  label: ReactNode;
  tone?: string;
  emphasis?: "h2" | "h1" | "display";
  align?: CSSProperties["textAlign"];
}) {
  const metricClassName = emphasis === "display"
    ? "sp-metric-value sp-metric-value--display"
    : emphasis === "h1"
      ? "sp-metric-value sp-metric-value--h1"
      : "sp-metric-value";

  return (
    <div style={{ textAlign: align }}>
      <strong className={metricClassName} style={tone ? { color: tone } : undefined}>{value}</strong>
      <p className="sp-meta">{label}</p>
    </div>
  );
}

export function SpActionTile({
  icon,
  title,
  description,
  active,
  onClick,
}: {
  icon: string;
  title: string;
  description?: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button className="sp-action-tile" data-active={active} onClick={onClick} type="button">
      <IconSurface
        name={icon}
        size="metric"
        shape="soft-square"
        tone="primary"
        color={active ? "currentColor" : "var(--color-text-placeholder)"}
        style={active ? { background: "color-mix(in srgb, white 16%, transparent)", borderColor: "transparent", boxShadow: "none" } : undefined}
      />
      <strong className="hb-heading">{title}</strong>
      {description ? <span className="sp-meta">{description}</span> : null}
    </button>
  );
}

export function SpInlineAlert({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "warning" | "error";
}) {
  const icon = tone === "error" ? "Warning" : "InfoFilled";
  return (
    <div className="sp-inline-alert" data-tone={tone}>
      <Icon name={icon} size={18} color="currentColor" />
      <span>{children}</span>
    </div>
  );
}
