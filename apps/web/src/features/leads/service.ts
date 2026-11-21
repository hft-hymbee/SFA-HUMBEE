import {
  captureLeadApiV1LeadsPost,
  getLeadApiV1LeadsLeadIdGet,
  leadCountsByEmployeeApiV1LeadsCountsByEmployeeGet,
  listLeadsApiV1LeadsGet,
  type CaptureLeadBody,
  type LeadCountsByEmployee,
  type LeadDetailOut,
  type LeadOut,
  type LeadPage,
} from "@humbee/api-contract";
import {
  createIdempotencyKey,
  getBrowserApiClient,
  idempotencyHeaders,
} from "@/src/shared/api";

export type {
  CaptureLeadBody,
  LeadCapturedBy,
  LeadCapturedByDetail,
  LeadCountsByEmployee,
  LeadDetailOut,
  LeadEmployeeCount,
  LeadListItem,
  LeadOut,
  LeadPage,
} from "@humbee/api-contract";

export interface LeadListParams {
  from?: string;
  to?: string;
  employeeId?: string;
  q?: string;
  cursor?: string;
  limit?: number;
}

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function client() {
  return getBrowserApiClient();
}

export const leadsService = {
  async captureLead(body: CaptureLeadBody, idempotencyKey = createIdempotencyKey()): Promise<LeadOut> {
    return unwrap(await captureLeadApiV1LeadsPost({
      client: client(),
      body,
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },

  async list(params: LeadListParams = {}, signal?: AbortSignal): Promise<LeadPage> {
    return unwrap(await listLeadsApiV1LeadsGet({
      client: client(),
      query: {
        from: params.from || undefined,
        to: params.to || undefined,
        employee_id: params.employeeId || undefined,
        q: params.q?.trim() || undefined,
        cursor: params.cursor || undefined,
        limit: params.limit ?? 20,
      },
      signal,
      throwOnError: true,
    }));
  },

  async detail(id: string, signal?: AbortSignal): Promise<LeadDetailOut> {
    return unwrap(await getLeadApiV1LeadsLeadIdGet({
      client: client(),
      path: { lead_id: id },
      signal,
      throwOnError: true,
    }));
  },

  async countsByEmployee(signal?: AbortSignal): Promise<LeadCountsByEmployee> {
    return unwrap(await leadCountsByEmployeeApiV1LeadsCountsByEmployeeGet({
      client: client(),
      signal,
      throwOnError: true,
    }));
  },
};
