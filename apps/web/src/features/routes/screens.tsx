"use client";

import {
  BottomSheet,
  Button,
  DateField,
  EmptyState,
  ErrorState,
  Icon,
  ListRow,
  Select,
  Skeleton,
  SkeletonRow,
  StatusChip,
  Tabs,
  TextField,
} from "humbee-design-system";
import type { OutcomeBody, RoutePlanResponse } from "@humbee/api-contract";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { ulid } from "ulid";
import type { CSSProperties, PointerEvent as ReactPointerEvent, ReactNode } from "react";
import {
  SpActionTile,
  SpCard,
  SpInlineAlert,
  SpMetricStat,
  SpProgressBar,
  SpScreen,
  SpSectionLabel,
  SpStatusRow,
  SpStickyFooter,
} from "@/src/features/shell/components";
import { SpInlineSkeleton, SpListSkeleton, SpPageSkeleton } from "@/src/features/shell/loading";
import { useOrderDraft } from "@/src/features/orders/order-draft";
import { useOutletSellers, useOrder } from "@/src/features/orders/hooks";
import { statusChip, statusLabel } from "@/src/features/orders/screens";
import { istBusinessDate, useAttendanceToday } from "@/src/features/attendance/service";
import { ApiClientError } from "@/src/shared/api";
import { vibrate } from "@/src/shared/feedback";
import { createBrowserCapabilities, getCurrentLocationLabel } from "@/src/shared/capabilities";
import type { GeoCoordinates } from "@/src/shared/capabilities";
import { formatPaiseToInr } from "@/src/shared/formatting";
import type { BeatChoice, OutletSnapshot, RouteStop, VisitType } from "./service";
import {
  ALL_ROUTE_PLAN_GROUP_ID,
  beatRunSectionLabel,
  findOpenRouteStop,
  getVisitOutcomeReasons,
  isRouteStopVisitInProgress,
  mapRouteStop,
  mapUnplannedRouteStop,
  routePlanStartedBeatIds,
  routePlanBeatGroups,
  routePlanStops,
  useApprovedBeatChoices,
  useLastOutletVisit,
  useRouteDay,
  useMissedVisits,
  useOutletSnapshot,
  useRoutePlanMutations,
  useUnplannedOutletSearch,
  useVisitMutations,
  useVisitOutcome,
} from "./service";
import { partnerIcon } from "@/src/features/orders/service";

interface RouteView {
  visited: number;
  total: number;
  locked: boolean;
  stops: RouteStop[];
}

const EMPTY_BEATS: BeatChoice[] = [];

function routeStopHadOrder(stop: RouteStop) {
  return stop.visitOutcome === "with_order" || (stop.orderCount ?? 0) > 0;
}

function MoneyBagIcon() {
  return (
    <svg
      className="sp-route-stop-mark__money-icon"
      width={30}
      height={30}
      viewBox="0 0 430 430"
      fill="none"
      aria-hidden="true"
    >
      <g transform="translate(214.461,269)">
        <path
          fill="var(--color-primary)"
          d="M61.54,-126 C61.54,-126 105.29,-77.5 130.29,-20.5 C155.29,36.5 148.144,125.5 0.46,125.5 C-147.224,125.5 -154.96,38 -130.46,-20.5 C-105.96,-79 -61.54,-125.5 -61.54,-125.5"
        />
      </g>
      <g transform="translate(213.921,96.75)">
        <path
          fill="var(--color-primary)"
          d="M-61,46.75 C-61,46.75 -99.5,-46.75 -99.5,-46.75 C-99.5,-46.75 -68.19,-26.25 -49.95,-26.25 C-31.71,-26.25 -20.61,-46.5 -0.79,-46.5 C19.03,-46.5 27.3,-26.25 48.76,-26.25 C69.97,-26.25 99.5,-46.25 99.5,-46.25 C99.5,-46.25 63,45.75 63,45.75"
        />
      </g>
      <g
        transform="translate(227.708,185.5)"
        fill="none"
        stroke="var(--color-accent)"
        strokeWidth={7}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M52.212,-42 C52.212,-42 -77.288,-42 -77.288,-42" />
        <path d="M61.212,42 C30.712,11.5 52.212,-42 52.212,-42" />
        <path d="M75.712,8.5 C84.712,-27 52.212,-42 52.212,-42" />
      </g>
      <text
        x="214"
        y="300"
        textAnchor="middle"
        fontSize="90"
        fontWeight={700}
        fill="var(--color-text-inverse)"
      >
        ₹
      </text>
    </svg>
  );
}

function RouteStopMark({ stop }: { stop: RouteStop }) {
  const completed = stop.status === "done";
  const withOrder = completed && routeStopHadOrder(stop);
  const markClass = withOrder
    ? "sp-route-stop-mark sp-route-stop-mark--money"
    : completed
      ? "sp-route-stop-mark sp-route-stop-mark--done"
      : stop.status === "next"
        ? "sp-route-stop-mark sp-route-stop-mark--next"
        : "sp-route-stop-mark";
  const label = withOrder
    ? "Completed with order"
    : completed
      ? "Completed with no order"
      : stop.status === "next"
        ? `Stop ${stop.sequence}, in progress`
        : `Stop ${stop.sequence}`;
  return (
    <span className={markClass} aria-label={label}>
      {withOrder ? (
        <MoneyBagIcon />
      ) : completed ? (
        <Icon name="Check" size={18} color="var(--color-success)" />
      ) : stop.sequence}
    </span>
  );
}

function RouteStopTrailing({ stop }: { stop: RouteStop }) {
  const isTelephonic = stop.visitType === "Telephonic";
  if (!stop.combinedVisitScheduled && !isTelephonic) return null;
  return (
    <>
      {stop.combinedVisitScheduled ? (
        <span className="sp-route-stop-schedule" aria-label="Manager scheduled visit">
          <Icon name="Group" size={18} color="var(--color-primary)" />
        </span>
      ) : null}
      {isTelephonic ? (
        <span className="sp-route-stop-call" aria-label="Telephonic visit">
          <Icon name="Call" size={18} color="var(--color-info)" />
        </span>
      ) : null}
    </>
  );
}

function visitOutcomeLabel(stop: RouteStop) {
  if (stop.visitOutcome === "with_order") return "Order placed";
  if (stop.visitOutcome === "no_order") return "No order";
  return "Completed";
}

function noOrderReasonLabel(reasonId: string | null | undefined) {
  if (!reasonId) return null;
  return getVisitOutcomeReasons().find((reason) => reason.id === reasonId)?.label ?? reasonId.replaceAll("_", " ");
}

function visitStageLabel(visitCompleted: boolean, visitActive: boolean) {
  if (visitCompleted) return "Completed";
  if (visitActive) return "In progress";
  return "Not started";
}

function formatVisitDateTime(value: string | null | undefined) {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Not recorded";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(parsed);
}

function LastOutletVisitCard({ outletRef }: { outletRef: string }) {
  const lastVisit = useLastOutletVisit(outletRef);

  if (lastVisit.isPending) return <SpCard><SkeletonRow /></SpCard>;

  if (lastVisit.isError) {
    return (
      <SpCard>
        <div className="sp-visit-record-body">
          <SpInlineAlert tone="error">Last visit details are unavailable right now.</SpInlineAlert>
          <Button variant="outlined" color="primary" label="Retry" onClick={() => void lastVisit.refetch()} style={{ width: "100%" }} />
        </div>
      </SpCard>
    );
  }

  const visit = lastVisit.data.last_visit;
  if (!visit) {
    return (
      <div className="sp-visit-callout" data-tone="neutral">
        <div className="sp-visit-callout__row">
          <span className="sp-visit-callout__icon" data-tone="neutral">
            <Icon name="LocationMarker" size={18} color="var(--color-primary)" />
          </span>
          <div className="sp-visit-callout__copy">
            <div className="sp-body-strong--sm">Visiting first time</div>
            <div className="sp-meta sp-visit-callout__description">No earlier visits are recorded at this outlet.</div>
          </div>
        </div>
      </div>
    );
  }

  const outcomeLabel = visit.outcome === "order_placed" ? "Order placed" : "No order";
  const visitedBy = visit.employee_name ?? "Former employee";
  const rows: Array<{ label: string; value: ReactNode }> = [
    { label: "Outcome", value: <StatusChip status="completed" label={outcomeLabel} type="outlined" /> },
    { label: "Visited by", value: visitedBy },
    { label: "Visit type", value: visit.visit_type === "telephonic" ? "Telephonic" : "Physical" },
    { label: "Checked in", value: formatVisitDateTime(visit.checked_in_at) },
    { label: "Checked out", value: formatVisitDateTime(visit.checked_out_at) },
    ...(visit.order_count ? [{ label: "Orders placed", value: String(visit.order_count) }] : []),
    ...(visit.no_order_reason ? [{ label: "Reason", value: noOrderReasonLabel(visit.no_order_reason) }] : []),
  ];

  return (
    <VisitCollapsibleCard
      title={`Last visit · ${formatMissedVisitDate(visit.business_date)}`}
      subtitle={`${outcomeLabel} · ${visitedBy}`}
    >
      <div className="sp-visit-record-body">
        <div style={{ display: "grid", gap: 6 }}>
          {rows.map((row) => (
            <SpStatusRow key={row.label} label={row.label} value={row.value} labelClassName="sp-meta" valueAlign="right" />
          ))}
        </div>
        {visit.note ? (
          <div>
            <p className="sp-meta">Comment</p>
            <p style={{ margin: 0 }}>{visit.note}</p>
          </div>
        ) : null}
      </div>
    </VisitCollapsibleCard>
  );
}

