"use client";

import { BottomNav, Icon, IconSurface, OfflineBanner, TopAppBar } from "humbee-design-system";
import humbeeLogo from "humbee-design-system/assets/humbee_go_logo.svg";
import Image from "next/image";
import type { ReactNode } from "react";
import { useUnreadNotificationCount } from "@/src/features/approvals/hooks";
import { useManagementRole, useManagementRouter } from "./role-context";
import type { ManagementView } from "./service";
import styles from "./management.module.css";

const managerTabs = [
  { id: "dashboard", label: "Dashboard", icon: "Dashboard", activeIcon: "Dashboard" },
  { id: "reports", label: "Coverage", icon: "Map", activeIcon: "Map" },
  { id: "approvals", label: "Approvals", icon: "CheckCircle", activeIcon: "CheckCircle" },
  { id: "team", label: "Team", icon: "PersonRounded", activeIcon: "PersonRounded" },
  { id: "more", label: "More", icon: "Menu", activeIcon: "Menu" },
];

const adminTabs = [
  { id: "dashboard", label: "Dashboard", icon: "Dashboard", activeIcon: "Dashboard" },
  { id: "org", label: "Org", icon: "AccountTree", activeIcon: "AccountTree" },
  { id: "approvals", label: "Oversight", icon: "CheckCircle", activeIcon: "CheckCircle" },
  { id: "reports", label: "Coverage", icon: "Map", activeIcon: "Map" },
  { id: "more", label: "More", icon: "Menu", activeIcon: "Menu" },
];

export const viewTitles: Record<ManagementView, string> = {
  dashboard: "Dashboard",
  "dashboard-drill": "Orders",
  approvals: "Approvals",
  "approval-detail": "Approval",
  team: "Team",
  "team-day": "Day timeline",
  employees: "Employees",
  employee: "Employee",
  "employee-add": "Add employee",
  "employee-edit": "Edit employee",
  "org-tree": "Organization",
  hierarchy: "Move in hierarchy",
  geography: "Geography scope",
  profile: "My profile",
  "combined-visits": "Combined visits",
  "combined-visit-sales-person": "Choose sales person",
  "combined-visit-beat": "Choose beat",
  "combined-visit-outlet": "Choose outlet",
  "combined-visit-day": "Choose day",
  "visit-feedback": "Visit feedback",
  coverage: "Team coverage",
  attendance: "Attendance",
  order: "Order",
  leave: "Team leave",
  "my-leave": "Leave",
  "leave-apply": "Apply leave",
  "leave-detail": "Leave request",
  targets: "Targets",
  "target-edit": "Set target",
  "team-performance": "Team performance",
  beats: "Beat management",
  "admin-reports": "Reports",
  notifications: "Notifications",
  more: "More",
  "missed-visits": "Missed visits",
};

const routeForTab: Record<string, string> = {
  dashboard: "/mgmt",
  team: "/mgmt/team",
  org: "/mgmt/org-tree",
  employees: "/mgmt/employees",
  approvals: "/mgmt/approvals",
  reports: "/mgmt/coverage",
  more: "/mgmt/more",
};

function activeTab(view: ManagementView, isAdmin: boolean) {
  if (view === "dashboard" || view === "dashboard-drill" || view === "team-performance") return "dashboard";
  if (view === "approvals" || view === "approval-detail") return "approvals";
  if (view === "more" || view === "notifications" || view === "profile" || view === "my-leave" || view === "leave-apply" || view === "leave-detail") return "more";
  if (["team", "team-day", "combined-visits", "combined-visit-sales-person", "combined-visit-beat", "combined-visit-outlet", "combined-visit-day", "visit-feedback"].includes(view)) return isAdmin ? "org" : "team";
  if (view === "org-tree" || view === "hierarchy") return isAdmin ? "org" : "team";
  if (["employees", "employee", "employee-add", "employee-edit", "geography"].includes(view)) return isAdmin ? "org" : "team";
  return "reports";
}

const MANAGER_TAB_ROOTS = new Set<ManagementView>(["dashboard", "team", "approvals", "coverage", "more"]);
const ADMIN_TAB_ROOTS = new Set<ManagementView>(["dashboard", "org-tree", "approvals", "coverage", "more"]);

function isTabRoot(view: ManagementView, isAdmin: boolean) {
  return (isAdmin ? ADMIN_TAB_ROOTS : MANAGER_TAB_ROOTS).has(view);
}

