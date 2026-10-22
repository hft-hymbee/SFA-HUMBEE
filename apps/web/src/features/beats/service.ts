import {
  adminUpdateBeatApiV1BeatsBeatIdPatch,
  createBeatApiV1BeatsPost,
  createEditBranchApiV1BeatsBeatIdEditRequestsPost,
  deactivateBeatApiV1BeatsBeatIdDeactivatePost,
  discardDraftApiV1BeatsBeatIdDraftDiscardPost,
  getBeatApiV1BeatsBeatIdGet,
  getBeatDraftApiV1BeatsBeatIdDraftGet,
  listBeatsApiV1BeatsGet,
  reactivateBeatApiV1BeatsBeatIdReactivatePost,
  replaceDraftOutletsApiV1BeatsBeatIdDraftOutletsPut,
  searchScopeOutletsApiV1BeatsBeatIdScopeOutletsGet,
  submitBeatApiV1BeatsBeatIdSubmitPost,
  submitEditApiV1BeatsBeatIdEditRequestsSubmitPost,
  updateDraftApiV1BeatsBeatIdDraftPatch,
  type AdminUpdateBeatBody,
  type BeatDetailResponse,
  type Frequency,
  type GeoScope,
  type ScopeOutletItem,
  type ShopCategory,
} from "@humbee/api-contract";
import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { ulid } from "ulid";
import { approvalService } from "@/src/features/approvals/service";
import { ApiClientError, createIdempotencyKey, getBrowserApiClient, idempotencyHeaders } from "@/src/shared/api";
import { readSessionSync } from "@/src/shared/auth/session";
import { readGeographyMaster, shopCategoryLabel } from "@/src/shared/geography-master";
import { fetchAllPages } from "@/src/shared/pagination";

export interface Beat {
  id: string;
  name: string;
  zones: string[];
  states: string[];
  districts: string[];
  locations: string[];
  categories: string[];
  outletIds: string[];
  outletCount: number;
  frequency: string;
  frequencyPlan: {
    cadence: "daily" | "weekly" | "fortnightly" | "monthly";
    days: number[];
    weeks: number[];
  };
  status: "approved" | "pending" | "draft" | "inactive";
}

export interface OutletChoice {
  id: string;
  name: string;
  zone: string;
  state: string;
  district: string;
  location: string;
  category: string;
  selected: boolean;
  takenBy?: string | null;
}

export interface BeatScope {
  zones: string[];
  states: string[];
  districts: string[];
  categories: string[];
}

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function actorId() {
  return readSessionSync()?.employeeId ?? "";
}

function readStringArray(value: unknown, key: string) {
  if (!value || typeof value !== "object") return [];
  const candidate = (value as Record<string, unknown>)[key];
  return Array.isArray(candidate) ? candidate.filter((item): item is string => typeof item === "string") : [];
}

function readNumberArray(value: unknown, key: string) {
  if (!value || typeof value !== "object") return [];
  const candidate = (value as Record<string, unknown>)[key];
  return Array.isArray(candidate) ? candidate.filter((item): item is number => typeof item === "number") : [];
}

const ISO_BUSINESS_DATE = /^\d{4}-\d{2}-\d{2}$/;
const BEAT_PAGE_SIZE = 100;

export function isBeatPlannedOnDate(frequency: unknown, iso: string) {
  if (!frequency || typeof frequency !== "object" || !ISO_BUSINESS_DATE.test(iso)) return false;
  const cadence = typeof (frequency as { frequency?: unknown }).frequency === "string"
    ? (frequency as { frequency: string }).frequency
    : "";
  if (cadence === "daily") return true;
  const visitDays = readNumberArray(frequency, "visit_days");
  if (!visitDays.length) return false;
  const [year = 0, month = 0, day = 0] = iso.split("-").map(Number);
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  if (!visitDays.includes(weekday)) return false;
  if (cadence !== "fortnightly" && cadence !== "monthly") return true;
  const weeks = readNumberArray(frequency, "week_cycle");
  if (!weeks.length) return false;
  // W1-W4 are Sunday-start calendar weeks of the month, matching DateField.
  const firstWeekday = new Date(Date.UTC(year, month - 1, 1)).getUTCDay();
  const weekOfMonth = Math.floor((firstWeekday + day - 1) / 7) + 1;
  return weeks.includes(weekOfMonth);
}