function manufacturerIdForBrandOrder(brand: {
  brand_id: string;
  sellers: Array<{ seller_id: string; seller_type: string }>;
}) {
  return brand.brand_id;
}

function sellerIdForBrandOrder(brand: {
  sellers: Array<{ seller_id: string }>;
}) {
  return brand.sellers.length === 1
    ? brand.sellers[0]?.seller_id ?? undefined
    : undefined;
}

function RouteActionGate({
  title,
  back = false,
  bell = false,
  route,
  duty,
  loadingContent,
  lockMessage = "Punch in to start your day.",
  children,
}: {
  title: string;
  back?: boolean;
  bell?: boolean;
  route: ReturnType<typeof useRouteDay>;
  duty: ReturnType<typeof useAttendanceToday>;
  loadingContent: ReactNode;
  lockMessage?: string;
  children: (args: { routeDay: RoutePlanResponse; readOnly: boolean }) => ReactNode;
}) {
  const router = useRouter();
  const retryRoute = () => { void route.refetch(); };
  const retryDuty = () => { void duty.refetch(); };
  if (route.isPending || duty.isPending) return <SpScreen title={title} back={back} bell={bell}>{loadingContent}</SpScreen>;
  if (route.isError || duty.isError || !route.data) return <SpScreen title={title} back={back} bell={bell}><ErrorState onRetry={() => { retryRoute(); retryDuty(); }} /></SpScreen>;
  const readOnly = !duty.data?.on_duty && Boolean(route.data.punched_out_at);
  if (!duty.data?.on_duty && !readOnly) {
    return (
      <SpScreen title={title} back={back} bell={bell}>
        <EmptyState
          icon="Lock"
          title="Punch in first"
          message={lockMessage}
          actionLabel="Go to Today"
          onAction={() => router.push("/sp")}
        />
      </SpScreen>
    );
  }
  return <>{children({ routeDay: route.data, readOnly })}</>;
}

