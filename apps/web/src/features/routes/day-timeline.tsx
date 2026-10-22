"use client";

import { EmptyState, Skeleton } from "humbee-design-system";
import type { RoutePlanResponse } from "@humbee/api-contract";
import { useQueries } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useMemo } from "react";
import { formatDuration, officialWorkTypes } from "@/src/features/attendance/screens";
import {
  compareTeamDayActivities,
  CoverageActivityTimeline,
  CoverageActivityTimelineSkeleton,
  type TeamDayActivity,
} from "@/src/features/management/activity-timeline";
import type { LivePositionMarker } from "@/src/features/management/live-positions-map";
import { SpCard, SpSectionLabel } from "@/src/features/shell/components";
import { getCurrentLocationLabel } from "@/src/shared/capabilities";
import { mapRouteStop, routePlanStops, type RouteStop } from "./service";

const LivePositionsMap = dynamic(
  () => import("@/src/features/management/live-positions-map").then((module) => module.LivePositionsMap),
  { ssr: false, loading: () => <Skeleton height={220} radius={12} /> },
);

function formatDateTime(value: string | null | undefined) {
  if (!value) return undefined;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    month: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value));
}

function routeStopStatus(stop: RouteStop) {
  if (stop.status === "done") {
    if (stop.visitOutcome === "with_order" || (stop.orderCount ?? 0) > 0) return { label: "Order placed" };
    if (stop.visitOutcome === "no_order") return { label: "No order" };
    return { label: "Completed" };
  }
  if (stop.status === "next") return { label: "In progress" };
  if (stop.status === "missed") return { label: "Missed" };
  return { label: "Scheduled" };
}

function stopTimelineSubtitle(stop: RouteStop, areaLabel?: string) {
  const visitStarted = stop.status === "next" || stop.status === "done" || Boolean(stop.checkedInAt) || Boolean(stop.checkedOutAt);
  const resolvedArea = (areaLabel ?? stop.area).trim();
  const hideArea = !visitStarted && resolvedArea.toLowerCase() === "location unavailable";
  return [stop.visitType, stop.outletLevel, hideArea ? undefined : resolvedArea].filter(Boolean).join(" · ");
}

function stopMapMarkers(stops: RouteStop[]): LivePositionMarker[] {
  return stops.flatMap((stop) => {
    if (!stop.checkinGps) return [];
    const status = routeStopStatus(stop);
    return [{
      id: stop.id,
      name: stop.outletName,
      initials: String(stop.sequence),
      territory: stop.area,
      punchIn: "—",
      duty: "on" as const,
      lat: stop.checkinGps.lat,
      lng: stop.checkinGps.lng,
      pin: stop.status === "next" ? "current" as const : "stop" as const,
      caption: `${status.label} · ${stop.area}`,
    }];
  });
}

export interface RouteDayTimelineProps {
  routeDay: RoutePlanResponse;
  locationQueryScope: string;
  mapLabelWithMarkers: string;
  mapLabelWithoutMarkers: string;
  punchInSubtitle: string;
  punchOutSubtitle: string;
  emptyTimelineMessage?: string;
}

