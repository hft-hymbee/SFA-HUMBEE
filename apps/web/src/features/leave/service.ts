import {
  getMyBalancesApiV1LeaveBalancesMeGet,
  listMyRequestsApiV1LeaveRequestsMineGet,
  listTeamApiV1LeaveTeamGet,
  previewApiV1LeavePreviewGet,
  submitLeaveApiV1LeaveRequestsPost,
  type LeaveBalancesResponse,
  type LeavePreviewResponse,
  type LeaveRequestItem,
  type LeaveRequestListResponse,
  type SubmitLeaveBody,
  type TeamLeaveListResponse,
} from "@humbee/api-contract";
import {
  getBrowserApiClient,
  idempotencyHeaders,
} from "@/src/shared/api";

export type LeaveType = SubmitLeaveBody["leave_type"];
export type LeaveHistoryFilter = "all" | "pending" | "history";
export type TeamLeaveFilter = "all" | "pending" | "approved" | "auto_approved" | "rejected";
export type LeaveTypeTone = "info" | "error" | "success";

export const LEAVE_TYPES: Array<{
  abbr: string;
  label: string;
  shortLabel: string;
  tone: LeaveTypeTone;
  value: LeaveType;
}> = [
  { abbr: "CL", label: "Casual leave", shortLabel: "Casual", tone: "info", value: "casual" },
  { abbr: "SL", label: "Sick leave", shortLabel: "Sick", tone: "error", value: "sick" },
  { abbr: "PL", label: "Privileged leave", shortLabel: "Privileged", tone: "success", value: "privileged" },
];

export function leaveTypeMeta(leaveType: string) {
  return LEAVE_TYPES.find((item) => item.value === leaveType) ?? {
    abbr: leaveType.slice(0, 2).toUpperCase() || "LV",
    label: leaveType,
    shortLabel: leaveType,
    tone: "info" as const,
    value: leaveType as LeaveType,
  };
}

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function client() {
  return getBrowserApiClient();
}

export const leaveService = {
  async getBalances(signal?: AbortSignal): Promise<LeaveBalancesResponse> {
    return unwrap(await getMyBalancesApiV1LeaveBalancesMeGet({
      client: client(),
      signal,
      throwOnError: true,
    }));
  },

  async preview(leaveType: LeaveType, fromDate: string, toDate: string, signal?: AbortSignal): Promise<LeavePreviewResponse> {
    return unwrap(await previewApiV1LeavePreviewGet({
      client: client(),
      query: {
        leave_type: leaveType,
        from_date: fromDate,
        to_date: toDate,
      },
      signal,
      throwOnError: true,
    }));
  },

  async submit(body: SubmitLeaveBody, idempotencyKey: string): Promise<LeaveRequestItem> {
    return unwrap(await submitLeaveApiV1LeaveRequestsPost({
      client: client(),
      body,
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },

  async listMine(filter: LeaveHistoryFilter, offset = 0, signal?: AbortSignal): Promise<LeaveRequestListResponse> {
    return unwrap(await listMyRequestsApiV1LeaveRequestsMineGet({
      client: client(),
      query: { status: filter, limit: 30, offset },
      signal,
      throwOnError: true,
    }));
  },

  async listTeam(filter: TeamLeaveFilter, offset = 0, signal?: AbortSignal): Promise<TeamLeaveListResponse> {
    return unwrap(await listTeamApiV1LeaveTeamGet({
      client: client(),
      query: { status: filter, limit: 30, offset },
      signal,
      throwOnError: true,
    }));
  },
};
