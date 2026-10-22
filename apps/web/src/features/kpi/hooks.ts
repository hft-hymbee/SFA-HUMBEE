"use client";

import { getTeamApiV1AttendanceTeamGet, type TeamAttendanceResponse } from "@humbee/api-contract";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useActorId } from "@/src/features/approvals/hooks";
import { istBusinessDate } from "@/src/features/attendance/service";
import { getBrowserApiClient } from "@/src/shared/api";
import { fetchAllPages } from "@/src/shared/pagination";
import {
  reportingService,
  type CallsKpiScope,
  type DashboardPeriod,
  type ReportingKpiSurface,
} from "./service";

export const reportingKeys = {
  all: (actorId: string) => ["reporting", { actorId }] as const,
  surface: (actorId: string, surface: ReportingKpiSurface, businessDate?: string | null) =>
    [...reportingKeys.all(actorId), "surface", surface, businessDate ?? "current"] as const,
  dashboardKpis: (
    actorId: string,
    role: "sp" | "manager" | "admin",
    period: DashboardPeriod,
    manufacturerId?: string | null,
    designationCode?: string | null,
  ) =>
    [
      ...reportingKeys.all(actorId),
      "dashboard-kpis",
      role,
      period,
      manufacturerId && manufacturerId !== "all" ? manufacturerId : "all",
      designationCode ?? "default",
    ] as const,
  attention: (actorId: string) => [...reportingKeys.all(actorId), "attention"] as const,
  spTargets: (actorId: string, manufacturerId?: string | null) =>
    [...reportingKeys.all(actorId), "sp-targets", manufacturerId && manufacturerId !== "all" ? manufacturerId : "all"] as const,
  callsKpis: (
    actorId: string,
    scope: CallsKpiScope,
    businessDate?: string | null,
    forEmployeeId?: string | null,
  ) =>
    [...reportingKeys.all(actorId), "calls-kpis", scope, businessDate ?? "current", forEmployeeId ?? "root"] as const,
};

export function useKpiSurface(surface: ReportingKpiSurface, businessDate?: string | null) {
  const actorId = useActorId();
  return useQuery({
    queryKey: reportingKeys.surface(actorId, surface, businessDate),
    queryFn: ({ signal }) => reportingService.getKpiSurface(surface, businessDate, signal),
    enabled: Boolean(actorId),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useSpAttention(input?: { enabled?: boolean }) {
  const actorId = useActorId();
  return useQuery({
    queryKey: reportingKeys.attention(actorId),
    queryFn: ({ signal }) => reportingService.getSpAttention(signal),
    enabled: Boolean(actorId) && (input?.enabled ?? true),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}

export function useSpDashboardKpis(
  period: DashboardPeriod = "mtd",
  input?: { enabled?: boolean },
) {
  const actorId = useActorId();
  return useQuery({
    queryKey: reportingKeys.dashboardKpis(actorId, "sp", period),
    queryFn: ({ signal }) => reportingService.getSpDashboardKpis(period, signal),
    enabled: Boolean(actorId) && (input?.enabled ?? true),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useSpTargetsKpis(input?: { enabled?: boolean; manufacturerId?: string | null }) {
  const actorId = useActorId();
  return useQuery({
    queryKey: reportingKeys.spTargets(actorId, input?.manufacturerId),
    queryFn: ({ signal }) => reportingService.getSpTargetsKpis(signal, input?.manufacturerId),
    enabled: Boolean(actorId) && (input?.enabled ?? true),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useManagerDashboardKpis(
  period: DashboardPeriod = "mtd",
  input?: { enabled?: boolean; manufacturerId?: string | null; designationCode?: string | null },
) {
  const actorId = useActorId();
  return useQuery({
    queryKey: reportingKeys.dashboardKpis(
      actorId, "manager", period, input?.manufacturerId, input?.designationCode,
    ),
    queryFn: ({ signal }) => reportingService.getManagerDashboardKpis(
      period, signal, input?.manufacturerId, input?.designationCode,
    ),
    placeholderData: keepPreviousData,
    enabled: Boolean(actorId) && (input?.enabled ?? true),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useAdminDashboardKpis(
  period: DashboardPeriod = "mtd",
  input?: { enabled?: boolean; manufacturerId?: string | null; designationCode?: string | null },
) {
  const actorId = useActorId();
  return useQuery({
    queryKey: reportingKeys.dashboardKpis(
      actorId, "admin", period, input?.manufacturerId, input?.designationCode,
    ),
    queryFn: ({ signal }) => reportingService.getAdminDashboardKpis(
      period, signal, input?.manufacturerId, input?.designationCode,
    ),
    enabled: Boolean(actorId) && (input?.enabled ?? true),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useCallsKpis(
  scope: CallsKpiScope,
  input?: { enabled?: boolean; businessDate?: string | null; forEmployeeId?: string | null },
) {
  const actorId = useActorId();
  return useQuery({
    queryKey: reportingKeys.callsKpis(actorId, scope, input?.businessDate, input?.forEmployeeId),
    queryFn: ({ signal }) => reportingService.getCallsKpis(scope, signal, {
      businessDate: input?.businessDate,
      forEmployeeId: input?.forEmployeeId,
    }),
    enabled: Boolean(actorId) && (input?.enabled ?? true),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useTeamAttendance(input?: { enabled?: boolean }) {
  const actorId = useActorId();
  const businessDate = istBusinessDate();
  return useQuery({
    queryKey: [...reportingKeys.all(actorId), "team-attendance", businessDate],
    queryFn: ({ signal }): Promise<TeamAttendanceResponse> => fetchAllPages(async (page) => {
      const result = await getTeamApiV1AttendanceTeamGet({
        client: getBrowserApiClient(),
        query: { business_date: businessDate, page, page_size: 100 },
        signal,
        throwOnError: true,
      });
      return result.data;
    }),
    enabled: Boolean(actorId) && (input?.enabled ?? true),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}
