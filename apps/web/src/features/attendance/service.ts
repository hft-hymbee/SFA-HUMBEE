import {
  endOfficialWorkApiV1OfficialWorkSessionsSessionIdEndPost,
  getExportApiV1AttendanceExportsJobIdGet,
  getCurrentOfficialWorkApiV1OfficialWorkSessionsCurrentGet,
  getHistoryApiV1AttendanceHistoryGet,
  getTodayApiV1AttendanceTodayGet,
  getTodayApiV1HomeTodayGet,
  listOfficialWorkApiV1OfficialWorkSessionsGet,
  punchApiV1AttendancePunchesPost,
  requestExportApiV1AttendanceExportsPost,
  startOfficialWorkApiV1OfficialWorkSessionsPost,
  type AttendanceHistoryResponse,
  type AttendanceTodayResponse,
  type ExportJobResponse,
  type ExportRequestBody,
  type OfficialWorkHistoryResponse,
  type OfficialWorkSessionItem,
  type PunchBody,
  type TodayResponse,
} from "@humbee/api-contract";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ulid } from "ulid";
import { createIdempotencyKey, getBrowserApiClient, idempotencyHeaders } from "@/src/shared/api";
import { readSessionSync } from "@/src/shared/auth/session";
import { createActorQueryKeys } from "@/src/shared/state/query-keys";

const attendanceKeys = createActorQueryKeys("attendance");
const todayKeys = createActorQueryKeys("today");
const officialWorkKeys = createActorQueryKeys("official-work");
const attendanceExportKeys = createActorQueryKeys("attendance-exports");

interface AttendanceTodayOptions {
  refetchOnWindowFocus?: boolean;
}

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function isOfficialWorkSession(value: unknown): value is OfficialWorkSessionItem {
  return Boolean(
    value
      && typeof value === "object"
      && "id" in value
      && "started_at" in value
      && "status" in value,
  );
}

export function istBusinessDate(date = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(date);
}

function actorId() {
  return readSessionSync()?.employeeId ?? "";
}

export function useAttendanceToday(options: AttendanceTodayOptions = {}) {
  const actor = actorId();
  const businessDate = istBusinessDate();
  return useQuery({
    queryKey: attendanceKeys.byBusinessDate(actor, businessDate),
    queryFn: async () => unwrap(await getTodayApiV1AttendanceTodayGet({
      client: getBrowserApiClient(),
      throwOnError: true,
    })),
    staleTime: 30_000,
    refetchOnWindowFocus: options.refetchOnWindowFocus ?? true,
  });
}

export function useTodaySummary() {
  const actor = actorId();
  return useQuery({
    queryKey: todayKeys.byBusinessDate(actor, istBusinessDate()),
    queryFn: async () => unwrap(await getTodayApiV1HomeTodayGet({
      client: getBrowserApiClient(),
      throwOnError: true,
    })),
    staleTime: 30_000,
  });
}

export function useAttendanceHistory(month: string) {
  const actor = actorId();
  return useQuery({
    queryKey: [...attendanceKeys.all(actor), "history", month],
    queryFn: async () => unwrap(await getHistoryApiV1AttendanceHistoryGet({
      client: getBrowserApiClient(),
      query: { month },
      throwOnError: true,
    })),
    staleTime: month === istBusinessDate().slice(0, 7) ? 30_000 : Infinity,
  });
}

export function useAttendanceExport(jobId: string | null | undefined) {
  const actor = actorId();
  return useQuery({
    queryKey: [...attendanceExportKeys.all(actor), jobId ?? ""],
    queryFn: async () => unwrap(await getExportApiV1AttendanceExportsJobIdGet({
      client: getBrowserApiClient(),
      path: { job_id: jobId! },
      throwOnError: true,
    })),
    enabled: Boolean(actor && jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status?.toLowerCase();
      return status === "queued" || status === "running" ? 5_000 : false;
    },
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });
}

export function useAttendanceExportRequest() {
  const queryClient = useQueryClient();
  const actor = actorId();
  return useMutation({
    mutationFn: async (body: ExportRequestBody) => unwrap(await requestExportApiV1AttendanceExportsPost({
      client: getBrowserApiClient(),
      body,
      headers: idempotencyHeaders(createIdempotencyKey()),
      throwOnError: true,
    })),
    onSuccess: (job) => {
      queryClient.setQueryData([...attendanceExportKeys.all(actor), job.id], job);
      void queryClient.invalidateQueries({ queryKey: attendanceExportKeys.all(actor) });
    },
  });
}

