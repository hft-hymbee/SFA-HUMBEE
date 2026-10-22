import {
  checkInApiV1VisitsVisitIdCheckInPost,
  checkOutApiV1VisitsVisitIdCheckOutPost,
  coverageTeamApiV1CoverageTeamGet,
  createCombinedVisitApiV1CombinedVisitsPost,
  getCombinedVisitApiV1CombinedVisitsCombinedVisitIdGet,
  getCurrentRoutePlanApiV1RoutePlansCurrentGet,
  getLastOutletVisitApiV1OutletsOutletRefLastVisitGet,
  getOutletDetailApiV1OutletsOutletIdGet,
  getVisitOutcomeApiV1VisitsVisitIdOutcomeGet,
  listCombinedVisitsApiV1CombinedVisitsGet,
  listBeatsApiV1BeatsGet,
  listMissedVisitsApiV1MissedVisitsGet,
  logOutcomeApiV1VisitsVisitIdOutcomePost,
  routeDaysApiV1RoutePlansDaysGet,
  listUnplannedOutletsApiV1RoutesUnplannedOutletsGet,
  startBeatApiV1RoutePlansSwitchBeatPost,
  submitCombinedVisitFeedbackApiV1CombinedVisitsCombinedVisitIdFeedbackPost,
  submitCoordinateCorrectionApiV1VisitsVisitIdOutletCoordinatesPost,
  type CheckInBody,
  type CombinedVisitFeedbackBody,
  type CombinedVisitResponse,
  type CoordinateCorrectionBody,
  type CoverageResponse,
  type CreateCombinedVisitBody,
  type LastOutletVisitResponse,
  type OutcomeBody,
  type OutletDetailResponse,
  type RouteDaysResponse,
  type RouteOutletGroup,
  type RoutePlanResponse,
  type RouteStopItem,
  type VisitOutcomeDetail,
} from "@humbee/api-contract";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ulid } from "ulid";
import { createIdempotencyKey, getBrowserApiClient, idempotencyHeaders } from "@/src/shared/api";
import { readSessionSync } from "@/src/shared/auth/session";
import { createActorQueryKeys } from "@/src/shared/state/query-keys";
import { istBusinessDate } from "@/src/features/attendance/service";
import { formatPaiseToInr } from "@/src/shared/formatting";
import { fetchAllPages } from "@/src/shared/pagination";

export type VisitType = "Physical" | "Telephonic";

export interface RouteStop {
  id: string;
  visitId: string | null;
  outletRef: string;
  sequence: number;
  outletName: string;
  area: string;
  status: "done" | "next" | "todo" | "missed";
  visitType?: VisitType;
  visitOutcome?: "with_order" | "no_order";
  orderCount?: number;
  planned: boolean;
  combinedVisitScheduled: boolean;
  beatId?: string | null;
  runOrigin?: string | null;
  outletLevel: "Dealer" | "Distribution Partner";
  location?: {
    latitude: number;
    longitude: number;
  };
  checkinGps?: {
    lat: number;
    lng: number;
    accuracyM: number | null;
    provider: string | null;
    isMock: boolean | null;
  };
  checkedInAt?: string | null;
  checkedOutAt?: string | null;
}

export interface BeatChoice {
  id: string;
  name: string;
  assignedToday: boolean;
  active: boolean;
  runOrigin: BeatRunSection;
}

export interface OutletSnapshot {
  contact: string;
  gst: string;
  locality: string | null;
  mobileLabel: string;
  mobileTel: string;
  name: string;
  location: {
    latitude: number;
    longitude: number;
  } | null;
  facts: Array<{ label: string; value: string }>;
  lastOrderDate: string;
  lastOrderStatus: "pending" | "approved" | "verified" | "cancelled" | "default" | "partially-completed" | "not-verified" | "completed" | "success";
  lastOrderStatusLabel: string;
}

export interface VisitOutcomeReason {
  id: string;
  icon: string;
  label: string;
}

export interface UnplannedOutletChoice {
  id: string;
  name: string;
  area: string;
}

const BEAT_CHOICE_PAGE_SIZE = 100;
const routeKeys = createActorQueryKeys("routes");
const combinedVisitKeys = createActorQueryKeys("combined-visits");
const coverageKeys = createActorQueryKeys("coverage");