function mapFrequency(value: Record<string, unknown>) {
  const cadence = typeof value.frequency === "string" ? value.frequency : "daily";
  const days = Array.isArray(value.visit_days) ? value.visit_days.filter((item): item is number => typeof item === "number") : [];
  const weeks = Array.isArray(value.week_cycle) ? value.week_cycle.filter((item): item is number => typeof item === "number") : [];
  const names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  return cadence === "daily" ? "Daily" : `${cadence[0]?.toUpperCase()}${cadence.slice(1)} · ${days.map((day) => names[day]).join(", ")}${weeks.length ? ` · ${weeks.map((week) => `W${week}`).join(", ")}` : ""}`;
}

export function mapBeat(detail: BeatDetailResponse): Beat {
  const scope = detail.geo_scope ?? {};
  const frequency = detail.frequency ?? {};
  return {
    id: detail.id,
    name: detail.display_name,
    zones: readStringArray(scope, "zones"),
    states: readStringArray(scope, "states"),
    districts: readStringArray(scope, "districts"),
    locations: [...new Set(detail.outlets.map((outlet) => outlet.locality).filter((item): item is string => Boolean(item)))],
    categories: readStringArray(scope, "cats"),
    outletIds: detail.outlets.map((outlet) => outlet.outlet_ref),
    outletCount: detail.outlet_count,
    frequency: mapFrequency(frequency),
    frequencyPlan: {
      cadence: (frequency.frequency as Beat["frequencyPlan"]["cadence"]) ?? "daily",
      days: readNumberArray(frequency, "visit_days"),
      weeks: readNumberArray(frequency, "week_cycle"),
    },
    status: detail.activation_state === "inactive"
      ? "inactive"
      : detail.pending_edit
        ? "pending"
        : detail.lifecycle_state === "approved"
          ? "approved"
          : detail.lifecycle_state === "draft"
            ? "draft"
            : "pending",
  };
}

export function useBeats(status?: string, { refetchOnMount = true }: { refetchOnMount?: boolean | "always" } = {}) {
  const actor = actorId();
  return useQuery({
    refetchOnMount,
    queryKey: ["beats", { actorId: actor, status: status ?? "all" }],
    queryFn: () => fetchAllPages(async (page) => unwrap(await listBeatsApiV1BeatsGet({
      client: getBrowserApiClient(),
      query: { status: status === "all" ? undefined : status, limit: BEAT_PAGE_SIZE, offset: (page - 1) * BEAT_PAGE_SIZE },
      throwOnError: true,
    }))),
    placeholderData: keepPreviousData,
  });
}

export function useBeat(beatId: string, enabled = true) {
  return useQuery({
    queryKey: ["beats", actorId(), beatId],
    queryFn: async () => unwrap(await getBeatApiV1BeatsBeatIdGet({
      client: getBrowserApiClient(),
      path: { beat_id: beatId },
      throwOnError: true,
    })),
    enabled: Boolean(beatId && enabled),
  });
}

export function useBeatDraftVersion(beatId: string, enabled = true) {
  return useQuery({
    queryKey: ["beats", actorId(), beatId, "draft"],
    queryFn: async () => {
      const result = await getBeatDraftApiV1BeatsBeatIdDraftGet({
        client: getBrowserApiClient(),
        path: { beat_id: beatId },
      });
      return result.data ?? null;
    },
    enabled: Boolean(beatId && enabled),
  });
}

interface BeatDetailOptions {
  enabled?: boolean;
  knownDraft?: boolean;
  pendingEdit?: boolean;
}

export function useBeatDetail(beatId: string, { enabled = true, knownDraft = false, pendingEdit = false }: BeatDetailOptions = {}) {
  const currentQuery = useBeat(beatId, enabled && !knownDraft);
  const neverApproved = currentQuery.error instanceof ApiClientError && currentQuery.error.code === "no_current_version";
  const draftRequired = knownDraft || neverApproved;
  const draftEnabled = enabled && (draftRequired || (pendingEdit && Boolean(currentQuery.data?.pending_edit)));
  const draftQuery = useBeatDraftVersion(beatId, draftEnabled);
  const current = currentQuery.data ?? null;
  const draft = draftEnabled ? draftQuery.data ?? null : null;
  return {
    current,
    draft,
    detail: current ?? (draftRequired ? draft : null),
    isPending: (enabled && !knownDraft && currentQuery.isPending) || (draftEnabled && draftQuery.isPending),
    isError: (currentQuery.isError && !neverApproved) || (draftRequired && draftQuery.isError),
    refetch: async () => {
      await Promise.all([
        knownDraft ? undefined : currentQuery.refetch(),
        draftEnabled ? draftQuery.refetch() : undefined,
      ]);
    },
  };
}