export function RouteDayTimeline({
  routeDay,
  locationQueryScope,
  mapLabelWithMarkers,
  mapLabelWithoutMarkers,
  punchInSubtitle,
  punchOutSubtitle,
  emptyTimelineMessage = "No activity on this day",
}: RouteDayTimelineProps) {
  const stops = useMemo(() => routePlanStops(routeDay).map(mapRouteStop), [routeDay]);
  const stopsNeedingResolvedLocation = useMemo(
    () => stops.flatMap((stop) => {
      if (!stop.checkinGps || stop.area.trim()) return [];
      return [{
        stopId: stop.id,
        latitude: stop.checkinGps.lat,
        longitude: stop.checkinGps.lng,
      }];
    }),
    [stops],
  );
  const resolvedLocationQueries = useQueries({
    queries: stopsNeedingResolvedLocation.map((item) => ({
      queryKey: ["location-label", locationQueryScope, item.stopId, item.latitude, item.longitude],
      queryFn: () => getCurrentLocationLabel({
        latitude: item.latitude,
        longitude: item.longitude,
        accuracyMeters: 0,
        capturedAt: 0,
      }),
      staleTime: 600_000,
      refetchOnWindowFocus: false,
      retry: 1,
    })),
  });
  const resolvedLocationByStopId = useMemo(() => {
    const labels = new Map<string, string>();
    stopsNeedingResolvedLocation.forEach((item, index) => {
      const value = resolvedLocationQueries[index]?.data;
      if (value) labels.set(item.stopId, value);
    });
    return labels;
  }, [resolvedLocationQueries, stopsNeedingResolvedLocation]);
  const timelineActivities = useMemo<TeamDayActivity[]>(() => {
    const activities: TeamDayActivity[] = [];
    if (routeDay.punched_in_at) {
      activities.push({
        id: "punch-in",
        occurredAt: routeDay.punched_in_at,
        sequence: -1,
        title: "Punch-in",
        subtitle: punchInSubtitle,
        chipLabel: "On duty",
        details: [],
      });
    }
    stops.forEach((stop) => {
      const status = routeStopStatus(stop);
      const locationLabel = stop.area.trim()
        ? stop.area
        : (resolvedLocationByStopId.get(stop.id) ?? (stop.checkinGps ? "Resolving location..." : "Location unavailable"));
      activities.push({
        id: `${stop.id}:activity`,
        occurredAt: stop.checkedInAt ?? stop.checkedOutAt ?? null,
        sequence: stop.sequence,
        title: stop.outletName,
        subtitle: stopTimelineSubtitle(stop, locationLabel),
        chipLabel: status.label,
        details: [
          ...(stop.checkedInAt ? [`Check-in ${formatDateTime(stop.checkedInAt)}`] : []),
          ...(stop.checkedOutAt ? [`Check-out ${formatDateTime(stop.checkedOutAt)}`] : []),
        ],
      });
    });
    (routeDay.official_work ?? []).forEach((block) => {
      activities.push({
        id: block.id,
        occurredAt: block.started_at,
        sequence: 0,
        title: officialWorkTypes.find((item) => item.value === block.work_type)?.label ?? block.work_type,
        subtitle: block.ended_at ? `Official work · ${formatDateTime(block.started_at)} - ${formatDateTime(block.ended_at)}` : `Official work · ${formatDateTime(block.started_at)}`,
        chipLabel: "Official work",
        details: block.duration_seconds !== null ? [`Duration ${formatDuration(block.duration_seconds)}`] : [],
      });
    });
    if (routeDay.punched_out_at) {
      activities.push({
        id: "punch-out",
        occurredAt: routeDay.punched_out_at,
        sequence: Number.MAX_SAFE_INTEGER,
        title: "Punch-out",
        subtitle: punchOutSubtitle,
        chipLabel: "Off duty",
        details: [],
      });
    }
    return activities.sort(compareTeamDayActivities);
  }, [punchInSubtitle, punchOutSubtitle, resolvedLocationByStopId, routeDay, stops]);
  const mapMarkers = useMemo(() => stopMapMarkers(stops), [stops]);
  const mapPath = useMemo<Array<[number, number]>>(
    () => mapMarkers.map((marker) => [marker.lng, marker.lat]),
    [mapMarkers],
  );

  const timeline = (
    <div>
      <SpSectionLabel>Activity timeline</SpSectionLabel>
      <SpCard>
        {timelineActivities.length ? (
          <CoverageActivityTimeline activities={timelineActivities} />
        ) : (
          <EmptyState icon="Schedule" title={emptyTimelineMessage} message="Punch and visit activities appear here in timestamp order." />
        )}
      </SpCard>
    </div>
  );
  const map = (
    <div>
      <SpSectionLabel>Route map</SpSectionLabel>
      <LivePositionsMap
        label={mapMarkers.length ? mapLabelWithMarkers : mapLabelWithoutMarkers}
        markers={mapMarkers}
        path={mapPath}
      />
    </div>
  );

  return <>{map}{timeline}</>;
}

export function RouteDayTimelineLoading() {
  const map = <Skeleton height={220} radius={12} />;
  const timeline = (
    <div>
      <SpSectionLabel>Activity timeline</SpSectionLabel>
      <SpCard>
        <CoverageActivityTimelineSkeleton rows={5} />
      </SpCard>
    </div>
  );
  return <>{map}{timeline}</>;
}
