import {
  createTargetApiV1TargetsPost,
  getTargetApiV1TargetsTargetIdGet,
  listManufacturersApiV1MastersManufacturersGet,
  listRosterApiV1TargetsRosterGet,
  listTargetsApiV1TargetsGet,
  removeTargetApiV1TargetsTargetIdDelete,
  updateTargetApiV1TargetsTargetIdPut,
  type CreateTargetBody,
  type ManufacturerOut,
  type ManufacturerRosterResponse,
  type RemoveTargetResponse,
  type TargetBasis,
  type TargetLineOut,
  type TargetListResponse,
  type TargetOut,
  type TargetRosterResponse,
  type TargetType,
  type UpdateTargetBody,
} from "@humbee/api-contract";
import {
  createIdempotencyKey,
  getBrowserApiClient,
  idempotencyHeaders,
} from "@/src/shared/api";

export type {
  CreateTargetBody,
  ManufacturerOut,
  ManufacturerRosterResponse,
  OutletCategoryScope,
  RemoveTargetResponse,
  TargetBasis,
  TargetLineBody,
  TargetLineOut,
  TargetListResponse,
  TargetOut,
  TargetRosterMember,
  TargetRosterResponse,
  TargetStatus,
  TargetType,
  UpdateTargetBody,
} from "@humbee/api-contract";

export interface TargetListInput {
  employeeId: string;
  periodMonth: string;
  targetType?: TargetType | null;
}

export interface UpdateTargetInput {
  targetId: string;
  body: UpdateTargetBody;
  idempotencyKey?: string;
}

export interface RemoveTargetInput {
  targetId: string;
  idempotencyKey?: string;
}

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function client() {
  return getBrowserApiClient();
}

export const TARGET_TYPE_LABELS: Record<TargetType, string> = {
  leads: "Leads",
  outlets: "New outlets",
  sales: "Sales target",
};

export const TARGET_BASIS_LABELS: Record<TargetBasis, string> = {
  amount: "Amount",
  volume: "Volume",
};

export type LiveTargetOut = TargetOut & {
  target_value_amount_paise?: number | null;
  target_value_volume_units?: number | null;
  lines: TargetLineOut[];
};

export function currentPeriodMonth(today = new Date()): string {
  const isoDate = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(today);
  return `${isoDate.slice(0, 7)}-01`;
}

export function nextPeriodMonth(periodMonth: string): string {
  const [year, month] = periodMonth.split("-").map(Number);
  if (!year || !month) return currentPeriodMonth();
  const next = new Date(year, month, 1);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-01`;
}

export function formatPeriodMonth(periodMonth: string): string {
  const [year, month] = periodMonth.split("-").map(Number);
  if (!year || !month) return periodMonth;
  return new Intl.DateTimeFormat("en-IN", {
    month: "long",
    year: "numeric",
  }).format(new Date(year, month - 1, 1));
}

export function formatTargetValue(value: number | null | undefined, basis?: TargetBasis | null): string {
  if (value === null || value === undefined) return "No target";
  if (basis === "amount") {
    return new Intl.NumberFormat("en-IN", {
      currency: "INR",
      maximumFractionDigits: 0,
      style: "currency",
    }).format(value / 100);
  }
  return new Intl.NumberFormat("en-IN").format(value);
}

export function formatSalesTargetSummary(target: TargetOut): string {
  const liveTarget = target as LiveTargetOut;
  const parts = [
    liveTarget.target_value_amount_paise === null || liveTarget.target_value_amount_paise === undefined
      ? null
      : formatTargetValue(liveTarget.target_value_amount_paise, "amount"),
    liveTarget.target_value_volume_units === null || liveTarget.target_value_volume_units === undefined
      ? null
      : `${formatTargetValue(liveTarget.target_value_volume_units, "volume")} Ton`,
  ].filter(Boolean);

  if (parts.length) return parts.join(" + ");
  return `${target.lines.length} manufacturer ${target.lines.length === 1 ? "line" : "lines"}`;
}

export function manufacturerUnitLabel(manufacturer: ManufacturerOut): string {
  return manufacturer.uom_label;
}

export function manufacturerBasis(manufacturer: ManufacturerOut): TargetBasis {
  return manufacturer.basis;
}

export const targetsService = {
  async listRoster(periodMonth: string, signal?: AbortSignal): Promise<TargetRosterResponse> {
    return unwrap(await listRosterApiV1TargetsRosterGet({
      client: client(),
      query: { period_month: periodMonth },
      signal,
      throwOnError: true,
    }));
  },

  async listTargets(input: TargetListInput, signal?: AbortSignal): Promise<TargetListResponse> {
    return unwrap(await listTargetsApiV1TargetsGet({
      client: client(),
      query: {
        employee_id: input.employeeId,
        period_month: input.periodMonth,
        type: input.targetType ?? undefined,
      },
      signal,
      throwOnError: true,
    }));
  },

  async getTarget(targetId: string, signal?: AbortSignal): Promise<TargetOut> {
    return unwrap(await getTargetApiV1TargetsTargetIdGet({
      client: client(),
      path: { target_id: targetId },
      signal,
      throwOnError: true,
    }));
  },

  async listManufacturers(signal?: AbortSignal): Promise<ManufacturerRosterResponse> {
    return unwrap(await listManufacturersApiV1MastersManufacturersGet({
      client: client(),
      signal,
      throwOnError: true,
    }));
  },

  async createTarget(body: CreateTargetBody, idempotencyKey = createIdempotencyKey()): Promise<TargetOut> {
    return unwrap(await createTargetApiV1TargetsPost({
      client: client(),
      body,
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },

  async updateTarget(input: UpdateTargetInput): Promise<TargetOut> {
    return unwrap(await updateTargetApiV1TargetsTargetIdPut({
      client: client(),
      path: { target_id: input.targetId },
      body: input.body,
      headers: idempotencyHeaders(input.idempotencyKey ?? createIdempotencyKey()),
      throwOnError: true,
    }));
  },

  async removeTarget(input: RemoveTargetInput): Promise<RemoveTargetResponse> {
    return unwrap(await removeTargetApiV1TargetsTargetIdDelete({
      client: client(),
      path: { target_id: input.targetId },
      headers: idempotencyHeaders(input.idempotencyKey ?? createIdempotencyKey()),
      throwOnError: true,
    }));
  },
};