export const ALL_ROUTE_PLAN_GROUP_ID = "all";
export type BeatRunSection = "assigned_beat" | "unplanned_beat" | "draft_beat";

export function beatRunSectionOrder(section: BeatRunSection) {
  if (section === "assigned_beat") return 0;
  if (section === "unplanned_beat") return 1;
  return 2;
}

export function beatRunSectionLabel(section: BeatRunSection) {
  if (section === "assigned_beat") return "Assigned beats";
  if (section === "unplanned_beat") return "Unplanned beats";
  return "Draft beats";
}

export function beatRunSectionFromBeatListItem(item: { lifecycle_state: string; run_origin?: string | null }): BeatRunSection {
  if (item.lifecycle_state === "draft") return "draft_beat";
  return item.run_origin === "assigned_beat" ? "assigned_beat" : "unplanned_beat";
}

interface CurrentRouteOptions {
  enabled?: boolean;
  refetchOnWindowFocus?: boolean;
}

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function actorId() {
  return readSessionSync()?.employeeId ?? "";
}

function routePlanGroupId(group: RouteOutletGroup, index: number) {
  return group.beat_id ?? `unplanned-${index}`;
}

export function mapRouteStop(stop: RouteStopItem): RouteStop {
  const visitState = stop.visit_state?.toLowerCase();
  const completed = visitState === "visited_with_order" || visitState === "visited_no_order";
  const visitInProgress = visitState === "in_progress";
  const visitStarted = visitInProgress || completed;
  return {
    id: stop.visit_id ?? stop.outlet_ref,
    visitId: stop.visit_id,
    outletRef: stop.outlet_ref,
    sequence: stop.sequence_no,
    outletName: stop.name,
    area: stop.locality?.trim() || "",
    status: completed
      ? "done"
      : visitInProgress
        ? "next"
        : visitState === "missed"
          ? "missed"
          : "todo",
    visitType: visitStarted && stop.visit_type === "telephonic" ? "Telephonic" : visitStarted && stop.visit_type === "physical" ? "Physical" : undefined,
    visitOutcome: visitState === "visited_with_order" ? "with_order" : visitState === "visited_no_order" ? "no_order" : undefined,
    orderCount: stop.order_count ?? 0,
    planned: stop.visit_origin !== "unplanned",
    combinedVisitScheduled: stop.combined_visit_scheduled ?? false,
    beatId: stop.beat_id,
    runOrigin: stop.run_origin,
    outletLevel: stop.category?.toLowerCase().includes("distribution") ? "Distribution Partner" : "Dealer",
    checkinGps: stop.checkin_gps
      ? {
          lat: stop.checkin_gps.lat,
          lng: stop.checkin_gps.lng,
          accuracyM: stop.checkin_gps.accuracy_m ?? null,
          provider: stop.checkin_gps.provider ?? null,
          isMock: stop.checkin_gps.is_mock ?? null,
        }
      : undefined,
    checkedInAt: stop.checked_in_at ?? null,
    checkedOutAt: stop.checked_out_at ?? null,
  };
}

export function routePlanStops(plan: RoutePlanResponse): RouteStopItem[] {
  return plan.outlet_groups.flatMap((group) => group.outlets);
}

export function routePlanStartedBeatIds(plan: RoutePlanResponse | null | undefined) {
  return new Set([
    plan?.beat_id,
    ...(plan ? routePlanStops(plan).map((stop) => stop.beat_id) : []),
  ].filter((beatId): beatId is string => Boolean(beatId)));
}

export interface RoutePlanBeatGroup {
  id: string;
  beatId: string | null;
  label: string;
  stops: RouteStop[];
  runOrigin: BeatRunSection;
}

export function routePlanBeatGroups(plan: RoutePlanResponse): RoutePlanBeatGroup[] {
  return plan.outlet_groups
    .map((group, index) => ({
      id: routePlanGroupId(group, index),
      beatId: group.beat_id,
      label: group.beat_name,
      stops: group.outlets.map(mapRouteStop),
      runOrigin: group.run_origin === "assigned_beat" ? "assigned_beat" : "unplanned_beat" as BeatRunSection,
      orderIndex: index,
    }))
    .sort((left, right) => {
      const sectionOrder = beatRunSectionOrder(left.runOrigin) - beatRunSectionOrder(right.runOrigin);
      if (sectionOrder !== 0) return sectionOrder;
      return left.orderIndex - right.orderIndex;
    })
    .map(({ orderIndex: _orderIndex, ...group }) => group);
}

