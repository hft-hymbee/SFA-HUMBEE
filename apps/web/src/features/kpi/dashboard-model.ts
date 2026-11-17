import type {
  AdminDashboardKpisResponse,
  CoverageRow,
  ManagerDashboardKpisResponse,
  ManufacturerOut,
  SpDashboardKpisResponse,
  TargetBasis,
  TargetOut,
} from "@humbee/api-contract";
import { formatTargetValue } from "@/src/features/targets/service";

type SpDashboardMetrics = SpDashboardKpisResponse["metrics"];
type ManagerDashboardMetrics = ManagerDashboardKpisResponse["team_metrics"];
type AdminDashboardMetrics = AdminDashboardKpisResponse["org_metrics"];

export type VisitWindow = "today" | "mtd";

export type VisitSplitPart = {
  color: string;
  label: string;
  value: number;
};

export type VisitModel = {
  coverage: string | null;
  distance: string | null;
  lines: string | null;
  noOrder: number | null;
  orders: string | null;
  planned: number | null;
  productive: number | null;
  productivity: string | null;
  still: number | null;
  tc: string | null;
  pc: string | null;
  utc: string | null;
  zo: string | null;
  unique: string | null;
  unplanned: number | null;
  visited: number | null;
};

export type ManufacturerRow = {
  basis: TargetBasis;
  hasTarget: boolean;
  id: string;
  name: string;
  targetLabel: string;
  targetValue: number | null;
  unit: string;
};

export type RosterStatus = "leave" | "none" | "punch" | "visiting" | "waiting";

export type RosterPerson = {
  id: string;
  initials: string;
  name: string;
  status: RosterStatus;
};

const ROSTER_TONES: Record<RosterStatus, { bg: string; ink: string; pip: string }> = {
  leave: { bg: "color-mix(in srgb, var(--info) 10%, transparent)", ink: "var(--info)", pip: "var(--info)" },
  none: { bg: "var(--n-100)", ink: "var(--ink-2)", pip: "var(--ink-2)" },
  punch: { bg: "var(--n-100)", ink: "var(--ink-3)", pip: "var(--ink-4)" },
  visiting: { bg: "var(--success-surface)", ink: "var(--success)", pip: "var(--success)" },
  waiting: { bg: "var(--warning-surface)", ink: "var(--gated-ink)", pip: "var(--accent-active)" },
};

export function formatKpiDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
    weekday: "short",
  }).format(new Date(value.includes("T") ? value : `${value}T12:00:00+05:30`));
}

export function formatMonthLabel(value: string | null | undefined) {
  if (!value) return "This month";
  return new Intl.DateTimeFormat("en-GB", {
    month: "long",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value.includes("T") ? value : `${value}T12:00:00+05:30`));
}

export function formatMonthShort(value: string | null | undefined) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value.includes("T") ? value : `${value}T12:00:00+05:30`));
}

export function previousMonthLabel(value: string | null | undefined, month: "long" | "short" = "long") {
  if (!value) return "last month";
  const date = new Date(value.includes("T") ? value : `${value}T12:00:00+05:30`);
  if (Number.isNaN(date.getTime())) return "last month";
  date.setDate(1);
  date.setMonth(date.getMonth() - 1);
  return new Intl.DateTimeFormat("en-GB", {
    month,
    timeZone: "Asia/Kolkata",
  }).format(date);
}

export function formatManufacturerQuantity(value: number, basis: TargetBasis) {
  return formatTargetValue(value, basis);
}

export function requiredDailyRateLabel(
  remainingValue: number | null,
  daysLeft: number | null,
  basis: TargetBasis | null,
  unit?: string,
) {
  if (remainingValue === null || remainingValue <= 0 || daysLeft === null) return null;
  const perDay = remainingValue / Math.max(daysLeft, 1);
  if (basis === "amount") return `${formatTargetValue(Math.round(perDay), "amount")}/day`;
  const rounded = Math.round(perDay * 10) / 10;
  const qty = rounded.toLocaleString("en-IN", { maximumFractionDigits: 1 });
  return unit && unit !== "—" ? `${qty} ${unit}/day` : `${qty}/day`;
}

export function periodMonthFromBusinessDate(value: string | null | undefined) {
  if (!value || value.length < 7) return "";
  return `${value.slice(0, 7)}-01`;
}

function workingDaysOfMonth(businessDate: string | null | undefined) {
  if (!businessDate) return null;
  const date = new Date(`${businessDate}T12:00:00+05:30`);
  if (Number.isNaN(date.getTime())) return null;
  const today = date.getDate();
  const last = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
  let elapsed = 0;
  let total = 0;
  for (let day = 1; day <= last; day += 1) {
    if (new Date(date.getFullYear(), date.getMonth(), day).getDay() === 0) continue;
    total += 1;
    if (day <= today) elapsed += 1;
  }
  return { elapsed, total };
}

