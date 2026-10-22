import {
  getAdminDashboardApiV1ReportingDashboardsAdminGet,
  getCallsKpisApiV1ReportingKpisCallsScopeGet,
  getKpiSurfaceApiV1ReportingKpiSurfacesSurfaceGet,
  getManagerDashboardApiV1ReportingDashboardsManagerGet,
  getSalesPersonAttentionApiV1ReportingDashboardsSalesPersonAttentionGet,
  getSalesPersonDashboardApiV1ReportingDashboardsSalesPersonGet,
  getSalesPersonTargetsApiV1ReportingDashboardsSalesPersonTargetsGet,
  type AdminDashboardKpisResponse,
  type CallsKpiResponse,
  type KpiSurfaceResponse,
  type ManagerDashboardKpisResponse,
  type SpAttentionResponse,
  type SpDashboardKpisResponse,
  type SpTargetsKpisResponse,
} from "@humbee/api-contract";
import { getBrowserApiClient } from "@/src/shared/api";

export type {
  AdminDashboardKpisResponse,
  CallsKpiResponse,
  CallsKpiRowOut,
  CallsKpiTotalsOut,
  KpiCardOut,
  KpiGroupOut,
  KpiSurfaceResponse,
  ManagerDashboardKpisResponse,
  SpAttentionResponse,
  SpDashboardKpisResponse,
  SpTargetsKpisResponse,
} from "@humbee/api-contract";

export type CallsKpiScope = CallsKpiResponse["view"]["scope"];

export type ReportingKpiSurface = KpiSurfaceResponse["surface"];
export type DashboardPeriod = SpDashboardKpisResponse["period"];
export type AttentionKind = NonNullable<SpAttentionResponse["items"]>[number]["kind"];

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function client() {
  return getBrowserApiClient();
}

function manufacturerQuery(manufacturerId?: string | null) {
  const id = manufacturerId?.trim();
  if (!id || id === "all") return undefined;
  return id;
}

export const reportingService = {
  async getKpiSurface(
    surface: ReportingKpiSurface,
    businessDate?: string | null,
    signal?: AbortSignal,
  ): Promise<KpiSurfaceResponse> {
    return unwrap(await getKpiSurfaceApiV1ReportingKpiSurfacesSurfaceGet({
      client: client(),
      path: { surface },
      query: { business_date: businessDate ?? undefined },
      signal,
      throwOnError: true,
    }));
  },

  async getSpAttention(signal?: AbortSignal): Promise<SpAttentionResponse> {
    return unwrap(await getSalesPersonAttentionApiV1ReportingDashboardsSalesPersonAttentionGet({
      client: client(),
      signal,
      throwOnError: true,
    }));
  },

  async getSpDashboardKpis(
    period: DashboardPeriod = "mtd",
    signal?: AbortSignal,
  ): Promise<SpDashboardKpisResponse> {
    return unwrap(await getSalesPersonDashboardApiV1ReportingDashboardsSalesPersonGet({
      client: client(),
      query: { period },
      signal,
      throwOnError: true,
    }));
  },

  async getSpTargetsKpis(
    signal?: AbortSignal,
    manufacturerId?: string | null,
  ): Promise<SpTargetsKpisResponse> {
    return unwrap(await getSalesPersonTargetsApiV1ReportingDashboardsSalesPersonTargetsGet({
      client: client(),
      query: { manufacturer_id: manufacturerQuery(manufacturerId) },
      signal,
      throwOnError: true,
    }));
  },

  async getManagerDashboardKpis(
    period: DashboardPeriod = "mtd",
    signal?: AbortSignal,
    manufacturerId?: string | null,
    designationCode?: string | null,
  ): Promise<ManagerDashboardKpisResponse> {
    return unwrap(await getManagerDashboardApiV1ReportingDashboardsManagerGet({
      client: client(),
      query: {
        period,
        manufacturer_id: manufacturerQuery(manufacturerId),
        designation_code: designationCode || undefined,
      },
      signal,
      throwOnError: true,
    }));
  },

  async getAdminDashboardKpis(
    period: DashboardPeriod = "mtd",
    signal?: AbortSignal,
    manufacturerId?: string | null,
    designationCode?: string | null,
  ): Promise<AdminDashboardKpisResponse> {
    return unwrap(await getAdminDashboardApiV1ReportingDashboardsAdminGet({
      client: client(),
      query: {
        period,
        manufacturer_id: manufacturerQuery(manufacturerId),
        designation_code: designationCode || undefined,
      },
      signal,
      throwOnError: true,
    }));
  },

  async getCallsKpis(
    scope: CallsKpiScope,
    signal?: AbortSignal,
    input?: { businessDate?: string | null; forEmployeeId?: string | null },
  ): Promise<CallsKpiResponse> {
    return unwrap(await getCallsKpisApiV1ReportingKpisCallsScopeGet({
      client: client(),
      path: { scope },
      query: {
        business_date: input?.businessDate || undefined,
        for_employee_id: input?.forEmployeeId || undefined,
      },
      signal,
      throwOnError: true,
    }));
  },
};