function nullableText(value: string | null | undefined, fallback = "Unavailable") {
  return value?.trim() || fallback;
}

function indianMobileDigits(value: string) {
  const digits = value.replace(/\D/g, "");
  if (digits.length >= 12 && digits.startsWith("91")) return digits.slice(-10);
  if (digits.length === 11 && digits.startsWith("0")) return digits.slice(1);
  return digits.length > 10 ? digits.slice(-10) : digits;
}

function mobileTel(value: string) {
  const digits = indianMobileDigits(value);
  return digits ? `+91${digits}` : "";
}

function mobileDisplayLabel(value: string | null | undefined) {
  const trimmed = value?.trim();
  if (!trimmed) return "Mobile unavailable";
  const digits = indianMobileDigits(trimmed);
  return digits ? `+91 ${digits}` : "Mobile unavailable";
}

export function mapOutletSnapshot(outlet: OutletDetailResponse): OutletSnapshot {
  const location = outlet.latitude !== null && outlet.longitude !== null
    ? { latitude: outlet.latitude, longitude: outlet.longitude }
    : null;
  const facts = [
    { label: "Status", value: outlet.is_active === false ? "Inactive" : "Active" },
    { label: "District", value: outlet.district_name },
    outlet.registered_address ? { label: "Address", value: outlet.registered_address } : null,
    outlet.credit_limit_paise !== null && outlet.credit_limit_paise !== undefined
      ? { label: "Credit limit", value: formatPaiseToInr(outlet.credit_limit_paise) }
      : null,
    outlet.credit_outstanding_paise !== null && outlet.credit_outstanding_paise !== undefined
      ? { label: "Outstanding", value: formatPaiseToInr(outlet.credit_outstanding_paise) }
      : null,
    location
      ? { label: "Saved GPS", value: "Location captured" }
      : { label: "Saved GPS", value: "Not saved" },
  ].filter((fact): fact is { label: string; value: string } => Boolean(fact));

  return {
    contact: nullableText(outlet.contact_person),
    gst: outlet.gstin || outlet.pan || "GST/PAN unavailable",
    locality: outlet.locality?.trim() || null,
    mobileLabel: mobileDisplayLabel(outlet.contact_mobile),
    mobileTel: outlet.contact_mobile?.trim() ? mobileTel(outlet.contact_mobile) : "",
    name: outlet.name,
    location,
    facts,
    lastOrderDate: "Order history unavailable",
    lastOrderStatus: "default",
    lastOrderStatusLabel: outlet.locality ?? outlet.name,
  };
}

export function isRouteStopVisitInProgress(stop: RouteStop) {
  return stop.status === "next" || Boolean(stop.checkedInAt && !stop.checkedOutAt);
}

export function mapUnplannedRouteStop(
  outletRef: string,
  visitId: string,
  snapshot?: {
    name?: string;
    locality?: string | null;
    location?: OutletSnapshot["location"];
  } | null,
  options?: { inProgress?: boolean },
): RouteStop {
  const inProgress = options?.inProgress ?? false;
  return {
    id: visitId,
    visitId: inProgress ? visitId : null,
    outletRef,
    sequence: 0,
    outletName: snapshot?.name ?? "Outlet",
    area: snapshot?.locality?.trim() || "",
    status: inProgress ? "next" : "todo",
    planned: false,
    combinedVisitScheduled: false,
    outletLevel: "Dealer",
    location: snapshot?.location ?? undefined,
  };
}

