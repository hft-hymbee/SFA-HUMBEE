import { leaveTypeMeta } from "./service";

export type LeaveStatusTone = "pending" | "approved" | "partially-completed" | "cancelled" | "default";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  approved: "Approved",
  approved_with_edits: "Edited",
  auto_approved: "Auto-approved",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  expired: "Expired",
};

export function leaveChipStatus(status: string): LeaveStatusTone {
  if (["rejected", "withdrawn", "expired"].includes(status)) return "cancelled";
  if (status === "auto_approved") return "approved";
  if (status === "approved_with_edits") return "partially-completed";
  if (status === "pending" || status === "approved") return status;
  return "default";
}

export function leaveStatusLabel(status: string) {
  return STATUS_LABELS[status] ?? "Unavailable";
}

export function formatLeaveDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(`${value}T00:00:00+05:30`));
}

export function leaveDateRange(from: string, to: string) {
  return from === to ? formatLeaveDate(from) : `${formatLeaveDate(from)} – ${formatLeaveDate(to)}`;
}

export function dayLabel(count: number) {
  if (count === 0.5) return "Half day";
  return Math.abs(count) === 1 ? `${count} day` : `${count} days`;
}

// A balance is a quantity, never a duration: 0.5 left is "0.5 days", not "Half day".
export function balanceLabel(days: number) {
  const value = Number(days.toFixed(1));
  return Math.abs(value) === 1 ? `${value} day` : `${value} days`;
}

export const MAX_LEAVE_DAYS = 364;

export function leaveSpanDays(from: string, to: string) {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000) + 1;
}

export function leaveTypeLabel(leaveType: string) {
  return leaveTypeMeta(leaveType).shortLabel;
}

// Auto-approval only ever happens at the top of the hierarchy, so the suffix is
// derived from the status rather than stored as prose.
export function leaveRoutingSuffix(status: string) {
  return status === "auto_approved" ? " · highest level" : "";
}