export function useGeographyMaster() {
  const actor = actorId();
  return useQuery({
    queryKey: ["geography-master", actor],
    queryFn: async () => readGeographyMaster({
      client: getBrowserApiClient(),
      assignedEmployeeId: actor,
    }),
    staleTime: 86_400_000,
    enabled: Boolean(actor),
  });
}

export interface UnsavedOutletScope {
  districts: string[];
  categories: ShopCategory[];
}

export function useScopeOutlets(beatId: string, query = "", enabled = true, scopeKey = "current", unsavedScope?: UnsavedOutletScope) {
  const actor = actorId();
  const queryResult = useInfiniteQuery({
    queryKey: ["beats", actor, beatId, "scope-outlets", scopeKey, query, unsavedScope ?? null],
    queryFn: async ({ pageParam }) => unwrap(await searchScopeOutletsApiV1BeatsBeatIdScopeOutletsGet({
      client: getBrowserApiClient(),
      path: { beat_id: beatId },
      query: {
        q: query || undefined,
        cursor: pageParam ?? undefined,
        limit: 100,
        district_ids: unsavedScope?.districts,
        shop_categories: unsavedScope?.categories.length ? unsavedScope.categories : undefined,
      },
      throwOnError: true,
    })),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    select: (data) => data.pages.flatMap((page) => page.items),
    enabled: Boolean(actor && beatId && enabled),
  });
  const { fetchNextPage, hasNextPage, isFetchingNextPage } = queryResult;
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage();
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);
  return queryResult;
}

export function mapOutlet(outlet: ScopeOutletItem): OutletChoice {
  return {
    id: outlet.outlet_ref,
    name: outlet.name,
    zone: "",
    state: "",
    district: "",
    location: outlet.locality?.trim() || "",
    category: outlet.category ? shopCategoryLabel(outlet.category) : "",
    selected: outlet.selected,
    takenBy: outlet.taken_by_beat,
  };
}

function beatMutationTarget(input: string | { beatId: string; idempotencyKey?: string }) {
  return typeof input === "string"
    ? { beatId: input, idempotencyKey: createIdempotencyKey() }
    : { beatId: input.beatId, idempotencyKey: input.idempotencyKey ?? createIdempotencyKey() };
}