export function findOpenRouteStop(
  stops: RouteStopItem[],
  input: { visitId?: string | null; outletRef?: string | null },
) {
  if (input.visitId) {
    const match = stops.find((stop) => stop.visit_id === input.visitId || stop.outlet_ref === input.visitId);
    if (match) return match;
  }
  if (!input.outletRef) return undefined;
  return stops.find((stop) => {
    if (stop.outlet_ref !== input.outletRef) return false;
    const visitState = stop.visit_state?.toLowerCase();
    const checkedIn = Boolean(stop.checked_in_at);
    const checkedOut = Boolean(stop.checked_out_at);
    return visitState === "in_progress" || visitState === "scheduled" || (checkedIn && !checkedOut);
  });
}

export function useUnplannedOutletSearch(enabled: boolean) {
  const actor = actorId();
  return useQuery({
    queryKey: [...routeKeys.all(actor), "unplanned-outlets"],
    queryFn: async () => unwrap(await listUnplannedOutletsApiV1RoutesUnplannedOutletsGet({
      client: getBrowserApiClient(),
      throwOnError: true,
    })),
    enabled: Boolean(actor && enabled),
    // Outlet search (C-2) never returns locality — only the per-outlet detail call (C-3) does,
    // and this list is too large to fetch one at a time — so there is no area line here.
    select: (items): UnplannedOutletChoice[] => items.map((item) => ({
      id: item.outlet_ref,
      name: item.name,
      area: "",
    })),
  });
}

export function useOutletSnapshot(outletRef: string) {
  const actor = actorId();
  return useQuery({
    queryKey: [...routeKeys.all(actor), "outlet-snapshot", outletRef],
    queryFn: async () => mapOutletSnapshot(unwrap(await getOutletDetailApiV1OutletsOutletIdGet({
      client: getBrowserApiClient(),
      path: { outlet_id: outletRef },
      throwOnError: true,
    }))),
    enabled: Boolean(actor && outletRef),
    staleTime: 30_000,
  });
}

export function useRouteDay(businessDate?: string, options: CurrentRouteOptions = {}, employeeId?: string) {
  const actor = actorId();
  const dateKey = businessDate ?? "server-today";
  return useQuery({
    queryKey: [...routeKeys.byBusinessDate(actor, dateKey), employeeId ?? "self"],
    queryFn: async () => unwrap(await getCurrentRoutePlanApiV1RoutePlansCurrentGet({
      client: getBrowserApiClient(),
      query: {
        ...(businessDate ? { business_date: businessDate } : {}),
        ...(employeeId ? { employee_id: employeeId } : {}),
      },
      throwOnError: true,
    })),
    enabled: options.enabled ?? Boolean(actor),
    retry: false,
    refetchOnWindowFocus: options.refetchOnWindowFocus ?? true,
  });
}

export function useApprovedBeatChoices() {
  const actor = actorId();
  return useQuery({
    queryKey: ["beats", { actorId: actor, status: "approved" }],
    queryFn: () => fetchAllPages(async (page) => unwrap(await listBeatsApiV1BeatsGet({
      client: getBrowserApiClient(),
      query: { status: "approved", limit: BEAT_CHOICE_PAGE_SIZE, offset: (page - 1) * BEAT_CHOICE_PAGE_SIZE },
      throwOnError: true,
    }))),
    select: (response): BeatChoice[] => response.items
      .map((beat) => {
        const runOrigin = beatRunSectionFromBeatListItem(beat);
        return {
          id: beat.id,
          name: beat.display_name,
          assignedToday: runOrigin === "assigned_beat",
          active: beat.activation_state === "active",
          runOrigin,
        };
      })
      .sort((left, right) => {
        const sectionOrder = beatRunSectionOrder(left.runOrigin) - beatRunSectionOrder(right.runOrigin);
        if (sectionOrder !== 0) return sectionOrder;
        return left.name.localeCompare(right.name);
      }),
  });
}

export function useRouteDays(input: { employeeId?: string; from?: string; to?: string }) {
  const actor = actorId();
  return useQuery({
    queryKey: [...routeKeys.all(actor), "days", input],
    queryFn: async () => unwrap(await routeDaysApiV1RoutePlansDaysGet({
      client: getBrowserApiClient(),
      query: {
        employee_id: input.employeeId!,
        from: input.from!,
        to: input.to!,
      },
      throwOnError: true,
    })),
    enabled: Boolean(actor && input.employeeId && input.from && input.to),
    staleTime: 30_000,
  });
}

