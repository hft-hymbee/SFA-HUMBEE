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

export function leadFiltersFromSearchParams(params: URLSearchParams): LeadFilters {
  const range = params.get("range");
  return {
    q: params.get("q") ?? DEFAULT_LEAD_FILTERS.q,
    range: isRange(range) ? range : DEFAULT_LEAD_FILTERS.range,
    from: params.get("from") ?? DEFAULT_LEAD_FILTERS.from,
    to: params.get("to") ?? DEFAULT_LEAD_FILTERS.to,
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

function isoLocal(date: Date): string {
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
        from: isoLocal(new Date(today.getFullYear(), today.getMonth(), 1)),
        to: isoLocal(today),
      };
    case "30":
      return {
        from: isoLocal(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 29)),
        to: isoLocal(today),
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