export function useBeatMutations() {
  const queryClient = useQueryClient();
  const actor = actorId();
  const invalidateBeatLists = () => queryClient.invalidateQueries({ queryKey: ["beats", { actorId: actor }] });
  const invalidateBeatDraft = async (beatId: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["beats", actor, beatId] }),
      queryClient.invalidateQueries({ queryKey: ["beats", actor, beatId, "draft"] }),
      queryClient.invalidateQueries({ queryKey: ["beats", actor, beatId, "scope-outlets"] }),
    ]);
  };
  const invalidateBeatLifecycle = async (beatId: string) => {
    await Promise.all([
      invalidateBeatLists(),
      invalidateBeatDraft(beatId),
      queryClient.invalidateQueries({ queryKey: ["approvals", { actorId: actor }] }),
      queryClient.invalidateQueries({ queryKey: ["notifications", { actorId: actor }] }),
    ]);
  };
  const create = useMutation({
    mutationFn: async (input?: string | { beatId?: string; idempotencyKey?: string; ownerEmployeeId?: string }) => {
      const beatId = typeof input === "string" ? input : input?.beatId;
      const idempotencyKey = typeof input === "string" ? createIdempotencyKey() : input?.idempotencyKey ?? createIdempotencyKey();
      const ownerEmployeeId = typeof input === "string" ? undefined : input?.ownerEmployeeId;
      return unwrap(await createBeatApiV1BeatsPost({
        client: getBrowserApiClient(),
        body: { id: beatId ?? ulid(), owner_employee_id: ownerEmployeeId },
        headers: idempotencyHeaders(idempotencyKey),
        throwOnError: true,
      }));
    },
    onSuccess: (beat) => {
      void invalidateBeatDraft(beat.id);
    },
  });
  const saveDraft = useMutation({
    mutationFn: async (input: { beatId: string; displayName?: string; code?: string; geoScope?: GeoScope; frequency?: Frequency; idempotencyKey?: string }) =>
      unwrap(await updateDraftApiV1BeatsBeatIdDraftPatch({
        client: getBrowserApiClient(),
        path: { beat_id: input.beatId },
        body: {
          display_name: input.displayName,
          code: input.code,
          geo_scope: input.geoScope,
          frequency: input.frequency,
        },
        headers: idempotencyHeaders(input.idempotencyKey ?? createIdempotencyKey()),
        throwOnError: true,
      })),
    onSuccess: (_data, input) => {
      void invalidateBeatDraft(input.beatId);
    },
  });
  const replaceOutlets = useMutation({
    mutationFn: async (input: { beatId: string; outletRefs: string[]; idempotencyKey?: string }) =>
      unwrap(await replaceDraftOutletsApiV1BeatsBeatIdDraftOutletsPut({
        client: getBrowserApiClient(),
        path: { beat_id: input.beatId },
        body: { outlet_refs: input.outletRefs },
        headers: idempotencyHeaders(input.idempotencyKey ?? createIdempotencyKey()),
        throwOnError: true,
      })),
    onSuccess: (_data, input) => {
      void invalidateBeatDraft(input.beatId);
    },
  });
  const submit = useMutation({
    mutationFn: async (input: string | { beatId: string; idempotencyKey?: string }) => {
      const target = beatMutationTarget(input);
      return unwrap(await submitBeatApiV1BeatsBeatIdSubmitPost({
        client: getBrowserApiClient(),
        path: { beat_id: target.beatId },
        headers: idempotencyHeaders(target.idempotencyKey),
        throwOnError: true,
      }));
    },
    onSuccess: (beat) => {
      void invalidateBeatLifecycle(beat.id);
    },
  });
  const branchEdit = useMutation({
    mutationFn: async (beatId: string) => unwrap(await createEditBranchApiV1BeatsBeatIdEditRequestsPost({
      client: getBrowserApiClient(),
      path: { beat_id: beatId },
      headers: idempotencyHeaders(createIdempotencyKey()),
      throwOnError: true,
    })),
    onSuccess: (branch) => {
      void invalidateBeatDraft(branch.beat_id);
    },
  });
  const submitEdit = useMutation({
    mutationFn: async (input: string | { beatId: string; idempotencyKey?: string }) => {
      const target = beatMutationTarget(input);
      return unwrap(await submitEditApiV1BeatsBeatIdEditRequestsSubmitPost({
        client: getBrowserApiClient(),
        path: { beat_id: target.beatId },
        headers: idempotencyHeaders(target.idempotencyKey),
        throwOnError: true,
      }));
    },
    onSuccess: (beat) => {
      void invalidateBeatLifecycle(beat.id);
    },
  });
  const adminUpdate = useMutation({
    mutationFn: async (input: { beatId: string; body: AdminUpdateBeatBody }) =>
      unwrap(await adminUpdateBeatApiV1BeatsBeatIdPatch({
        client: getBrowserApiClient(),
        path: { beat_id: input.beatId },
        body: input.body,
        headers: idempotencyHeaders(createIdempotencyKey()),
        throwOnError: true,
      })),
    onSuccess: (beat) => {
      void invalidateBeatLifecycle(beat.id);
    },
  });
  const deactivate = useMutation({
    mutationFn: async (beatId: string) => unwrap(await deactivateBeatApiV1BeatsBeatIdDeactivatePost({
      client: getBrowserApiClient(),
      path: { beat_id: beatId },
      body: { reason: "Deactivated by administrator" },
      headers: idempotencyHeaders(createIdempotencyKey()),
      throwOnError: true,
    })),
    onSuccess: (beat) => {
      void invalidateBeatLifecycle(beat.id);
    },
  });
  const reactivate = useMutation({
    mutationFn: async (beatId: string) => unwrap(await reactivateBeatApiV1BeatsBeatIdReactivatePost({
      client: getBrowserApiClient(),
      path: { beat_id: beatId },
      headers: idempotencyHeaders(createIdempotencyKey()),
      throwOnError: true,
    })),
    onSuccess: (beat) => {
      void invalidateBeatLifecycle(beat.id);
    },
  });
  const discardDraft = useMutation({
    mutationFn: async (beatId: string) => unwrap(await discardDraftApiV1BeatsBeatIdDraftDiscardPost({
      client: getBrowserApiClient(),
      path: { beat_id: beatId },
      headers: idempotencyHeaders(createIdempotencyKey()),
      throwOnError: true,
    })),
    onSuccess: (beat) => {
      void invalidateBeatDraft(beat.id);
    },
  });
  const withdraw = useMutation({
    mutationFn: async (input: { beatId: string; approvalRequestId: string }) =>
      approvalService.withdraw(input.approvalRequestId, undefined, createIdempotencyKey()),
    onSuccess: (_data, input) => {
      void invalidateBeatLifecycle(input.beatId);
    },
  });
  return { create, saveDraft, replaceOutlets, submit, branchEdit, submitEdit, adminUpdate, deactivate, reactivate, discardDraft, withdraw };
}