export function useTeamCoverage(
  input: { businessDate?: string; onlySalesPerson?: boolean; enabled?: boolean } = {},
) {
  const actor = actorId();
  const businessDate = input.businessDate ?? istBusinessDate();
  const onlySalesPerson = input.onlySalesPerson ?? true;
  return useQuery({
    queryKey: [...coverageKeys.all(actor), "team", businessDate, onlySalesPerson],
    queryFn: async ({ signal }): Promise<CoverageResponse> => unwrap(await coverageTeamApiV1CoverageTeamGet({
      client: getBrowserApiClient(),
      query: { business_date: businessDate, only_sales_person: onlySalesPerson },
      signal,
      throwOnError: true,
    })),
    enabled: Boolean(actor) && (input.enabled ?? true),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useRoutePlanMutations() {
  const queryClient = useQueryClient();
  const actor = actorId();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: routeKeys.all(actor) });
  const switchBeat = useMutation({
    mutationFn: async (input: string | { beatId: string; idempotencyKey?: string }) => {
      const beatId = typeof input === "string" ? input : input.beatId;
      const idempotencyKey = typeof input === "string" ? createIdempotencyKey() : input.idempotencyKey ?? createIdempotencyKey();
      return (
      unwrap(await startBeatApiV1RoutePlansSwitchBeatPost({
        client: getBrowserApiClient(),
        body: { beat_id: beatId },
        headers: idempotencyHeaders(idempotencyKey),
        throwOnError: true,
      }))
      );
    },
    onSuccess: invalidate,
  });
  return { switchBeat };
}

export function useCombinedVisits() {
  const actor = actorId();
  return useQuery({
    queryKey: combinedVisitKeys.all(actor),
    queryFn: async (): Promise<{ items: CombinedVisitResponse[] }> => {
      const response = unwrap(await listCombinedVisitsApiV1CombinedVisitsGet({
        client: getBrowserApiClient(),
        throwOnError: true,
      })) as { items?: unknown } | CombinedVisitResponse[];
      if (Array.isArray(response)) return { items: response };
      return {
        items: Array.isArray(response.items)
          ? response.items.filter((item): item is CombinedVisitResponse => Boolean(item && typeof item === "object" && "id" in item))
          : [],
      };
    },
    enabled: Boolean(actor),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}

export function useCombinedVisit(combinedVisitId: string | null | undefined) {
  const actor = actorId();
  return useQuery({
    queryKey: [...combinedVisitKeys.all(actor), combinedVisitId ?? ""],
    queryFn: async () => unwrap(await getCombinedVisitApiV1CombinedVisitsCombinedVisitIdGet({
      client: getBrowserApiClient(),
      path: { combined_visit_id: combinedVisitId! },
      throwOnError: true,
    })),
    enabled: Boolean(actor && combinedVisitId),
  });
}

export function useVisitOutcome(visitId: string | null | undefined) {
  const actor = actorId();
  return useQuery({
    queryKey: [...routeKeys.all(actor), "visit-outcome", visitId ?? ""],
    queryFn: async (): Promise<VisitOutcomeDetail> => unwrap(await getVisitOutcomeApiV1VisitsVisitIdOutcomeGet({
      client: getBrowserApiClient(),
      path: { visit_id: visitId! },
      throwOnError: true,
    })),
    enabled: Boolean(actor && visitId),
  });
}

export function useLastOutletVisit(outletRef: string | null | undefined) {
  const actor = actorId();
  return useQuery({
    queryKey: [...routeKeys.all(actor), "last-outlet-visit", outletRef ?? ""],
    queryFn: async (): Promise<LastOutletVisitResponse> => unwrap(await getLastOutletVisitApiV1OutletsOutletRefLastVisitGet({
      client: getBrowserApiClient(),
      path: { outlet_ref: outletRef! },
      throwOnError: true,
    })),
    enabled: Boolean(actor && outletRef),
  });
}

export function useCombinedVisitMutations() {
  const queryClient = useQueryClient();
  const actor = actorId();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: combinedVisitKeys.all(actor) });
  const create = useMutation({
    mutationFn: async (body: CreateCombinedVisitBody) => unwrap(await createCombinedVisitApiV1CombinedVisitsPost({
      client: getBrowserApiClient(),
      body: { ...body, id: body.id ?? ulid() },
      headers: idempotencyHeaders(createIdempotencyKey()),
      throwOnError: true,
    })),
    onSuccess: invalidate,
  });
  const submitFeedback = useMutation({
    mutationFn: async (input: { combinedVisitId: string; body: CombinedVisitFeedbackBody }) =>
      unwrap(await submitCombinedVisitFeedbackApiV1CombinedVisitsCombinedVisitIdFeedbackPost({
        client: getBrowserApiClient(),
        path: { combined_visit_id: input.combinedVisitId },
        body: input.body,
        headers: idempotencyHeaders(createIdempotencyKey()),
        throwOnError: true,
      })),
    onSuccess: invalidate,
  });
  return { create, submitFeedback };
}

export function useVisitMutations(visitId: string) {
  const queryClient = useQueryClient();
  const actor = actorId();
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: routeKeys.all(actor) });
    await queryClient.invalidateQueries({ queryKey: ["today"] });
    await queryClient.invalidateQueries({ queryKey: ["missed-visits"] });
  };
  const checkIn = useMutation({
    mutationFn: async (body: CheckInBody) =>
      unwrap(await checkInApiV1VisitsVisitIdCheckInPost({
        client: getBrowserApiClient(),
        path: { visit_id: visitId },
        body,
        headers: idempotencyHeaders(createIdempotencyKey()),
        throwOnError: true,
      })),
    onSuccess: invalidate,
  });
  const outcome = useMutation({
    mutationFn: async (body: OutcomeBody) =>
      unwrap(await logOutcomeApiV1VisitsVisitIdOutcomePost({
        client: getBrowserApiClient(),
        path: { visit_id: visitId },
        body,
        headers: idempotencyHeaders(createIdempotencyKey()),
        throwOnError: true,
      })),
    onSuccess: invalidate,
  });
  const coordinateCorrection = useMutation({
    mutationFn: async (body: CoordinateCorrectionBody) =>
      unwrap(await submitCoordinateCorrectionApiV1VisitsVisitIdOutletCoordinatesPost({
        client: getBrowserApiClient(),
        path: { visit_id: visitId },
        body,
        headers: idempotencyHeaders(createIdempotencyKey()),
        throwOnError: true,
      })),
    onSuccess: invalidate,
  });
  const checkOut = useMutation({
    mutationFn: async () =>
      unwrap(await checkOutApiV1VisitsVisitIdCheckOutPost({
        client: getBrowserApiClient(),
        path: { visit_id: visitId },
        headers: idempotencyHeaders(createIdempotencyKey()),
        throwOnError: true,
      })),
    onSuccess: invalidate,
  });
  return { checkIn, coordinateCorrection, outcome, checkOut };
}