export function RouteScreen({ state = "running" }: { state?: "running" | "empty" | "error" | "locked" }) {
  const router = useRouter();
  const current = useRouteDay();
  const duty = useAttendanceToday();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [outletQuery, setOutletQuery] = useState("");
  const [routeGroupId, setRouteGroupId] = useState(ALL_ROUTE_PLAN_GROUP_ID);
  const routeGroups = useMemo(() => current.data ? routePlanBeatGroups(current.data) : [], [current.data]);
  const allRouteStops = useMemo(() => current.data ? routePlanStops(current.data).map(mapRouteStop) : [], [current.data]);
  const selectedRouteGroup = useMemo(
    () => routeGroupId === ALL_ROUTE_PLAN_GROUP_ID ? undefined : routeGroups.find((group) => group.id === routeGroupId),
    [routeGroupId, routeGroups],
  );
  const effectiveRouteGroupId = selectedRouteGroup ? routeGroupId : ALL_ROUTE_PLAN_GROUP_ID;
  const visibleRouteStops = selectedRouteGroup?.stops ?? allRouteStops;
  const visibleVisited = useMemo(
    () => visibleRouteStops.filter((stop) => stop.status === "done").length,
    [visibleRouteStops],
  );
  const unplannedExcludeRefs = useMemo(
    () => new Set(allRouteStops.map((stop) => stop.outletRef)),
    [allRouteStops],
  );
  const unplannedOutlets = useUnplannedOutletSearch(pickerOpen);
  const visibleUnplannedOutlets = useMemo(() => {
    const query = outletQuery.trim().toLowerCase();
    return (unplannedOutlets.data ?? []).filter((outlet) => {
      if (unplannedExcludeRefs.has(outlet.id)) return false;
      return !query || outlet.name.toLowerCase().includes(query);
    });
  }, [outletQuery, unplannedExcludeRefs, unplannedOutlets.data]);
  const activeVisitStopId = useMemo(
    () => allRouteStops.find((stop) => isRouteStopVisitInProgress(stop))?.id ?? null,
    [allRouteStops],
  );
  const activeVisitVisible = useMemo(
    () => Boolean(activeVisitStopId && visibleRouteStops.some((stop) => stop.id === activeVisitStopId)),
    [activeVisitStopId, visibleRouteStops],
  );
  const activeVisitRowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!activeVisitVisible) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const timer = window.setTimeout(() => {
      activeVisitRowRef.current?.scrollIntoView({
        behavior: reducedMotion ? "auto" : "smooth",
        block: "center",
      });
    }, reducedMotion ? 0 : 280);
    return () => window.clearTimeout(timer);
  }, [activeVisitStopId, activeVisitVisible]);
  return (
    <RouteActionGate
      title="Today's route"
      bell
      route={current}
      duty={duty}
      loadingContent={<SpPageSkeleton rows={3} />}
    >
      {({ routeDay, readOnly }) => {
        if (state === "error") return <SpScreen title="Today's route" bell><ErrorState onRetry={() => { void current.refetch(); void duty.refetch(); }} /></SpScreen>;
        const unplannedVisited = routeDay.unplanned_visit_count ?? 0;
        const route: RouteView = {
          visited: selectedRouteGroup ? visibleVisited : routeDay.visited_count,
          total: selectedRouteGroup ? visibleRouteStops.length : routeDay.planned_stop_count + unplannedVisited,
          locked: false,
          stops: visibleRouteStops,
        };
        const noActivity = routeDay.planned_stop_count === 0 && routeDay.visited_count === 0 && allRouteStops.length === 0;
        if (state === "empty" || noActivity) {
          return (
            <SpScreen title="Today's route" bell>
              <EmptyState
                icon="Calendar"
                title="Start a beat"
                message="Start a beat to begin your day."
                actionLabel="Go to My beats"
                onAction={() => router.push("/sp/beats")}
              />
            </SpScreen>
          );
        }
        const locked = state === "locked";
        const onlyUnplannedSoFar = routeDay.planned_stop_count === 0 && unplannedVisited > 0;
        const routeProgress = routeDay.coverage_pct ?? 0;
        const coverageLabel = routeDay.coverage_pct === null || routeDay.coverage_pct === undefined
          ? "—"
          : `${Math.round(routeDay.coverage_pct)}%`;
        return (
          <SpScreen title="Today's route" bell>
            {locked ? (
              <div className="sp-view-swap">
                <div className="sp-list" style={{ opacity: 0.5, pointerEvents: "none" }}>
                  {route.stops.slice(0, 4).map((stop) => (
                    <ListRow
                      key={stop.id}
                      leading={<RouteStopMark stop={{ ...stop, status: "todo" }} />}
                      title={stop.outletName}
                    />
                  ))}
                </div>
              </div>
            ) : (
              <>
                <div className="sp-route-summary">
                  <div className="sp-route-summary-top">
                    <StatusChip status="verified" label="Today's route" type="outlined" />
                    <span className="sp-route-switch-beat">
                      <Button
                        variant="outlined"
                        color="primary"
                        size="small"
                        label="Switch beat"
                        leftIcon={<span className="sp-route-switch-beat__icon" aria-hidden="true"><Icon name="Calendar" size={18} color="currentColor" /></span>}
                        rightIcon={<span className="sp-route-switch-beat__chevron" aria-hidden="true"><Icon name="KeyboardArrowRight" size={18} color="currentColor" /></span>}
                        onClick={() => router.push("/sp/beats")}
                        disabled={readOnly}
                      />
                    </span>
                  </div>
                  <div className="sp-row" style={{ margin: "var(--space-sm) 0" }}>
                    <strong className="sp-body-strong">{routeDay.planned_stop_count} planned outlets</strong>
                    <strong className="sp-body-strong" style={{ color: "var(--color-primary)" }}>
                      {routeDay.visited_count} visited · {coverageLabel}
                    </strong>
                  </div>
                  <SpProgressBar value={routeProgress} />
                  {readOnly ? <div style={{ marginTop: "var(--space-sm)" }}><SpInlineAlert>Day ended. This view is read-only.</SpInlineAlert></div> : null}
                  {routeGroups.length > 1 ? (
                    <div style={{ marginTop: "var(--space-sm)" }}>
                      <Select
                        label="Beat filter"
                        fullWidth
                        value={effectiveRouteGroupId}
                        onChange={setRouteGroupId}
                        options={[
                          { value: ALL_ROUTE_PLAN_GROUP_ID, label: `All beats (${allRouteStops.length})` },
                          ...routeGroups.map((group) => ({ value: group.id, label: `${beatRunSectionLabel(group.runOrigin).replace(" beats", " beat")} · ${group.label} (${group.stops.length})` })),
                        ]}
                      />
                      {selectedRouteGroup ? <p className="sp-meta" style={{ margin: "var(--space-xs) 0 0" }}>Showing {beatRunSectionLabel(selectedRouteGroup.runOrigin).replace(" beats", " beat")} · {selectedRouteGroup.label}</p> : null}
                    </div>
                  ) : null}
                  {onlyUnplannedSoFar && !readOnly ? (
                    <div style={{ marginTop: "var(--space-sm)" }}>
                      <SpInlineAlert tone="info">Unplanned visits are active. Start a beat to add planned outlets.</SpInlineAlert>
                    </div>
                  ) : null}
                </div>
                <div className="sp-list">
                  {route.stops.map((stop) => {
                    const visitActive = isRouteStopVisitInProgress(stop);
                    return (
                      <div
                        key={stop.id}
                        ref={visitActive && stop.id === activeVisitStopId ? activeVisitRowRef : undefined}
                        className={visitActive ? "sp-route-stop-row--active" : undefined}
                        aria-current={visitActive ? "true" : undefined}
                      >
                        <ListRow
                          leading={<RouteStopMark stop={stop} />}
                          title={stop.outletName}
                          trailing={visitActive ? (
                            <>
                              <StatusChip status="pending" label="In progress" type="outlined" />
                              <RouteStopTrailing stop={stop} />
                            </>
                          ) : (
                            <RouteStopTrailing stop={stop} />
                          )}
                          showChevron={!readOnly}
                          style={visitActive ? { minHeight: 72, paddingTop: 14, paddingBottom: 14 } : undefined}
                          onClick={readOnly ? undefined : () => router.push(`/sp/route/visit?visitId=${encodeURIComponent(stop.id)}`)}
                        />
                      </div>
                    );
                  })}
                </div>
                {!readOnly ? (
                  <div className="sp-content">
                    <div className="sp-grid">
                      <Button variant="outlined" color="primary" label="Add unplanned visit" leftIcon={<Icon name="Add" size={20} color="currentColor" />} onClick={() => setPickerOpen(true)} style={{ width: "100%" }} />
                      <Button variant="outlined" color="primary" label="Onboard outlet" leftIcon={<Icon name="InventoryOutlined" size={20} color="currentColor" />} onClick={() => router.push("/sp/outlets/new")} style={{ width: "100%" }} />
                    </div>
                    <SpInlineAlert tone="warning">Pending stops are marked as missed at the end of the day. No action is required.</SpInlineAlert>
                  </div>
                ) : null}
              </>
            )}
            <BottomSheet
              open={pickerOpen}
              onClose={() => {
                setPickerOpen(false);
                setOutletQuery("");
              }}
              title="Add unplanned visit"
            >
              <div className="sp-stack">
                <TextField placeholder="Search outlets" startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />} value={outletQuery} onChange={(event) => setOutletQuery((event.target as HTMLInputElement).value)} />
                {unplannedOutlets.isFetching ? (
                  <div className="sp-list">{[0, 1, 2, 3, 4].map((item) => <SkeletonRow key={item} />)}</div>
                ) : unplannedOutlets.isError ? (
                  <ErrorState title="Outlets unavailable" message="Outlet search could not be loaded right now." onRetry={() => void unplannedOutlets.refetch()} />
                ) : !visibleUnplannedOutlets.length ? (
                  <EmptyState
                    icon="SearchOutlined"
                    title={outletQuery.trim() ? `No outlets match "${outletQuery.trim()}"` : "No outlets left to visit"}
                    message={outletQuery.trim() ? "Try another outlet name." : "You have no other assigned outlets left to visit today."}
                    actionLabel={outletQuery.trim() ? "Clear search" : "Close"}
                    onAction={() => {
                      if (outletQuery.trim()) {
                        setOutletQuery("");
                        return;
                      }
                      setPickerOpen(false);
                    }}
                  />
                ) : (
                  <div className="sp-list">
                    {visibleUnplannedOutlets.map((outlet) => (
                      <ListRow
                        key={outlet.id}
                        leading={<Icon name="InventoryOutlined" size={22} color="var(--color-primary)" />}
                        title={outlet.name}
                        subtitle={outlet.area}
                        showChevron
                        onClick={() => {
                          setPickerOpen(false);
                          setOutletQuery("");
                          const params = new URLSearchParams({
                            outletRef: outlet.id,
                            name: outlet.name,
                            area: outlet.area,
                          });
                          router.push(`/sp/route/visit?${params.toString()}`);
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            </BottomSheet>
          </SpScreen>
        );
      }}
    </RouteActionGate>
  );
}

export function BeatChooserScreen({ mode = "another" }: { mode?: "start" | "another" }) {
  const router = useRouter();
  const beatsQuery = useApprovedBeatChoices();
  const duty = useAttendanceToday({ refetchOnWindowFocus: false });
  const current = useRouteDay(undefined, { refetchOnWindowFocus: false });
  const mutations = useRoutePlanMutations();
  const beats = beatsQuery.data ?? EMPTY_BEATS;
  const [selected, setSelected] = useState("");
  const startingFirstBeat = mode === "start";
  const title = startingFirstBeat ? "Today's route" : "Start another beat";
  const startedBeatIds = useMemo(() => routePlanStartedBeatIds(current.data), [current.data]);
  const selectedBeatId = selected && !startedBeatIds.has(selected)
    ? selected
    : beats.find((beat) => beat.active && !startedBeatIds.has(beat.id))?.id || "";
  const beatSections = useMemo(
    () => (["assigned_beat", "unplanned_beat", "draft_beat"] as const)
      .map((section) => ({
        section,
        heading: beatRunSectionLabel(section),
        items: beats.filter((beat) => beat.runOrigin === section),
      }))
      .filter((section) => section.items.length),
    [beats],
  );
  const routeStartError = mutations.switchBeat.error;
  if (beatsQuery.isPending || duty.isPending || current.isPending) {
    return <SpScreen title={title} back={!startingFirstBeat} bell={startingFirstBeat}><SpPageSkeleton rows={3} /></SpScreen>;
  }
  if (beatsQuery.isError || duty.isError) return <SpScreen title={title} back={!startingFirstBeat} bell={startingFirstBeat}><ErrorState onRetry={() => { void beatsQuery.refetch(); void duty.refetch(); }} /></SpScreen>;
  if (!duty.data?.on_duty) return <SpScreen title={title} back={!startingFirstBeat} bell={startingFirstBeat}><EmptyState icon="Lock" title="Punch in first" message="Starting a beat stays locked until attendance is confirmed." actionLabel="Go to Today" onAction={() => router.push("/sp")} /></SpScreen>;
  if (!beats.some((beat) => beat.active)) {
    return <SpScreen title={title} back={!startingFirstBeat} bell={startingFirstBeat}><EmptyState icon="Calendar" title="No approved beats" message="You need an approved beat before you can start a route. Create one and wait for manager approval." actionLabel="Go to beats" onAction={() => router.push("/sp/beats")} /></SpScreen>;
  }
  return (
    <SpScreen title={title} back={!startingFirstBeat} bell={startingFirstBeat}>
      {beatSections.map(({ section, heading, items }) => (
        <div key={section}>
          <div style={{ padding: "var(--space-md) var(--space-md) var(--space-sm)" }}><SpSectionLabel>{heading}</SpSectionLabel></div>
          <div className="sp-list">
            {items.map((beat) => {
          const alreadyStarted = startedBeatIds.has(beat.id);
          const disabled = alreadyStarted || !beat.active;
          const selectedBeat = selectedBeatId === beat.id;
          const statusMeta = alreadyStarted ? "Already in today's route" : beat.active ? "Available" : "Inactive";
          return (
            <div key={beat.id} className="sp-beat-choice" data-active={selectedBeat} data-disabled={disabled}>
              <ListRow
                disabled={disabled}
                leading={alreadyStarted ? (
                  <span className="sp-started-beat-icon" aria-label="Started today">
                    <Icon name="Check" size={18} color="currentColor" />
                  </span>
                ) : <Icon name={section === "assigned_beat" ? "LocationMarker" : section === "draft_beat" ? "Edit" : "Calendar"} size={22} color={selectedBeat ? "var(--color-text-inverse)" : "var(--color-text-placeholder)"} />}
                title={<span style={{ color: selectedBeat ? "var(--color-text-inverse)" : "inherit" }}>{beat.name}</span>}
                subtitle={<span style={{ color: selectedBeat ? "var(--color-text-inverse)" : "inherit" }}>{statusMeta}</span>}
                trailing={alreadyStarted ? <StatusChip status="verified" label="Started" type="outlined" /> : selectedBeat ? <Icon name="Check" size={22} color="var(--color-text-inverse)" /> : null}
                style={{ background: "transparent", boxShadow: "none" }}
                onClick={disabled ? undefined : () => setSelected(beat.id)}
              />
            </div>
          );
            })}
          </div>
        </div>
      ))}
      <div className="sp-content">
        <SpInlineAlert>{startingFirstBeat ? "Choose an approved beat to build today's route." : "Choose an approved beat to add its outlets to today's route."}</SpInlineAlert>
        {routeStartError ? (
          <SpInlineAlert tone="error">
            {routeStartError instanceof ApiClientError
              ? routeStartError.message
              : "Route could not be started. Try again."}
          </SpInlineAlert>
        ) : null}
      </div>
      <SpStickyFooter><Button variant="filled" color="primary" label={startingFirstBeat ? "Start selected beat" : "Add selected beat"} leftIcon={<Icon name="Calendar" size={18} color="currentColor" />} loading={mutations.switchBeat.isPending} disabled={!selectedBeatId || mutations.switchBeat.isPending} onClick={() => mutations.switchBeat.mutate(selectedBeatId, { onSuccess: () => { if (!startingFirstBeat) router.push("/sp/route"); } })} style={{ width: "100%" }} /></SpStickyFooter>
    </SpScreen>
  );
}

function routeAreaLabel(area: string) {
  const label = area.trim();
  return label || null;
}

function useRouteLocationLabel(location: RouteStop["location"] | null | undefined, keyPart: string) {
  return useQuery({
    queryKey: location
      ? ["location-label", "routes", keyPart, location.latitude, location.longitude]
      : ["location-label", "routes", keyPart, "none"],
    queryFn: () => {
      if (!location) return Promise.reject(new Error("Location is unavailable."));
      return getCurrentLocationLabel({
        latitude: location.latitude,
        longitude: location.longitude,
        accuracyMeters: 0,
        capturedAt: 0,
      });
    },
    enabled: Boolean(location),
    staleTime: 600_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}

function VisitCollapsibleCard({
  title,
  subtitle,
  defaultOpen = false,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <SpCard padded={false}>
      <button
        type="button"
        className="sp-visit-collapsible__toggle"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        <span className="sp-visit-collapsible__copy">
          <strong className="sp-body-strong">{title}</strong>
          {subtitle ? <span className="sp-meta">{subtitle}</span> : null}
        </span>
        <span className={`sp-visit-collapsible__chevron${open ? " sp-visit-collapsible__chevron--open" : ""}`}>
          <Icon name="KeyboardArrowRight" size={20} color="currentColor" />
        </span>
      </button>
      {open ? <div className="sp-visit-collapsible__body">{children}</div> : null}
    </SpCard>
  );
}

function OutletVisitSummaryCard({
  data,
  isError,
  isPending,
  onRetry,
  outletTone,
  savedLocation,
  savedLocationLabel,
  stop,
  visitCompleted,
  visitActive,
  visitType,
}: {
  data?: OutletSnapshot;
  isError: boolean;
  isPending: boolean;
  onRetry: () => void;
  outletTone: string;
  savedLocation?: RouteStop["location"];
  savedLocationLabel?: string;
  stop: RouteStop;
  visitCompleted: boolean;
  visitActive: boolean;
  visitType: VisitType;
}) {
  const outletIcon = partnerIcon(stop.outletLevel === "Dealer" ? "dealer" : "distribution_partner");
  const [detailsExpanded, setDetailsExpanded] = useState(false);
  const outletLocality = data?.locality ?? routeAreaLabel(stop.area);
  const outletName = data?.name ?? stop.outletName;
  const lifecycleLabel = visitStageLabel(visitCompleted, visitActive);
  const lifecycleStatus = visitCompleted
    ? "completed"
    : visitActive
      ? "pending"
      : "default";
  const header = (
    <div className="sp-visit-summary-head">
      <div className="sp-visit-summary-head__top">
        <span className="sp-visit-summary-head__icon" style={{ color: outletTone }}>
          <Icon name={outletIcon} size={20} color="currentColor" />
        </span>
        <div className="sp-visit-summary-head__copy">
          <h2 className="sp-title sp-visit-summary-head__name" title={outletName}>{outletName}</h2>
          {outletLocality ? (
            <p className="sp-meta sp-visit-summary-head__locality">
              <Icon name="LocationPin" size={16} color="var(--color-text-placeholder)" /> {outletLocality}
            </p>
          ) : null}
          <div className="sp-visit-summary-head__meta">
            <span className="sp-visit-summary-head__meta-item">{stop.planned ? "Planned visit" : "Unplanned visit"}</span>
            <span className="sp-visit-summary-head__meta-item">{visitType}</span>
            {visitCompleted ? <span className="sp-visit-summary-head__meta-item">{visitOutcomeLabel(stop)}</span> : null}
          </div>
        </div>
        <span className="sp-visit-summary-head__stage">
          <StatusChip status={lifecycleStatus} label={lifecycleLabel} type="outlined" />
        </span>
      </div>
    </div>
  );

  if (isPending) {
    return (
      <SpCard>
        <div className="sp-visit-summary">
          {header}
          <div className="sp-visit-summary-facts">
            {[0, 1, 2, 3].map((item) => (
              <div key={item} className="sp-visit-summary-fact sp-visit-summary-fact--loading">
                <Skeleton width={72} height={12} />
                <Skeleton width={140} height={14} />
              </div>
            ))}
          </div>
        </div>
      </SpCard>
    );
  }

  if (isError) {
    return (
      <SpCard>
        <div className="sp-visit-summary">
          {header}
          <div className="sp-visit-summary-feedback">
            <SpInlineAlert tone="error">Outlet details are unavailable right now.</SpInlineAlert>
          </div>
          <Button
            variant="outlined"
            color="primary"
            label="Retry"
            onClick={onRetry}
            style={{ marginTop: "var(--space-sm)", width: "100%" }}
          />
        </div>
      </SpCard>
    );
  }

  if (!data) {
    return (
      <SpCard>
        <div className="sp-visit-summary">
          {header}
          <div className="sp-visit-summary-feedback">
            <EmptyState icon="InventoryOutlined" title="Outlet details unavailable" message="No outlet snapshot was returned for this visit." />
          </div>
        </div>
      </SpCard>
    );
  }

  const status = data.facts.find((fact) => fact.label === "Status")?.value ?? "Active";
  const detailFacts = data.facts
    .filter((fact) => fact.label !== "Status")
    .map((fact) => fact.label === "Saved GPS" && savedLocation
      ? { ...fact, value: savedLocationLabel ?? fact.value }
      : fact);
  const summaryFacts: Array<{ label: string; value: ReactNode }> = [
    { label: "GST/PAN", value: data.gst || "Not available" },
    {
      label: "Status",
      value: <StatusChip status={status === "Inactive" ? "cancelled" : "verified"} label={status} type="outlined" />,
    },
    ...detailFacts.map((fact) => ({ label: fact.label, value: fact.value || "Not available" })),
  ];
  return (
    <SpCard>
      <div className="sp-visit-summary">
        {header}
        <div className="sp-visit-summary-inline">
          <span className="sp-visit-summary-inline__item">
            <strong className="sp-body-strong--sm sp-visit-summary-contact__name">{data.contact || "Not available"}</strong>
            {data.mobileTel ? (
              <a href={`tel:${data.mobileTel}`} className="sp-visit-summary-call">
                <Icon name="Call" size={16} color="currentColor" />
                {data.mobileLabel}
              </a>
            ) : (
              <span className="sp-meta">{data.mobileLabel || "Not available"}</span>
            )}
          </span>
        </div>
        <button
          type="button"
          className="sp-visit-summary-toggle"
          onClick={() => setDetailsExpanded((open) => !open)}
          aria-expanded={detailsExpanded}
        >
          <span>{detailsExpanded ? "Hide outlet details" : "View outlet details"}</span>
          <span className={`sp-visit-summary-toggle__chevron${detailsExpanded ? " sp-visit-summary-toggle__chevron--open" : ""}`}>
            <Icon name="KeyboardArrowRight" size={18} color="currentColor" />
          </span>
        </button>
        {detailsExpanded ? (
          <div className="sp-visit-summary-facts">
            {summaryFacts.map((fact, index) => (
              <div className="sp-visit-summary-fact" key={`${fact.label}-${index}`}>
                <span className="sp-meta">{fact.label}</span>
                <strong className="sp-body-strong--sm">{fact.value}</strong>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </SpCard>
  );
}

export function OutletVisitScreen({
  stopId,
  outletRef,
  outletName,
  outletArea,
}: {
  stopId?: string | null;
  outletRef?: string | null;
  outletName?: string | null;
  outletArea?: string | null;
}) {
  const router = useRouter();
  const route = useRouteDay(undefined, { refetchOnWindowFocus: false });
  const duty = useAttendanceToday({ refetchOnWindowFocus: false });
  const [unplannedVisitId] = useState(() => ulid());
  const pendingOutletRef = outletRef ?? "";
  return (
    <RouteActionGate
      title={outletName || "Visit"}
      back
      route={route}
      duty={duty}
      loadingContent={<div className="sp-content">{[0, 1, 2].map((item) => <SkeletonRow key={item} />)}</div>}
      lockMessage="Punch in to start your day."
    >
      {({ routeDay }) => {
        const apiStop = findOpenRouteStop(routePlanStops(routeDay), { visitId: stopId, outletRef });
        if (apiStop) return <OutletVisitContent stop={mapRouteStop(apiStop)} />;
        if (!pendingOutletRef) {
          return (
            <SpScreen title="Visit" back>
              <EmptyState
                icon="LocationPin"
                title="Visit unavailable"
                message="This stop is not part of the current route."
                actionLabel="Back to route"
                onAction={() => router.push("/sp/route")}
              />
            </SpScreen>
          );
        }
        const resolvedVisitId = stopId ?? unplannedVisitId;
        return (
          <OutletVisitContent
            stop={mapUnplannedRouteStop(pendingOutletRef, resolvedVisitId, {
              name: outletName?.trim() || "Outlet",
              locality: outletArea?.trim() || null,
            }, { inProgress: Boolean(stopId) })}
          />
        );
      }}
    </RouteActionGate>
  );
}

function VisitOrderSummaryRow({ orderId }: { orderId: string }) {
  const router = useRouter();
  const order = useOrder(orderId);
  if (order.isPending) return <SkeletonRow />;
  if (order.isError || !order.data) {
    return <ListRow title="Order unavailable" subtitle={orderId} />;
  }
  const detail = order.data;
  return (
    <ListRow
      leading={<Icon name="ShoppingCartOutlined" size={22} color="var(--color-primary)" />}
      title={detail.order_number}
      subtitle={`${detail.counterparty_name} · ${detail.business_date}`}
      meta={formatPaiseToInr(detail.gross_total_paise)}
      trailing={<StatusChip status={statusChip(detail.status)} label={statusLabel(detail.status)} type="outlined" />}
      showChevron
      onClick={() => router.push(`/sp/orders/detail?orderId=${encodeURIComponent(orderId)}`)}
    />
  );
}

function OutletVisitContent({ stop }: { stop: RouteStop }) {
  const router = useRouter();
  const { beginVisitOrder, completeVisit } = useOrderDraft();
  const stopVisitInProgress = isRouteStopVisitInProgress(stop);
  const [activeVisitId, setActiveVisitId] = useState(stop.visitId ?? (stopVisitInProgress ? stop.id : null));
  const mutationVisitId = activeVisitId ?? stop.id;
  const visits = useVisitMutations(mutationVisitId);
  const [visitType, setVisitType] = useState<VisitType>(stop.visitType ?? "Physical");
  const [visitState, setVisitState] = useState<"idle" | "locating" | "active">(stopVisitInProgress ? "active" : "idle");
  const [savedOutletLocation, setSavedOutletLocation] = useState(stop.location);
  const [capturedLocation, setCapturedLocation] = useState<GeoCoordinates | null>(null);
  const [locationAdded, setLocationAdded] = useState(false);
  const [addingShopLocation, setAddingShopLocation] = useState(false);
  const [coordinateSaveError, setCoordinateSaveError] = useState<string | null>(null);
  const visitCompleted = stop.status === "done";
  const visitOutcomeDetail = useVisitOutcome(visitCompleted ? mutationVisitId : null);
  const isTelephonic = visitType === "Telephonic";
  const isPhysical = visitType === "Physical";
  const visitActive = (visitState === "active" || stopVisitInProgress) && !visitCompleted;

  const [syncedStop, setSyncedStop] = useState(stop);
  if (
    syncedStop.id !== stop.id
    || syncedStop.visitId !== stop.visitId
    || syncedStop.status !== stop.status
    || syncedStop.checkedInAt !== stop.checkedInAt
    || syncedStop.checkedOutAt !== stop.checkedOutAt
  ) {
    setSyncedStop(stop);
    if (stopVisitInProgress) {
      setVisitState((current) => (current === "locating" ? current : "active"));
      setActiveVisitId(stop.visitId ?? stop.id);
    }
  }
  const outletTone = stop.outletLevel === "Dealer" ? "var(--color-info)" : "var(--color-primary)";
  const outletSnapshot = useOutletSnapshot(stop.outletRef);
  const outletSnapshotLocation = outletSnapshot.data?.location ?? null;
  const effectiveSavedOutletLocation = savedOutletLocation ?? outletSnapshotLocation;
  const checkInLocation = stop.checkinGps
    ? { latitude: stop.checkinGps.lat, longitude: stop.checkinGps.lng }
    : capturedLocation
      ? { latitude: capturedLocation.latitude, longitude: capturedLocation.longitude }
      : null;
  const savedLocationLabelQuery = useRouteLocationLabel(effectiveSavedOutletLocation ?? undefined, `${stop.id}:saved`);
  const checkInLocationLabelQuery = useRouteLocationLabel(checkInLocation, `${stop.id}:checkin`);
  const fallbackAreaLabel = routeAreaLabel(stop.area);
  const savedGpsLabel = !effectiveSavedOutletLocation
    ? "Not saved"
    : savedLocationLabelQuery.isPending
      ? "Resolving location..."
      : savedLocationLabelQuery.data ?? fallbackAreaLabel ?? "Location unavailable";
  const hasSavedOutletLocation = Boolean(effectiveSavedOutletLocation) || locationAdded;
  const checkingSavedOutletLocation = isPhysical && !hasSavedOutletLocation && outletSnapshot.isPending;
  const outletSellers = useOutletSellers(stop.outletRef);
  const brandChoices = useMemo(
    () => (outletSellers.data?.sellers_by_brand ?? [])
      .map((brand) => ({
        ...brand,
        sellers: brand.sellers.filter((seller) => seller.is_active),
      })),
    [outletSellers.data],
  );
  const orderableBrands = useMemo(
    () => brandChoices.filter((brand) => brand.sellers.length > 0),
    [brandChoices],
  );
  const singleBrand = orderableBrands.length === 1 ? orderableBrands[0] : null;
  const orderEntry = singleBrand && mutationVisitId && (activeVisitId || stopVisitInProgress)
    ? {
      visitId: mutationVisitId,
      outletId: stop.outletRef,
      manufacturerId: manufacturerIdForBrandOrder(singleBrand),
      sellerId: sellerIdForBrandOrder(singleBrand),
    }
    : null;
  const hasMultipleSources = orderableBrands.length > 1;
  const hasOrderTaken = (stop.orderCount ?? 0) > 0;
  const visitOutcomePath = `/sp/route/outcome?visitId=${encodeURIComponent(mutationVisitId)}&withOrder=${hasOrderTaken ? "1" : "0"}`;
  const startBrandOrder = (brand: typeof brandChoices[number]) => {
    if (!brand.sellers.length) return;
    if (!mutationVisitId || (!activeVisitId && !stopVisitInProgress)) return;
    beginVisitOrder(
      orderableBrands.map((item) => item.brand_id),
      stop.id,
      {
        visitId: mutationVisitId,
        outletId: stop.outletRef,
        manufacturerId: manufacturerIdForBrandOrder(brand),
        sellerId: sellerIdForBrandOrder(brand),
      },
      brandChoices,
      stop.outletRef,
    );
    router.push("/sp/orders/new");
  };
  const checkInLocationLabel = !checkInLocation
    ? null
    : checkInLocationLabelQuery.isPending
      ? "Resolving location..."
      : checkInLocationLabelQuery.data ?? fallbackAreaLabel ?? "Location unavailable";
  const currentLocationName = !isPhysical
    ? null
    : hasSavedOutletLocation
      ? savedGpsLabel
      : checkInLocationLabel;
  const activeVisitLocationLabel = currentLocationName ?? fallbackAreaLabel ?? "Location unavailable";
  const checkInGpsLabel = checkInLocationLabel ?? "Not recorded";

  const chooseVisitType = (type: VisitType) => {
    if (visitActive || visitCompleted) return;
    setVisitType(type);
    setVisitState("idle");
    setCapturedLocation(null);
    setCoordinateSaveError(null);
  };

  const captureLocation = async () => {
    setVisitState("locating");
    try {
      const location = await createBrowserCapabilities().getCurrentLocation();
      setCapturedLocation(location);
      return location;
    } catch {
      setVisitState("idle");
      return null;
    }
  };

  const startVisit = async () => {
    if (!visitType || visitCompleted) return;
    let fix = capturedLocation;
    if (isPhysical) {
      fix ??= await captureLocation();
      if (!fix) return;
    }
    try {
      const visit = await visits.checkIn.mutateAsync({
        visit_type: isTelephonic ? "telephonic" : "physical",
        occurred_at: new Date().toISOString(),
        outlet_ref: activeVisitId ? null : stop.outletRef,
        gps: fix ? { lat: fix.latitude, lng: fix.longitude, accuracy_m: fix.accuracyMeters, provider: "gps", is_mock: false } : null,
        note: null,
      });
      setActiveVisitId(visit.id);
      setVisitState("active");
    } catch {
      setVisitState("idle");
    }
  };

  const addShopLocation = async () => {
    setAddingShopLocation(true);
    setCoordinateSaveError(null);
    try {
      const location = await createBrowserCapabilities().getCurrentLocation();
      setCapturedLocation(location);
      const correction = await visits.coordinateCorrection.mutateAsync({
        lat: location.latitude,
        lng: location.longitude,
        accuracy_m: location.accuracyMeters,
        provider: "gps",
        captured_at: new Date(location.capturedAt).toISOString(),
      });
      const nextLocation = {
        latitude: correction.latitude ?? location.latitude,
        longitude: correction.longitude ?? location.longitude,
      };
      if (correction.status === "accepted") {
        setSavedOutletLocation(nextLocation);
        setLocationAdded(true);
        setCoordinateSaveError(null);
      } else {
        setCoordinateSaveError(correction.rejection_code ? `GPS was rejected: ${correction.rejection_code}.` : "GPS could not be saved. Try again.");
      }
    } catch {
      setCoordinateSaveError("GPS could not be saved. Try again.");
      return;
    } finally {
      setAddingShopLocation(false);
    }
  };

  const endVisit = () => {
    visits.checkOut.mutate(undefined, {
      onError: (error) => {
        if (error instanceof ApiClientError && error.code === "outcome_required") {
          router.push(visitOutcomePath);
        }
      },
      onSuccess: () => {
        completeVisit();
        router.push("/sp/route");
      },
    });
  };

  return (
    <SpScreen title={outletSnapshot.data?.name ?? stop.outletName} back>
      <div className="sp-content sp-visit-content">
        <div className="sp-visit-layout">
          <div className="sp-visit-layout__main">
            <OutletVisitSummaryCard
              data={outletSnapshot.data}
              isError={outletSnapshot.isError}
              isPending={outletSnapshot.isPending}
              onRetry={() => void outletSnapshot.refetch()}
              outletTone={outletTone}
              savedLocation={effectiveSavedOutletLocation ?? undefined}
              savedLocationLabel={savedGpsLabel}
              stop={stop}
              visitCompleted={visitCompleted}
              visitActive={visitActive}
              visitType={visitType}
            />

            {stop.outletRef ? (
              <Button
                variant="outlined"
                color="primary"
                label="Open full outlet insights"
                leftIcon={<Icon name="Dashboard" size={18} color="currentColor" />}
                onClick={() => {
                  const params = new URLSearchParams({ outletId: stop.outletRef });
                  const name = outletSnapshot.data?.name ?? stop.outletName;
                  if (name) params.set("name", name);
                  router.push(`/sp/route/insights?${params.toString()}`);
                }}
                style={{ width: "100%" }}
              />
            ) : null}

            {!visitCompleted && stop.outletRef ? <LastOutletVisitCard outletRef={stop.outletRef} /> : null}

            {visitCompleted ? (
              <VisitCollapsibleCard
                title="Visit record"
                subtitle={`${visitOutcomeLabel(stop)} · ${stop.visitType ?? "Visit type not recorded"}`}
              >
                <div className="sp-visit-record-body">
                  <div style={{ display: "grid", gap: 6 }}>
                    <SpStatusRow
                      label="Outcome"
                      value={<StatusChip status="completed" label={visitOutcomeLabel(stop)} type="outlined" />}
                      labelClassName="sp-meta"
                      valueAlign="right"
                    />
                    <SpStatusRow
                      label="Visit type"
                      value={stop.visitType ?? "Not recorded"}
                      labelClassName="sp-meta"
                      valueAlign="right"
                    />
                    <SpStatusRow
                      label="Checked in"
                      value={formatVisitDateTime(stop.checkedInAt)}
                      labelClassName="sp-meta"
                      valueAlign="right"
                    />
                    <SpStatusRow
                      label="Checked out"
                      value={formatVisitDateTime(stop.checkedOutAt)}
                      labelClassName="sp-meta"
                      valueAlign="right"
                    />
                    <SpStatusRow
                      label="Check-in GPS"
                      value={checkInGpsLabel}
                      labelClassName="sp-meta"
                      valueAlign="right"
                    />
                    {visitOutcomeDetail.data?.no_order_reason ? (
                      <SpStatusRow
                        label="Reason"
                        value={noOrderReasonLabel(visitOutcomeDetail.data.no_order_reason)}
                        labelClassName="sp-meta"
                        valueAlign="right"
                      />
                    ) : null}
                  </div>
                  {visitOutcomeDetail.data?.note ? (
                    <div>
                      <p className="sp-meta">Comment</p>
                      <p style={{ margin: 0 }}>{visitOutcomeDetail.data.note}</p>
                    </div>
                  ) : null}
                  {visitOutcomeDetail.data?.order_ids?.length ? (
                    <div>
                      <SpSectionLabel>
                        Orders placed · {visitOutcomeDetail.data.order_ids.length}
                      </SpSectionLabel>
                      <SpCard padded={false}>
                        <div className="sp-list">
                          {visitOutcomeDetail.data.order_ids.map((orderId) => (
                            <VisitOrderSummaryRow key={orderId} orderId={orderId} />
                          ))}
                        </div>
                      </SpCard>
                    </div>
                  ) : null}
                </div>
              </VisitCollapsibleCard>
            ) : (
              <div>
                <SpSectionLabel>Visit controls</SpSectionLabel>
                <SpCard>
                  <div className="sp-visit-session-wrapper">
                    <div className="sp-visit-session">

                      {!visitActive ? (
                        <div className="sp-visit-session__type">
                          <p className="sp-meta sp-visit-session__type-label">Visit type</p>
                          <div className="sp-task-tabs sp-visit-session__tabs">
                            <Tabs
                              tabs={[{ label: "Physical", value: "Physical" }, { label: "Telephonic", value: "Telephonic" }]}
                              value={visitType}
                              onChange={(value) => chooseVisitType(value as VisitType)}
                              type="boxed"
                              size="medium"
                              style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", width: "100%" }}
                            />
                          </div>
                        </div>
                      ) : null}

                      {visitActive && isPhysical && !hasSavedOutletLocation && !checkingSavedOutletLocation ? (
                        <>
                            <div className="sp-visit-callout__actions sp-visit-callout__actions--inline">
                              <Button
                                variant="filled"
                                color="primary"
                                size="small"
                                label="Save outlet location"
                                leftIcon={<Icon name="GpsFixed" size={18} color="currentColor" />}
                                loading={addingShopLocation || visits.coordinateCorrection.isPending}
                                disabled={addingShopLocation || visits.coordinateCorrection.isPending}
                                onClick={() => void addShopLocation()}
                                style={{ minHeight: 38, paddingInline: 12, width: "100%" }}
                              />
                            </div>
                          {coordinateSaveError ? <div style={{ marginTop: 6 }}><SpInlineAlert tone="warning">{coordinateSaveError}</SpInlineAlert></div> : null}
                      </>
                      ) : null}

                      {visitActive ? (
                          <SlideToVisitAction
                            label={isTelephonic ? "Slide to end call" : "Slide to end visit"}
                            pendingLabel="Ending..."
                            pending={visits.checkOut.isPending}
                            onComplete={endVisit}
                            compact
                            tone="primary"
                            hapticOnComplete
                          />
                      ) : (
                        <div className="sp-visit-callout" data-tone="neutral">
                          <div className="sp-visit-callout__row">
                            <span className="sp-visit-callout__icon" data-tone="neutral">
                              <Icon name={isTelephonic ? "Call" : "GpsFixed"} size={18} color="var(--color-primary)" />
                            </span>
                            <div className="sp-visit-callout__copy">
                              <div className="sp-body-strong--sm">{isTelephonic ? "Start telephonic call" : "Ready to start physical visit"}</div>
                              <div className="sp-meta sp-visit-callout__description">
                                {isTelephonic
                                  ? "Start the call visit without capturing outlet GPS."
                                  : checkingSavedOutletLocation
                                    ? <SpInlineSkeleton width="54%" height={12} />
                                    : hasSavedOutletLocation
                                      ? currentLocationName
                                        ? `Saved shop GPS: ${currentLocationName}`
                                        : "Current GPS will be captured when the visit starts."
                                      : "Current GPS will be captured when the visit starts."}
                              </div>
                            </div>
                          </div>

                          <SlideToVisitAction
                            label={isTelephonic ? "Slide to start call" : "Slide to start physical visit"}
                            pendingLabel={visitState === "locating" ? "Capturing GPS..." : "Starting..."}
                            pending={visitState === "locating" || visits.checkIn.isPending}
                            onComplete={startVisit}
                          />
                        </div>
                      )}

                      {visits.checkIn.isError ? <SpInlineAlert tone="error">{visits.checkIn.error instanceof ApiClientError ? visits.checkIn.error.message : "Visit could not be started. Try again."}</SpInlineAlert> : null}
                    </div>
                  </div>
                </SpCard>
              </div>
            )}
          </div>

          {!visitCompleted ? (
            <div className="sp-visit-layout__aside">
              <div>
                <SpSectionLabel>Order placement</SpSectionLabel>
                <SpCard>
                <div className="sp-visit-order-body">
                  {!visitActive ? (
                    <SpInlineAlert tone="info">Start the visit to unlock order placement for linked manufacturers.</SpInlineAlert>
                  ) : outletSellers.isPending ? (
                    <SpListSkeleton rows={3} />
                  ) : outletSellers.isError ? (
                    <>
                      <SpInlineAlert tone="error">Seller data is unavailable right now.</SpInlineAlert>
                      <Button
                        variant="outlined"
                        color="primary"
                        label="Retry"
                        onClick={() => void outletSellers.refetch()}
                        style={{ marginTop: "var(--space-sm)", width: "100%" }}
                      />
                    </>
                  ) : brandChoices.length ? (
                    <div className="sp-visit-order-stack">
                      <div className="sp-list">
                        {brandChoices.map((brand) => (
                          <ListRow
                            key={brand.brand_id}
                            leading={<span className="sp-partner-mark"><Icon name="InventoryOutlined" size={22} color="currentColor" /></span>}
                            title={brand.brand_name}
                            subtitle={[
                              brand.sellers.length
                                ? `${brand.sellers.length} active seller${brand.sellers.length === 1 ? "" : "s"}`
                                : "No active sellers linked",
                              brand.sellers.some((seller) => seller.requires_purchase_order) ? "PO path available" : "Direct path",
                              brand.sellers_filtered_by_district ? "District filtered" : "Wider seller list",
                            ].join(" · ")}
                            disabled={!visitActive || !brand.sellers.length}
                            showChevron
                            onClick={() => startBrandOrder(brand)}
                          />
                        ))}
                      </div>
                      <Button
                        variant="filled"
                        color="primary"
                        disabled={!visitActive || (!hasMultipleSources && !orderEntry)}
                        label={hasMultipleSources ? "Choose manufacturer" : `Order from ${singleBrand?.brand_name ?? "selected manufacturer"}`}
                        rightIcon={<Icon name="KeyboardArrowRight" size={20} color="currentColor" />}
                        onClick={() => {
                          if (!stop.visitId) return;
                          beginVisitOrder(
                            orderableBrands.map((brand) => brand.brand_id),
                            stop.id,
                            orderEntry ?? undefined,
                            brandChoices,
                            stop.outletRef,
                          );
                          router.push(
                            hasMultipleSources
                              ? "/sp/orders/new/manufacturer"
                              : "/sp/orders/new",
                          );
                        }}
                        style={{ width: "100%" }}
                      />
                    </div>
                  ) : (
                    <EmptyState
                      icon="Lock"
                      title="No active sellers linked"
                      message="This outlet has no active seller relationship for order placement."
                      actionLabel="View orders"
                      onAction={() => router.push("/sp/orders")}
                    />
                  )}
                </div>
                </SpCard>
              </div>

              <button
                type="button"
                className="sp-visit-outcome-action"
                disabled={!visitActive}
                onClick={() => router.push(visitOutcomePath)}
              >
                <Icon name="Edit" size={20} color="var(--color-primary)" />
                <span>
                  <strong className="sp-body-strong">Log visit outcome</strong>
                  <span className="sp-meta">{hasOrderTaken ? "Order taken · mark completed" : "No order and follow-up reason"}</span>
                </span>
                <Icon name="KeyboardArrowRight" size={24} color="var(--color-text-placeholder)" />
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </SpScreen>
  );
}

const SLIDE_THUMB_SIZE = 48;
const SLIDE_TRACK_PADDING = 4;
const ORDER_COMPLETED_REASON_ID = "order_completed";

function getMaxSlideOffset(trackWidth: number, thumbSize: number, trackPadding: number) {
  return Math.max(trackWidth - thumbSize - (trackPadding * 2), 0);
}

function SlideToVisitAction({
  label,
  pendingLabel,
  pending,
  onComplete,
  compact = false,
  tone = "success",
  hapticOnComplete = false,
}: {
  label: string;
  pendingLabel: string;
  pending: boolean;
  onComplete: () => void | Promise<void>;
  compact?: boolean;
  tone?: "success" | "primary";
  hapticOnComplete?: boolean;
}) {
  const thumbSize = compact ? 40 : SLIDE_THUMB_SIZE;
  const trackPadding = compact ? 3 : SLIDE_TRACK_PADDING;
  const slideStyle = {
    "--sp-slide-padding": `${trackPadding}px`,
    "--sp-slide-thumb-center": `${thumbSize / 2}px`,
    "--sp-slide-thumb-size": `${thumbSize}px`,
  } as CSSProperties;
  const trackRef = useRef<HTMLButtonElement>(null);
  const startXRef = useRef(0);
  const maxOffsetRef = useRef(0);
  const dragOffsetRef = useRef(0);
  const completedRef = useRef(false);
  const completionTimerRef = useRef<number | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const [completing, setCompleting] = useState(false);

  const syncDragOffset = (nextOffset: number) => {
    if (animationFrameRef.current !== null) {
      window.cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    dragOffsetRef.current = nextOffset;
    trackRef.current?.style.setProperty("--sp-slide-thumb-x", `${nextOffset}px`);
  };

  const updateDragOffset = (nextOffset: number) => {
    dragOffsetRef.current = nextOffset;
    if (animationFrameRef.current !== null) return;
    animationFrameRef.current = window.requestAnimationFrame(() => {
      trackRef.current?.style.setProperty("--sp-slide-thumb-x", `${dragOffsetRef.current}px`);
      animationFrameRef.current = null;
    });
  };

  useEffect(() => {
    if (pending) return;
    const resetTimer = window.setTimeout(() => {
      completedRef.current = false;
      syncDragOffset(0);
      setDragging(false);
      setCompleting(false);
    }, 0);
    return () => window.clearTimeout(resetTimer);
  }, [pending]);

  useEffect(() => () => {
    if (completionTimerRef.current) window.clearTimeout(completionTimerRef.current);
    if (animationFrameRef.current !== null) window.cancelAnimationFrame(animationFrameRef.current);
  }, []);

  const completeAfterAnimation = () => {
    if (pending || completedRef.current) return;
    completedRef.current = true;
    setCompleting(true);
    syncDragOffset(maxOffsetRef.current);
    if (hapticOnComplete) {
      vibrate([40, 30, 80]);
    }
    completionTimerRef.current = window.setTimeout(() => {
      void onComplete();
    }, 260);
  };

  const beginSlide = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (pending || completing) return;
    if (event.pointerType === "mouse" && event.button !== 0) return;
    const bounds = trackRef.current?.getBoundingClientRect();
    if (!bounds) return;
    startXRef.current = event.clientX - dragOffsetRef.current;
    maxOffsetRef.current = getMaxSlideOffset(bounds.width, thumbSize, trackPadding);
    setDragging(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveSlide = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (!dragging || pending || completing) return;
    const bounds = trackRef.current?.getBoundingClientRect();
    if (bounds) maxOffsetRef.current = getMaxSlideOffset(bounds.width, thumbSize, trackPadding);
    const nextOffset = Math.min(Math.max(event.clientX - startXRef.current, 0), maxOffsetRef.current);
    updateDragOffset(nextOffset);
  };

  const finishSlide = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (!dragging) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDragging(false);
    if (maxOffsetRef.current > 0 && dragOffsetRef.current >= maxOffsetRef.current * 0.78) {
      completeAfterAnimation();
      return;
    }
    syncDragOffset(0);
  };

  const completeFromKeyboard = () => {
    if (maxOffsetRef.current <= 0) {
      const bounds = trackRef.current?.getBoundingClientRect();
      maxOffsetRef.current = bounds ? getMaxSlideOffset(bounds.width, thumbSize, trackPadding) : 0;
    }
    completeAfterAnimation();
  };

  return (
    <button
      ref={trackRef}
      type="button"
      className={`sp-slide-complete${tone === "primary" ? " sp-slide-complete--primary" : ""}${compact ? " sp-slide-complete--compact" : ""}${dragging ? " sp-slide-complete--dragging" : ""}${completing ? " sp-slide-complete--completing" : ""}`}
      disabled={pending || completing}
      aria-label={label}
      aria-busy={pending || completing}
      style={slideStyle}
      onPointerDown={beginSlide}
      onPointerMove={moveSlide}
      onPointerUp={finishSlide}
      onPointerCancel={finishSlide}
      onKeyDown={(event) => {
        if (event.repeat || (event.key !== " " && event.key !== "Enter")) return;
        event.preventDefault();
        completeFromKeyboard();
      }}
      onClick={(event) => event.preventDefault()}
    >
      <span className="sp-slide-complete__fill" />
      <span className="sp-slide-complete__label">{pending || completing ? pendingLabel : label}</span>
      <span className="sp-slide-complete__thumb">
        {pending ? <span className="sp-spinner" /> : completing ? <Icon name="Check" size={22} color="currentColor" /> : <Icon name="KeyboardArrowRight" size={24} color="currentColor" />}
      </span>
    </button>
  );
}

export function VisitOutcomeScreen({ stopId, forceOrderCompleted = false }: { stopId: string; forceOrderCompleted?: boolean }) {
  const router = useRouter();
  const route = useRouteDay(undefined, { refetchOnWindowFocus: false });
  const duty = useAttendanceToday({ refetchOnWindowFocus: false });
  return (
    <RouteActionGate
      title="Log visit outcome"
      back
      route={route}
      duty={duty}
      loadingContent={<SpPageSkeleton rows={2} />}
      lockMessage="Punch in to start your day."
    >
      {({ routeDay }) => {
        const apiStop = routePlanStops(routeDay).find((stop) => stop.visit_id === stopId || stop.outlet_ref === stopId);
        if (!apiStop) {
          return (
            <SpScreen title="Log visit outcome" back>
              <EmptyState
                icon="LocationPin"
                title="Visit unavailable"
                message="This stop is not part of the current route."
                actionLabel="Back to route"
                onAction={() => router.push("/sp/route")}
              />
            </SpScreen>
          );
        }
        return <VisitOutcomeContent stop={mapRouteStop(apiStop)} forceOrderCompleted={forceOrderCompleted} />;
      }}
    </RouteActionGate>
  );
}

function VisitOutcomeContent({ stop, forceOrderCompleted }: { stop: RouteStop; forceOrderCompleted: boolean }) {
  const router = useRouter();
  const { completeVisit } = useOrderDraft();
  const visits = useVisitMutations(stop.id);
  const noOrderReasons = useMemo(() => getVisitOutcomeReasons(), []);
  const hasOrderTaken = forceOrderCompleted || (stop.orderCount ?? 0) > 0;
  const reasons = useMemo(
    () => hasOrderTaken
      ? [{ id: ORDER_COMPLETED_REASON_ID, icon: "CheckCircle", label: "Order completed" }, ...noOrderReasons]
      : noOrderReasons,
    [hasOrderTaken, noOrderReasons],
  );
  const [reason, setReason] = useState(() => (
    hasOrderTaken ? ORDER_COMPLETED_REASON_ID : (noOrderReasons[0]?.id ?? "")
  ));
  const [note, setNote] = useState("");

  const saveOutcome = () => {
    if (reason === ORDER_COMPLETED_REASON_ID) {
      visits.checkOut.mutate(undefined, {
        onError: (error) => {
          if (error instanceof ApiClientError && error.code === "outcome_required") {
            setReason(noOrderReasons[0]?.id ?? "");
          }
        },
        onSuccess: () => {
          completeVisit();
          router.push("/sp/route");
        },
      });
      return;
    }
    visits.outcome.mutate(
      { reason: reason as OutcomeBody["reason"], note: note.trim() || null },
      {
        onSuccess: () => {
          completeVisit();
          router.push("/sp/route");
        },
      },
    );
  };

  const noteRequired = reason === "other";
  const saving = reason === ORDER_COMPLETED_REASON_ID ? visits.checkOut.isPending : visits.outcome.isPending;
  const submitLabel = reason === ORDER_COMPLETED_REASON_ID ? "Mark visited · order completed" : "Mark visited · no order";
  return (
    <SpScreen title="Log visit outcome" back>
      <div className="sp-content">
        <SpCard><h2 className="sp-title">{stop.outletName}</h2><p className="sp-meta">{hasOrderTaken ? "Order taken from outlet" : "No order this visit"}</p></SpCard>
        <div><SpSectionLabel>{hasOrderTaken ? "Select outcome" : "Select a reason"}</SpSectionLabel><div className="sp-grid">{reasons.map((item) => <SpActionTile key={item.id} icon={item.icon} title={item.label} active={reason === item.id} onClick={() => setReason(item.id)} />)}</div></div>
        <TextField label="Add detail" placeholder={noteRequired ? "Required for Other" : "Optional note"} multiline rows={3} value={note} onChange={(event) => setNote((event.target as HTMLInputElement).value)} required={noteRequired} />
      </div>
      <SpStickyFooter><Button variant="filled" color="primary" label={submitLabel} loading={saving} disabled={!reason || (noteRequired && !note.trim()) || saving} onClick={saveOutcome} style={{ width: "100%" }} /></SpStickyFooter>
    </SpScreen>
  );
}

function formatMissedVisitDate(iso: string) {
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(`${iso}T12:00:00+05:30`));
}

export function MissedVisitAuditScreen() {
  const today = istBusinessDate();
  const [date, setDate] = useState(today);
  const missed = useMissedVisits({ from: date, to: date });
  const stops = missed.data?.items ?? [];
  const adherence = missed.data?.summary.adherence_pct;
  return (
    <SpScreen title="Missed visits" back>
      <div className="sp-content">
        <DateField
          label="Date"
          value={formatMissedVisitDate(date)}
          dateValue={date}
          max={today}
          onChange={(value) => {
            if (/^\d{4}-\d{2}-\d{2}$/.test(value)) setDate(value);
          }}
        />
        {missed.isPending ? (
          <SpPageSkeleton rows={3} />
        ) : missed.isError ? (
          <ErrorState onRetry={() => void missed.refetch()} />
        ) : (
          <>
            <SpInlineAlert tone="warning">Planned visits not completed by the end of the day are recorded as missed. No action is required.</SpInlineAlert>
            <div className="sp-grid" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
              <SpCard><SpMetricStat value={(missed.data?.summary.missed ?? stops.length) + (missed.data?.summary.visited ?? 0)} label="Total visits" tone="var(--color-text-primary)" /></SpCard>
              <SpCard><SpMetricStat value={missed.data?.summary.missed ?? stops.length} label="Missed" tone="var(--color-error)" /></SpCard>
              <SpCard><SpMetricStat value={adherence === null || adherence === undefined ? "—" : `${Math.round(adherence)}%`} label="Adherence" tone="var(--color-success)" /></SpCard>
            </div>
          </>
        )}
      </div>
      {missed.isPending || missed.isError ? null : stops.length ? (
        <div className="sp-list">{stops.map((stop) => <ListRow key={stop.id} leading={<Icon name="Close" size={22} color="var(--color-error)" />} title={stop.outlet_name ?? "Outlet details unavailable"} subtitle={`${stop.outlet_locality ? `${stop.outlet_locality} · ` : ""}Planned ${new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeZone: "Asia/Kolkata" }).format(new Date(`${stop.business_date}T12:00:00+05:30`))}`} trailing={<StatusChip status="cancelled" label="Missed" type="outlined" />} />)}</div>
      ) : (
        <EmptyState icon="CheckCircle" title="No missed visits" message="No missed visits were recorded on this date." />
      )}
    </SpScreen>
  );
}