export function workingDaysLeft(businessDate: string | null | undefined) {
  const days = workingDaysOfMonth(businessDate);
  return days ? days.total - days.elapsed : null;
}

export function monthPacePct(businessDate: string | null | undefined) {
  const days = workingDaysOfMonth(businessDate);
  return days?.total ? Math.round((100 * days.elapsed) / days.total) : null;
}

export function monthDayProgress(businessDate: string | null | undefined) {
  if (!businessDate) return null;
  const date = new Date(`${businessDate}T12:00:00+05:30`);
  if (Number.isNaN(date.getTime())) return null;
  const day = date.getDate();
  const total = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
  return { day, total };
}

export function toInNumber(value: number) {
  return value.toLocaleString("en-IN");
}

export function moneyFromPaise(paise: number) {
  const rupees = Math.round(paise / 100);
  if (!rupees) return "₹ 0";
  if (rupees >= 100000) return `₹ ${(rupees / 100000).toFixed(1).replace(/\.0$/, "")}L`;
  if (rupees >= 1000) return `₹ ${(rupees / 1000).toFixed(1).replace(/\.0$/, "")}K`;
  return new Intl.NumberFormat("en-IN", {
    currency: "INR",
    maximumFractionDigits: 0,
    style: "currency",
  }).format(rupees);
}

export function shortDisplayName(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length < 2) return name.trim();
  const first = parts[0] ?? "";
  const last = parts[parts.length - 1] ?? "";
  if (!first || !last) return name.trim();
  const initial = first.endsWith(".") ? first : `${first.slice(0, 1)}.`;
  return `${initial} ${last}`;
}

export function leagueBarFill(pct: number | null | undefined) {
  if (pct == null) return "transparent";
  if (pct >= 70) return "var(--league-on)";
  if (pct >= 50) return "var(--league-behind)";
  return "var(--league-risk)";
}

export type ProgressBar = { taken: number; target: number | null };

function highestTarget(bars: ProgressBar[]) {
  return bars.reduce((max, bar) => (bar.target != null && bar.target > max ? bar.target : max), 0);
}

function highestTaken(bars: ProgressBar[]) {
  return bars.reduce((max, bar) => Math.max(max, bar.taken), 0);
}

/**
 * Shared axis for a group of progress bars. The track ends at the larger of the highest
 * month target and the highest order placed, so each target tick stays on the scale and an
 * order past every target still fits.
 */
export function progressScale(bars: ProgressBar[]) {
  return Math.max(1, highestTarget(bars), highestTaken(bars));
}

/**
 * Percentage used to color a bar. A bar with its own achievement uses that. A bar with no
 * personal target is measured against the group's highest target, or against the highest
 * order when the group has no target.
 */
export function progressColorBaseline(bars: ProgressBar[]) {
  const target = highestTarget(bars);
  if (target > 0) return target;
  return Math.max(1, highestTaken(bars));
}

export function progressColorPct(bar: ProgressBar, pct: number | null, baseline: number) {
  if (pct != null) return pct;
  if (baseline <= 0) return 0;
  return (bar.taken / baseline) * 100;
}

export function initialsFromName(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0] ?? "";
  const last = parts.at(-1) ?? "";
  if (!first) return "—";
  if (parts.length === 1) return first.slice(0, 2).toUpperCase();
  return `${first[0] ?? ""}${last[0] ?? ""}`.toUpperCase();
}

export function rosterTone(status: RosterStatus) {
  return ROSTER_TONES[status];
}

function emptyVisitModel(): VisitModel {
  return {
    coverage: null,
    distance: null,
    lines: null,
    noOrder: null,
    orders: null,
    planned: null,
    productive: null,
    productivity: null,
    still: null,
    tc: null,
    pc: null,
    utc: null,
    zo: null,
    unique: null,
    unplanned: null,
    visited: null,
  };
}

export function visitModelFromMetrics(
  metrics: SpDashboardMetrics | ManagerDashboardMetrics | AdminDashboardMetrics | null | undefined,
  window: VisitWindow,
): VisitModel {
  if (!metrics) return finalizeVisitModel(emptyVisitModel());

  const plannedVisits = "planned_visits" in metrics ? metrics.planned_visits : undefined;
  const metres = "distance_metres" in metrics ? metrics.distance_metres : null;
  const unique = "utc" in metrics
    ? toInNumber(metrics.utc)
    : "unique_outlets" in metrics && metrics.unique_outlets != null
      ? toInNumber(metrics.unique_outlets)
      : null;

  return finalizeVisitModel({
    coverage: "coverage_pct" in metrics && metrics.coverage_pct != null
      ? `${metrics.coverage_pct}%`
      : null,
    distance: metres != null && metres > 0
      ? `${toInNumber(Math.round(metres / 1000))} km`
      : null,
    lines: "order_lines_count" in metrics
      ? `${toInNumber(metrics.order_lines_count)} ${metrics.order_lines_count === 1 ? "line" : "lines"}`
      : null,
    noOrder: null,
    orders: "orders_submitted" in metrics ? toInNumber(metrics.orders_submitted) : null,
    planned: window === "today" && plannedVisits != null && plannedVisits > 0 ? plannedVisits : null,
    productive: metrics.productive_visits,
    productivity: metrics.visits_total > 0 && "productivity_pct" in metrics && metrics.productivity_pct != null
      ? `${metrics.productivity_pct}%`
      : null,
    still: null,
    tc: toInNumber(metrics.visits_total),
    pc: toInNumber(metrics.productive_visits),
    utc: "utc" in metrics ? toInNumber(metrics.utc) : null,
    zo: "zo" in metrics ? toInNumber(metrics.zo) : null,
    unique,
    unplanned: "unplanned_visits" in metrics ? metrics.unplanned_visits : null,
    visited: metrics.visits_total,
  });
}

