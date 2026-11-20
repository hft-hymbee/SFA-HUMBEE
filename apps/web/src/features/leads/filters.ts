export type LeadDateRange = "all" | "month" | "30" | "custom";

export interface LeadFilters {
  q: string;
  range: LeadDateRange;
  from: string;
  to: string;
  /** Empty string means all employees. */
  employeeId: string;
}

export const DEFAULT_LEAD_FILTERS: LeadFilters = {
  q: "",
  range: "all",
  from: "",
  to: "",
  employeeId: "",
};

const RANGES: readonly LeadDateRange[] = ["all", "month", "30", "custom"];

function isRange(value: string | null): value is LeadDateRange {
  return RANGES.includes(value as LeadDateRange);
}

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** True for a real calendar date written as `YYYY-MM-DD` (rejects e.g. 2026-02-30). */
export function isLeadIsoDate(value: string): boolean {
  const match = ISO_DATE.exec(value);
  if (!match) return false;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(year, month - 1, day);
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
}

export function leadFiltersFromSearchParams(params: URLSearchParams): LeadFilters {
  const rawRange = params.get("range");
  const range = isRange(rawRange) ? rawRange : DEFAULT_LEAD_FILTERS.range;
  const date = (key: "from" | "to") => {
    const value = params.get(key) ?? "";
    return range === "custom" && isLeadIsoDate(value) ? value : "";
  };
  const from = date("from");
  let to = date("to");
  if (from && to && from > to) to = "";
  return {
    q: params.get("q") ?? DEFAULT_LEAD_FILTERS.q,
    range,
    from,
    to,
    employeeId: params.get("emp") ?? DEFAULT_LEAD_FILTERS.employeeId,
  };
}

export function leadFiltersToSearchParams(f: LeadFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (f.q !== DEFAULT_LEAD_FILTERS.q) params.set("q", f.q);
  if (f.range !== DEFAULT_LEAD_FILTERS.range) params.set("range", f.range);
  if (f.from !== DEFAULT_LEAD_FILTERS.from) params.set("from", f.from);
  if (f.to !== DEFAULT_LEAD_FILTERS.to) params.set("to", f.to);
  if (f.employeeId !== DEFAULT_LEAD_FILTERS.employeeId) params.set("emp", f.employeeId);
  return params;
}

/** Local calendar date as `YYYY-MM-DD`. */
export function leadIsoDate(date: Date): string {
  const y = String(date.getFullYear()).padStart(4, "0");
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function resolveLeadDateWindow(
  f: LeadFilters,
  today: Date,
): { from?: string; to?: string } {
  switch (f.range) {
    case "month":
      return {
        from: leadIsoDate(new Date(today.getFullYear(), today.getMonth(), 1)),
        to: leadIsoDate(today),
      };
    case "30":
      return {
        from: leadIsoDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 29)),
        to: leadIsoDate(today),
      };
    case "custom":
      return {
        ...(f.from ? { from: f.from } : {}),
        ...(f.to ? { to: f.to } : {}),
      };
    default:
      return {};
  }
}

export function hasActiveLeadFilters(f: LeadFilters): boolean {
  return (
    f.q.trim() !== "" ||
    f.range !== DEFAULT_LEAD_FILTERS.range ||
    f.employeeId !== ""
  );
}