function DesktopTopNav({
  tabs,
  active,
  onNav,
}: {
  tabs: typeof managerTabs;
  active: string;
  onNav: (tab: string) => void;
}) {
  return (
    <nav aria-label="Primary" className={styles.desktopNav}>
      <button type="button" className={styles.desktopNavBrand} aria-label="Humbee home" onClick={() => onNav("dashboard")}>
        <Image src={humbeeLogo} alt="" height={28} />
      </button>
      {tabs.map((tab) => {
        const on = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            className={`${styles.desktopNavItem}${on ? ` ${styles.desktopNavItemActive}` : ""}`}
            aria-current={on ? "page" : undefined}
            onClick={() => onNav(tab.id)}
          >
            <Icon name={on ? tab.activeIcon : tab.icon} size={20} color="currentColor" />
            <span>{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

export function ManagementScreen({
  view,
  children,
  footer,
  title,
  action,
  offline,
  onBack,
}: {
  view: ManagementView;
  children: ReactNode;
  footer?: ReactNode;
  title?: string;
  action?: ReactNode;
  offline?: boolean;
  onBack?: () => void;
}) {
  const router = useManagementRouter();
  const { isAdmin } = useManagementRole();
  const unread = useUnreadNotificationCount();
  const tabs = isAdmin ? adminTabs : managerTabs;
  const heading = title ?? (view === "dashboard" ? `${isAdmin ? "Admin" : "Manager"} dashboard` : viewTitles[view]);
  const showBack = !isTabRoot(view, isAdmin);
  const showBell = view !== "notifications";
  return (
    <div className={styles.background}>
      <section className={styles.shell}>
        <DesktopTopNav tabs={tabs} active={activeTab(view, isAdmin)} onNav={(tab) => router.push(routeForTab[tab] ?? "/mgmt")} />
        <TopAppBar
          title={heading}
          onBack={onBack ?? (showBack ? () => router.back() : undefined)}
          onBell={showBell ? () => router.push("/mgmt/notifications") : undefined}
          bellCount={showBell ? unread.data?.count ?? 0 : undefined}
          action={action}
        />
        {offline ? <OfflineBanner onRetry={() => router.refresh()} /> : null}
        <main className={styles.scroll}>
          <div className={`sp-view-swap ${styles.viewBody}`} key={view}>{children}</div>
        </main>
        {footer ? <footer className={styles.footer}>{footer}</footer> : null}
        <BottomNav active={activeTab(view, isAdmin)} tabs={tabs} onNav={(tab) => router.push(routeForTab[tab] ?? "/mgmt")} />
      </section>
    </div>
  );
}

export function Section({ label, children }: { label: string; children: ReactNode }) {
  return <section className={styles.section}><p className={`${styles.sectionLabel} hb-heading`}>{label}</p>{children}</section>;
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warning" | "success" | "error" }) {
  const icon = tone === "success" ? "CheckCircle" : tone === "warning" || tone === "error" ? "Warning" : "InfoFilled";
  return <div className={`${styles.notice} ${tone === "warning" ? styles.warning : ""} ${tone === "success" ? styles.success : ""} ${tone === "error" ? styles.error : ""}`}><Icon name={icon} size={18} color="currentColor" /><span>{children}</span></div>;
}

export function ManagementMetric({
  value,
  label,
  tone,
  emphasis = "h2",
}: {
  value: ReactNode;
  label: ReactNode;
  tone?: string;
  emphasis?: "h2" | "h1";
}) {
  const metricClassName = emphasis === "h1"
    ? "sp-metric-value sp-metric-value--h1"
    : "sp-metric-value";

  return (
    <div className={styles.summary}>
      <strong className={metricClassName} style={tone ? { color: tone } : undefined}>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

export function SummaryGrid({ items }: { items: Array<[string, string, string?]> }) {
  return <div className={styles.summaryGrid}>{items.map(([value, label, tone]) => <ManagementMetric key={label} value={value} label={label} tone={tone} />)}</div>;
}

export function DataRow({
  icon,
  initials,
  title,
  subtitle,
  trailing,
  onClick,
  destructive = false,
  selected = false,
  chevron = true,
}: {
  icon?: string;
  initials?: string;
  title: string;
  subtitle?: string;
  trailing?: ReactNode;
  onClick?: () => void;
  destructive?: boolean;
  selected?: boolean;
  chevron?: boolean;
}) {
  const iconColor = destructive ? "var(--color-error)" : "var(--color-primary)";
  const leading = icon
    ? <IconSurface name={icon} size="metric" shape="soft-square" tone={destructive ? "error" : "primary"} color={iconColor} />
    : initials
      ? <span className={styles.avatar}>{initials}</span>
      : null;
  const content = <>{leading}<span className={styles.rowCopy}><strong className="hb-heading">{title}</strong>{subtitle ? <span>{subtitle}</span> : null}</span>{trailing}{onClick && chevron ? <Icon name="KeyboardArrowRight" size={20} color="var(--color-text-placeholder)" /> : null}</>;
  const className = `${styles.row}${selected ? ` ${styles.rowSelected}` : ""}`;
  return onClick ? <button className={className} onClick={onClick} type="button">{content}</button> : <div className={className}>{content}</div>;
}
