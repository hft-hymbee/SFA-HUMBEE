export type ManagementRole = "manager" | "admin";
export type ManagementView =
  | "dashboard"
  | "dashboard-drill"
  | "approvals"
  | "approval-detail"
  | "team"
  | "team-day"
  | "employees"
  | "employee"
  | "employee-add"
  | "employee-edit"
  | "org-tree"
  | "hierarchy"
  | "geography"
  | "combined-visits"
  | "combined-visit-sales-person"
  | "combined-visit-beat"
  | "combined-visit-outlet"
  | "combined-visit-day"
  | "visit-feedback"
  | "coverage"
  | "attendance"
  | "order"
  | "leave"
  | "my-leave"
  | "leave-apply"
  | "leave-detail"
  | "targets"
  | "target-edit"
  | "team-performance"
  | "beats"
  | "admin-reports"
  | "notifications"
  | "more"
  | "missed-visits"
  | "profile";

export type StatusTone = "pending" | "approved" | "verified" | "cancelled" | "default" | "partially-completed" | "not-verified";

export interface ApprovalRequest {
  id: string;
  kind: "order" | "beat" | "leave";
  title: string;
  subtitle: string;
  age: string;
  icon: string;
}

export const catalog: Record<string, any> = {};

export const managementViews: ManagementView[] = [
  "dashboard", "dashboard-drill", "approvals", "approval-detail", "team", "team-day",
  "employees", "employee", "employee-add", "employee-edit", "org-tree", "hierarchy", "geography",
  "combined-visits", "combined-visit-sales-person", "combined-visit-beat", "combined-visit-outlet", "combined-visit-day", "visit-feedback", "coverage", "attendance", "order", "leave",
  "my-leave", "leave-apply", "leave-detail",
  "targets", "target-edit", "team-performance", "beats", "admin-reports", "notifications", "more", "missed-visits",
  "profile",
];

export const employeeFilters = [
  "all",
  "sp",
  "mgr",
  "active",
  "inactive",
  "unassigned",
  "missing-manager",
  "missing-geography",
  "recent",
] as const;

export type EmployeeFilter = (typeof employeeFilters)[number];

export function isEmployeeFilter(value: string | null | undefined): value is EmployeeFilter {
  return !!value && (employeeFilters as readonly string[]).includes(value);
}

export function employeesHref(filter: EmployeeFilter = "all") {
  return filter === "all" ? "/mgmt/employees" : `/mgmt/employees?filter=${filter}`;
}

export function initialsFromName(name: string) {
  return name.split(" ").filter(Boolean).map((word) => word[0]).join("").slice(0, 2).toUpperCase();
}

export type DayScope = "today" | "yesterday" | "pick";

export function isManagementView(value: string): value is ManagementView {
  return managementViews.includes(value as ManagementView);
}