export function visitSplitParts(model: VisitModel, includeEmpty = false): VisitSplitPart[] {
  const parts: VisitSplitPart[] = [];
  if (model.productive !== null) {
    parts.push({ color: "var(--primary)", label: "Ordered", value: model.productive });
  }
  if (model.noOrder !== null) {
    parts.push({ color: "var(--primary-light)", label: "No order", value: model.noOrder });
  }
  if (model.still !== null) {
    parts.push({ color: "var(--n-200)", label: "Still to go", value: model.still });
  }
  return includeEmpty ? parts : parts.filter((part) => part.value > 0);
}

export function visitHasValues(model: VisitModel) {
  return model.planned !== null || model.visited !== null || model.productive !== null;
}

export function finalizeVisitModel(model: VisitModel): VisitModel {
  const noOrder = model.noOrder ?? (
    model.visited !== null && model.productive !== null
      ? Math.max(0, model.visited - model.productive)
      : null
  );
  const still = model.still ?? (
    model.planned !== null && model.visited !== null
      ? Math.max(0, model.planned - model.visited)
      : null
  );
  const productivity = model.productivity ?? (
    model.visited !== null && model.visited > 0 && model.productive !== null
      ? `${Math.round((100 * model.productive) / model.visited)}%`
      : null
  );
  return { ...model, noOrder, still, productivity };
}

export function spRollupOrderValueLabel(metrics?: SpDashboardMetrics | null): string | null {
  if (!metrics || metrics.order_value_paise == null) return null;
  return moneyFromPaise(metrics.order_value_paise);
}

export function spRollupOrderVolumeLabel(metrics?: SpDashboardMetrics | null): string | null {
  if (
    !metrics
    || metrics.order_volume_units == null
    || !metrics.order_volume_uom
  ) return null;
  return `${toInNumber(metrics.order_volume_units)} ${metrics.order_volume_uom}`;
}

export function manufacturerRows(manufacturers: ManufacturerOut[] | undefined, targets: TargetOut[] | undefined): ManufacturerRow[] {
  const salesTarget = (targets ?? []).find((target) => target.target_type === "sales" && target.status === "active");
  const lines = new Map((salesTarget?.lines ?? []).map((line) => [line.manufacturer_id, line]));
  const source = manufacturers?.length
    ? manufacturers
    : (salesTarget?.lines ?? []).map((line) => ({
      basis: line.line_basis,
      display_label: line.manufacturer_label,
      manufacturer_id: line.manufacturer_id,
      uom_label: line.uom_label,
    }));

  return source.map((item) => {
    const line = lines.get(item.manufacturer_id);
    const basis = line?.line_basis ?? item.basis;
    const unit = line?.uom_label ?? item.uom_label;
    const targetLabel = line
      ? line.line_basis === "amount"
        ? formatTargetValue(line.line_value, "amount")
        : `${formatTargetValue(line.line_value, "volume")} ${line.uom_label}`
      : "No target set";
    return {
      basis,
      hasTarget: Boolean(line),
      id: item.manufacturer_id,
      name: item.display_label,
      targetLabel,
      targetValue: line?.line_value ?? null,
      unit,
    };
  });
}

export function rosterFromCoverage(rows: CoverageRow[] | undefined): RosterPerson[] {
  return (rows ?? []).map((row) => {
    const punchedIn = Boolean(row.punched_in_at);
    let status: RosterStatus = "punch";
    if (row.on_leave) status = "leave";
    else if (row.on_duty && row.visited > 0) status = "visiting";
    else if (row.on_duty) status = "waiting";
    else if (!punchedIn) status = "punch";
    else status = "none";
    return {
      id: row.employee_id,
      initials: initialsFromName(row.employee_name),
      name: row.employee_name,
      status,
    };
  });
}

export function rosterCounts(people: RosterPerson[]) {
  const counts: Record<RosterStatus, number> = { leave: 0, none: 0, punch: 0, visiting: 0, waiting: 0 };
  for (const person of people) counts[person.status] += 1;
  return counts;
}