export function usePunch() {
  const queryClient = useQueryClient();
  const actor = actorId();
  return useMutation({
    mutationFn: async (body: PunchBody & { idempotencyKey: string }) => {
      const { idempotencyKey, ...payload } = body;
      return unwrap(await punchApiV1AttendancePunchesPost({
        client: getBrowserApiClient(),
        body: payload,
        headers: idempotencyHeaders(idempotencyKey),
        throwOnError: true,
      }));
    },
    onSuccess: async (duty) => {
      queryClient.setQueryData(attendanceKeys.byBusinessDate(actor, duty.business_date), duty);
      await queryClient.invalidateQueries({ queryKey: todayKeys.all(actor) });
      await queryClient.invalidateQueries({ queryKey: ["routes"] });
    },
  });
}

export function buildPunchBody(
  direction: "in" | "out",
  location: {
    latitude: number;
    longitude: number;
    accuracyMeters: number;
    altitudeMeters?: number | null;
    provider?: string;
    isMockLocation?: boolean;
  },
  resolvedAddress: string | null,
): PunchBody & { idempotencyKey: string } {
  const occurredAt = new Date().toISOString();
  const provider = location.provider?.toLowerCase();
  return {
    id: ulid(),
    idempotencyKey: createIdempotencyKey(),
    direction,
    occurred_at: occurredAt,
    resolved_address: resolvedAddress,
    gps_fix: {
      latitude: location.latitude,
      longitude: location.longitude,
      accuracy_m: 50,
      altitude_m: location.altitudeMeters ?? null,
      provider: provider === "network" || provider === "fused" ? provider : "gps",
      is_mock_location: location.isMockLocation ?? false,
      captured_at: occurredAt,
    },
  };
}

function weekPeriod() {
  const now = new Date();
  const day = (now.getDay() + 6) % 7;
  const from = new Date(now);
  from.setDate(now.getDate() - day);
  const to = new Date(from);
  to.setDate(from.getDate() + 6);
  return { from: istBusinessDate(from), to: istBusinessDate(to) };
}

export function useOfficialWorkCurrent() {
  const actor = actorId();
  return useQuery({
    queryKey: [...officialWorkKeys.all(actor), "current"],
    queryFn: async () => {
      const current = unwrap(await getCurrentOfficialWorkApiV1OfficialWorkSessionsCurrentGet({
        client: getBrowserApiClient(),
        throwOnError: true,
      }));
      return isOfficialWorkSession(current) ? current : null;
    },
    refetchOnReconnect: true,
  });
}

export function useOfficialWorkHistory() {
  const actor = actorId();
  const period = weekPeriod();
  return useQuery({
    queryKey: officialWorkKeys.byPeriod(actor, period),
    queryFn: async () => unwrap(await listOfficialWorkApiV1OfficialWorkSessionsGet({
      client: getBrowserApiClient(),
      query: period,
      throwOnError: true,
    })),
  });
}

export function useOfficialWorkMutations() {
  const queryClient = useQueryClient();
  const actor = actorId();
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: officialWorkKeys.all(actor) });
    await queryClient.invalidateQueries({ queryKey: attendanceKeys.all(actor) });
    await queryClient.invalidateQueries({ queryKey: todayKeys.all(actor) });
  };
  const start = useMutation({
    mutationFn: async (input: { workType: "meeting" | "training" | "collection" | "other"; purpose: string; notes: string }) =>
      unwrap(await startOfficialWorkApiV1OfficialWorkSessionsPost({
        client: getBrowserApiClient(),
        body: {
          id: ulid(),
          work_type: input.workType,
          purpose: input.purpose.trim() || null,
          notes: input.notes.trim() || null,
          occurred_at: new Date().toISOString(),
        },
        headers: idempotencyHeaders(createIdempotencyKey()),
        throwOnError: true,
      })),
    onSuccess: invalidate,
  });
  const end = useMutation({
    mutationFn: async (sessionId: string) =>
      unwrap(await endOfficialWorkApiV1OfficialWorkSessionsSessionIdEndPost({
        client: getBrowserApiClient(),
        path: { session_id: sessionId },
        body: { occurred_at: new Date().toISOString() },
        headers: idempotencyHeaders(createIdempotencyKey()),
        throwOnError: true,
      })),
    onSuccess: invalidate,
  });
  return { start, end };
}

export type {
  AttendanceHistoryResponse,
  AttendanceTodayResponse,
  ExportJobResponse,
  OfficialWorkHistoryResponse,
  OfficialWorkSessionItem,
  TodayResponse,
};