export function useMissedVisits(input?: { from?: string; to?: string }) {
  const actor = actorId();
  const from = input?.from;
  const to = input?.to;
  return useQuery({
    queryKey: ["missed-visits", { actorId: actor, from: from ?? null, to: to ?? null }],
    queryFn: async () => unwrap(await listMissedVisitsApiV1MissedVisitsGet({
      client: getBrowserApiClient(),
      query: {
        ...(from ? { from } : {}),
        ...(to ? { to } : {}),
      },
      throwOnError: true,
    })),
  });
}

const VISIT_OUTCOME_REASONS: VisitOutcomeReason[] = [
  { id: "shop_closed", icon: "Lock", label: "Shop closed" },
  { id: "no_requirement", icon: "InventoryOutlined", label: "No requirement" },
  { id: "stock_full", icon: "InventoryOutlined", label: "Stock full" },
  { id: "revisit_later", icon: "Schedule", label: "Revisit later" },
  { id: "credit_issue", icon: "Warning", label: "Credit issue" },
  { id: "other", icon: "MoreHoriz", label: "Other" },
];

export function getVisitOutcomeReasons(): VisitOutcomeReason[] {
  return VISIT_OUTCOME_REASONS;
}

export type {
  CombinedVisitResponse,
  CreateCombinedVisitBody,
  LastOutletVisitResponse,
  RouteDaysResponse,
  VisitOutcomeDetail,
};
