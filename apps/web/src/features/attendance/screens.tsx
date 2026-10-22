"use client";

import {
  Button,
  EmptyState,
  ErrorState,
  Icon,
  ListRow,
  Select,
  Skeleton,
  StatusChip,
  TextField,
} from "humbee-design-system";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import { readSessionSync, subscribeToSession } from "@/src/shared/auth/session";
import {
  getCurrentDeviceLocation,
  getCurrentLocationLabel,
  openLocationPermissionSettings,
  type GeoCoordinates,
} from "@/src/shared/capabilities";
import { playFeedback, vibrate } from "@/src/shared/feedback";
import { SalespersonAttentionSection, SalespersonRequestsSection, SalespersonVisitsSection } from "@/src/features/kpi/home-dashboard";
import {
  SpCard,
  SpInlineAlert,
  SpMetricStat,
  SpScreen,
  SpSectionLabel,
  SpStickyFooter,
} from "@/src/features/shell/components";
import { ApiClientError } from "@/src/shared/api";
import { identityService } from "@/src/features/identity/service";
import { AttendanceMonthCard, SalespersonAttendanceSection } from "./month-card";
import { shiftMonthKey } from "./month-grid";
import {
  buildPunchBody,
  istBusinessDate,
  useAttendanceHistory,
  useAttendanceToday,
  useOfficialWorkCurrent,
  useOfficialWorkHistory,
  useOfficialWorkMutations,
  usePunch,
  useTodaySummary,
} from "./service";

const PunchLocationMap = dynamic(
  () => import("./location-map").then((module) => module.PunchLocationMap),
  { ssr: false, loading: () => <div className="sp-punch-map" aria-hidden /> },
);

function sectionData(section: { status?: string; data?: unknown }) {
  return section.status === "available" && section.data && typeof section.data === "object"
    ? section.data as Record<string, unknown>
    : null;
}

function sectionReason(section: { status?: string; reason?: unknown }) {
  return section.status === "unavailable" && typeof section.reason === "string"
    ? section.reason.replaceAll("_", " ")
    : "Unavailable";
}

function formatDutyClock(value?: string | null) {
  if (!value) return null;
  const instant = Date.parse(value);
  if (!Number.isFinite(instant)) return null;
  return new Intl.DateTimeFormat("en-IN", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  }).format(new Date(instant));
}

const FINGERPRINT_ICON_PATH = "M17.81 4.47c-.08 0-.16-.02-.23-.06C15.66 3.42 14 3 12.01 3c-1.98 0-3.86.47-5.57 1.41-.24.13-.54.04-.68-.2-.13-.24-.04-.55.2-.68C7.82 2.52 9.86 2 12.01 2c2.13 0 3.99.47 6.03 1.52.25.13.34.43.21.67-.09.18-.26.28-.44.28zM3.5 9.72c-.1 0-.2-.03-.29-.09-.23-.16-.28-.47-.12-.7.99-1.4 2.25-2.5 3.75-3.27C9.98 4.04 14 4.03 17.15 5.65c1.5.77 2.76 1.86 3.75 3.25.16.22.11.54-.12.7-.23.16-.54.11-.7-.12-.9-1.26-2.04-2.25-3.39-2.94-2.87-1.47-6.54-1.47-9.4.01-1.36.7-2.5 1.7-3.4 2.96-.08.14-.23.21-.39.21zm6.25 12.07c-.13 0-.26-.05-.35-.15-.87-.87-1.34-1.43-2.01-2.64-.69-1.23-1.05-2.73-1.05-4.34 0-2.97 2.54-5.39 5.66-5.39s5.66 2.42 5.66 5.39c0 .28-.22.5-.5.5s-.5-.22-.5-.5c0-2.42-2.09-4.39-4.66-4.39-2.57 0-4.66 1.97-4.66 4.39 0 1.44.32 2.77.93 3.85.64 1.15 1.08 1.64 1.85 2.42.19.2.19.51 0 .71-.11.1-.24.15-.37.15zm7.17-1.86c-1.19 0-2.24-.3-3.1-.89-1.49-1.01-2.38-2.65-2.38-4.39 0-.28.22-.5.5-.5s.5.22.5.5c0 1.41.72 2.74 1.94 3.56.71.48 1.54.71 2.54.71.24 0 .64-.03 1.04-.1.27-.05.53.13.58.41.05.27-.13.53-.41.58-.57.11-1.07.12-1.21.12zM14.91 22c-.04 0-.09-.01-.13-.02-1.59-.44-2.63-1.03-3.72-2.1-1.4-1.39-2.17-3.24-2.17-5.22 0-1.62 1.38-2.94 3.08-2.94 1.7 0 3.08 1.32 3.08 2.94 0 1.07.93 1.94 2.08 1.94s2.08-.87 2.08-1.94c0-3.77-3.25-6.83-7.25-6.83-2.84 0-5.44 1.58-6.61 4.03-.39.81-.59 1.76-.59 2.8 0 .78.07 2.01.67 3.61.1.26-.03.55-.29.64-.26.1-.55-.04-.64-.29-.49-1.31-.73-2.61-.73-3.96 0-1.2.23-2.29.68-3.24 1.33-2.79 4.28-4.6 7.51-4.6 4.55 0 8.25 3.51 8.25 7.83 0 1.62-1.38 2.94-3.08 2.94s-3.08-1.32-3.08-2.94c0-1.07-.93-1.94-2.08-1.94s-2.08.87-2.08 1.94c0 1.71.66 3.31 1.87 4.51.95.94 1.86 1.46 3.27 1.85.27.07.42.35.35.61-.05.23-.26.38-.47.38z";

const FINGERPRINT_LOAD_PARTS = [
  "M17.81 4.47c-.08 0-.16-.02-.23-.06C15.66 3.42 14 3 12.01 3c-1.98 0-3.86.47-5.57 1.41-.24.13-.54.04-.68-.2-.13-.24-.04-.55.2-.68C7.82 2.52 9.86 2 12.01 2c2.13 0 3.99.47 6.03 1.52.25.13.34.43.21.67-.09.18-.26.28-.44.28z",
  "M3.5 9.72c-.1 0-.2-.03-.29-.09-.23-.16-.28-.47-.12-.7.99-1.4 2.25-2.5 3.75-3.27C9.98 4.04 14 4.03 17.15 5.65c1.5.77 2.76 1.86 3.75 3.25.16.22.11.54-.12.7-.23.16-.54.11-.7-.12-.9-1.26-2.04-2.25-3.39-2.94-2.87-1.47-6.54-1.47-9.4.01-1.36.7-2.5 1.7-3.4 2.96-.08.14-.23.21-.39.21z",
  "M9.75 21.79c-.13 0-.26-.05-.35-.15-.87-.87-1.34-1.43-2.01-2.64-.69-1.23-1.05-2.73-1.05-4.34 0-2.97 2.54-5.39 5.66-5.39s5.66 2.42 5.66 5.39c0 .28-.22.5-.5.5s-.5-.22-.5-.5c0-2.42-2.09-4.39-4.66-4.39-2.57 0-4.66 1.97-4.66 4.39 0 1.44.32 2.77.93 3.85.64 1.15 1.08 1.64 1.85 2.42.19.2.19.51 0 .71-.11.1-.24.15-.37.15z",
  "M16.92 19.93c-1.19 0-2.24-.3-3.1-.89-1.49-1.01-2.38-2.65-2.38-4.39 0-.28.22-.5.5-.5s.5.22.5.5c0 1.41.72 2.74 1.94 3.56.71.48 1.54.71 2.54.71.24 0 .64-.03 1.04-.1.27-.05.53.13.58.41.05.27-.13.53-.41.58-.57.11-1.07.12-1.21.12z",
  "M14.91 22c-.04 0-.09-.01-.13-.02-1.59-.44-2.63-1.03-3.72-2.1-1.4-1.39-2.17-3.24-2.17-5.22 0-1.62 1.38-2.94 3.08-2.94 1.7 0 3.08 1.32 3.08 2.94 0 1.07.93 1.94 2.08 1.94s2.08-.87 2.08-1.94c0-3.77-3.25-6.83-7.25-6.83-2.84 0-5.44 1.58-6.61 4.03-.39.81-.59 1.76-.59 2.8 0 .78.07 2.01.67 3.61.1.26-.03.55-.29.64-.26.1-.55-.04-.64-.29-.49-1.31-.73-2.61-.73-3.96 0-1.2.23-2.29.68-3.24 1.33-2.79 4.28-4.6 7.51-4.6 4.55 0 8.25 3.51 8.25 7.83 0 1.62-1.38 2.94-3.08 2.94s-3.08-1.32-3.08-2.94c0-1.07-.93-1.94-2.08-1.94s-2.08.87-2.08 1.94c0 1.71.66 3.31 1.87 4.51.95.94 1.86 1.46 3.27 1.85.27.07.42.35.35.61-.05.23-.26.38-.47.38z",
];

function AnimatedFingerprintIcon() {
  return (
    <svg className="sp-fingerprint-loader" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path className="sp-fingerprint-loader__track" d={FINGERPRINT_ICON_PATH} />
      {FINGERPRINT_LOAD_PARTS.map((part, index) => (
        <path
          key={part}
          className={`sp-fingerprint-loader__print sp-fingerprint-loader__print--${index + 1}`}
          d={part}
        />
      ))}
    </svg>
  );
}

export function TodayScreen() {
  const router = useRouter();
  const today = useTodaySummary();
  const duty = useAttendanceToday();
  const sessionName = useSyncExternalStore(
    subscribeToSession,
    () => readSessionSync()?.displayName ?? "",
    () => "",
  );

  const summary = today.data;
  const identity = summary ? sectionData(summary.identity) : null;
  const notifications = summary ? sectionData(summary.notifications) : null;
  const onDuty = Boolean(duty.data?.on_duty);
  const punchedInAt = formatDutyClock(duty.data?.punched_in_at);

  if (today.isPending || duty.isPending) {
    return (
      <SpScreen title="Today" bell>
        <div className="sp-content">
          <Skeleton width="50%" height={22} />
          <Skeleton height={96} radius={12} />
          <Skeleton height={168} radius={12} />
          <Skeleton height={88} radius={12} />
        </div>
      </SpScreen>
    );
  }
  if (today.isError || duty.isError || !summary) {
    return <SpScreen title="Today" bell><ErrorState onRetry={() => { void today.refetch(); void duty.refetch(); }} /></SpScreen>;
  }

  const firstName = String(identity?.greeting_name ?? sessionName).split(" ")[0];

  return (
    <SpScreen title="Today" bell>
      <div className="sp-view-swap sp-today-home">
      <div className="sp-today-header">
        <div className="sp-today-header-copy">
          <h2 className="sp-title sp-title--h2">Hi, {firstName}</h2>
          <p className="sp-copy">{new Intl.DateTimeFormat("en-IN", { dateStyle: "full", timeZone: "Asia/Kolkata" }).format(new Date(`${summary.business_date}T12:00:00+05:30`))}</p>
        </div>
        <button
          className="sp-attendance-quick"
          data-state={onDuty ? "out" : "in"}
          onClick={() => router.push("/sp/more/attendance")}
          type="button"
          aria-label={onDuty ? "Punch out on attendance page" : "Punch in on attendance page"}
        >
          <span className="sp-attendance-quick-icon" aria-hidden="true">
            {onDuty ? (
              <>
                <Icon name="LogoutOutlined" size={18} color="currentColor" />
                <span className="sp-attendance-dot" />
              </>
            ) : (
              <AnimatedFingerprintIcon />
            )}
          </span>
          <span className="sp-attendance-quick-copy">
            <strong>{onDuty ? "Punch out" : "Punch in"}</strong>
            <span className="sp-meta">{onDuty ? (punchedInAt ? `On duty · ${punchedInAt}` : "On duty") : "Start duty"}</span>
          </span>
        </button>
      </div>
      <div className="sp-content">
        <SalespersonAttentionSection />
        <SalespersonVisitsSection />
        <SalespersonRequestsSection />
        {!notifications ? <SpInlineAlert>Notifications are {sectionReason(summary.notifications)}.</SpInlineAlert> : null}
      </div>
      </div>
    </SpScreen>
  );
}

export function PunchScreen() {
  const router = useRouter();
  const duty = useAttendanceToday();
  const punch = usePunch();
  const holdTimerRef = useRef<number | null>(null);
  const vibrationTimerRef = useRef<number | null>(null);
  const holdCompletedRef = useRef(false);
  const [state, setState] = useState<"locating" | "ready" | "error">("locating");
  const [location, setLocation] = useState<GeoCoordinates | null>(null);
  const [locationLabel, setLocationLabel] = useState("");
  const [retryBody, setRetryBody] = useState<ReturnType<typeof buildPunchBody> | null>(null);
  const [holdingPunch, setHoldingPunch] = useState(false);
  const [clock, setClock] = useState(() => Date.now());
  const punchedIn = duty.data?.on_duty ?? false;
  const dutyElapsed = duty.data?.punched_in_at ? formatDuration(elapsedSecondsSince(duty.data.punched_in_at, clock)) : "—";

  const clearPunchHold = useCallback((cancelVibration = true) => {
    if (holdTimerRef.current) {
      window.clearTimeout(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    if (vibrationTimerRef.current) {
      window.clearInterval(vibrationTimerRef.current);
      vibrationTimerRef.current = null;
    }
    if (cancelVibration) {
      vibrate(0);
    }
    setHoldingPunch(false);
  }, []);

  useEffect(() => {
    if (!punchedIn) return;
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [punchedIn]);

  useEffect(() => () => clearPunchHold(), [clearPunchHold]);

  const captureLocation = useCallback(async () => {
    setState("locating");
    setLocation(null);
    setLocationLabel("");
    try {
      const currentLocation = await getCurrentDeviceLocation();
      const currentLocationLabel = await getCurrentLocationLabel(currentLocation);
      setLocation(currentLocation);
      setLocationLabel(currentLocationLabel);
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);

  useEffect(() => {
    const captureTimer = window.setTimeout(() => void captureLocation(), 0);
    return () => window.clearTimeout(captureTimer);
  }, [captureLocation]);

  const confirmPunch = async ({ logoutAfter = false }: { logoutAfter?: boolean } = {}) => {
    if (!location) return;
    const direction = punchedIn ? "out" : "in";
    const body = retryBody ?? buildPunchBody(direction, location, locationLabel || null);
    setRetryBody(body);
    try {
      await punch.mutateAsync(body);
      setRetryBody(null);
      if (direction === "out") {
        playFeedback("punchOut");
        vibrate([50, 35, 70, 35, 50]);
      } else {
        playFeedback("punchIn");
        vibrate([45, 40, 90]);
      }
      if (logoutAfter) {
        await identityService.logout();
        router.replace("/auth");
        return;
      }
      router.push("/sp");
    } catch {
      clearPunchHold();
    }
  };

  const startPunchHold = (event?: PointerEvent<HTMLButtonElement> | KeyboardEvent<HTMLButtonElement>) => {
    if (state !== "ready" || punch.isPending || holdTimerRef.current) return;
    holdCompletedRef.current = false;
    setHoldingPunch(true);
    vibrate(35);
    vibrationTimerRef.current = window.setInterval(() => vibrate(15), 650);
    if (event && "pointerId" in event) {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    holdTimerRef.current = window.setTimeout(() => {
      holdCompletedRef.current = true;
      clearPunchHold(false);
      void confirmPunch({ logoutAfter: punchedIn });
    }, 2_000);
  };

  const cancelPunchHold = () => {
    if (holdCompletedRef.current) return;
    clearPunchHold();
  };

  const addressLabel = locationLabel || "Finding your current location";

  return (
    <SpScreen title="Attendance" back>
      <div className={`sp-punch-page${punchedIn ? " sp-punch-page--out" : ""}`}>
        <div>
          <div className="sp-punch-location-heading">
            <SpSectionLabel>Your location</SpSectionLabel>
            {punchedIn ? (
              <div className="sp-punch-elapsed" aria-label="Elapsed duty time" aria-live="polite">
                <Icon name="Schedule" size={20} color="var(--color-success)" />
                <span className="sp-punch-elapsed-label">
                  Elapsed time
                <strong>{dutyElapsed}</strong>
                </span>
              </div>
            ) : null}
          </div>
          <SpCard padded={false}>
            {location
              ? <PunchLocationMap lat={location.latitude} lng={location.longitude} captured label={addressLabel} />
              : (
                <div
                  className="sp-punch-map"
                  style={{ alignItems: "center", display: "flex", justifyContent: "center" }}
                  aria-hidden
                >
                  {state === "locating" ? <span className="sp-spinner" /> : null}
                </div>
              )}
          </SpCard>
        </div>
        <div key={state} className={`sp-punch-control sp-view-swap sp-punch-control--${state}${punchedIn ? " sp-punch-control--out" : ""}${holdingPunch ? " sp-punch-control--holding" : ""}`}>
          {state === "ready" ? (
            <>
              <span className="sp-punch-ripple sp-punch-ripple--one" />
              <span className="sp-punch-ripple sp-punch-ripple--two" />
              <span className="sp-punch-ripple sp-punch-ripple--three" />
            </>
          ) : null}
          <span className="sp-punch-ring" />
          {holdingPunch ? (
            <svg className="sp-punch-hold-progress-ring" viewBox="0 0 120 120" aria-hidden="true" focusable="false">
              <circle className="sp-punch-hold-progress-ring__track" cx="60" cy="60" r="54" pathLength={100} />
              <circle className="sp-punch-hold-progress-ring__value" cx="60" cy="60" r="54" pathLength={100} />
            </svg>
          ) : null}
          <button
            className={`sp-punch-button${holdingPunch ? " sp-punch-button--holding" : ""}`}
            type="button"
            disabled={state !== "ready" || punch.isPending}
            aria-label={punchedIn ? "Punch out" : "Punch in"}
            onPointerDown={startPunchHold}
            onPointerUp={cancelPunchHold}
            onPointerLeave={cancelPunchHold}
            onPointerCancel={cancelPunchHold}
            onKeyDown={(event) => {
              if (event.repeat || (event.key !== " " && event.key !== "Enter")) return;
              event.preventDefault();
              startPunchHold(event);
            }}
            onKeyUp={(event) => {
              if (event.key !== " " && event.key !== "Enter") return;
              event.preventDefault();
              cancelPunchHold();
            }}
            onClick={(event) => {
              event.preventDefault();
            }}
          >
            {state === "locating" ? <span className="sp-spinner" /> : <AnimatedFingerprintIcon />}
            <strong>{state === "locating" ? "Locating…" : state === "error" ? "GPS unavailable" : punch.isPending ? (punchedIn ? "Punching out…" : "Punching in…") : holdingPunch ? "Keep holding" : punchedIn ? "Punch out" : "Punch in"}</strong>
          </button>
        </div>
        <div className="sp-punch-hint">
          <p className="sp-meta" aria-live="polite">
            {state === "locating"
              ? "Fetching precise GPS location"
              : state === "error"
                ? "Location could not be captured"
                : punchedIn
                  ? "Hold until the circle completes to punch out and log out"
                  : "Hold until the circle completes to punch in with GPS"}
          </p>
          {punch.isError ? <SpInlineAlert tone="error">{punch.error instanceof ApiClientError ? punch.error.message : "Attendance could not be recorded. Retry with the captured location."}</SpInlineAlert> : null}
          {state === "error" ? (
            <button className="sp-text-link" type="button" onClick={() => void captureLocation()}>
              Retry location
            </button>
          ) : (
            <button className="sp-text-link" type="button" onClick={() => router.push("/sp/more/attendance/blocked?reason=permission")}>
              Can&apos;t get location?
            </button>
          )}
        </div>
      </div>
    </SpScreen>
  );
}

export function PunchBlockedScreen({ reason = "permission" }: { reason?: "permission" | "gpsoff" }) {
  const router = useRouter();
  const content = {
    permission: { icon: "Lock", title: "Location permission needed", message: "Enable location access in your settings to record attendance.", cta: "Open settings" },
    gpsoff: { icon: "LocationMarker", title: "Turn on GPS", message: "Turn on device location, then retry the GPS capture.", cta: "Retry" },
  }[reason];
  const handleBlockedAction = async () => {
    if (reason === "permission" && await openLocationPermissionSettings()) {
      return;
    }

    router.push("/sp/more/attendance");
  };

  return (
    <SpScreen title="Attendance" back>
      <div className="sp-punch-page">
        <div className="sp-view-swap" style={{ alignItems: "center", display: "flex", flex: 1, flexDirection: "column", justifyContent: "center", textAlign: "center" }}>
          <Icon name={content.icon} size={36} color="var(--color-error)" />
          <h2 className="sp-title sp-title--h2" style={{ marginTop: "var(--space-sm)" }}>{content.title}</h2>
          <p className="sp-copy" style={{ maxWidth: 280 }}>{content.message}</p>
        </div>
        <SpInlineAlert tone="warning">Route and orders remain locked until you punch in.</SpInlineAlert>
      </div>
      <SpStickyFooter>
        <Button variant="filled" color="primary" label={content.cta} leftIcon={<Icon name={reason === "permission" ? "SettingsOutlined" : "Autorenew"} size={20} color="currentColor" />} onClick={() => void handleBlockedAction()} style={{ width: "100%" }} />
      </SpStickyFooter>
    </SpScreen>
  );
}

export function AttendanceHistoryScreen() {
  const currentMonth = istBusinessDate().slice(0, 7);
  const [monthKey, setMonthKey] = useState(currentMonth);
  const [selectedDay, setSelectedDay] = useState(() => Number.parseInt(istBusinessDate().slice(-2), 10));
  const history = useAttendanceHistory(monthKey);
  const year = Number(monthKey.slice(0, 4));
  const month = Number(monthKey.slice(5, 7));
  const records = history.data?.days ?? [];
  const recordsByDay = new Map(records.map((record) => [Number.parseInt(record.business_date.slice(-2), 10), record]));
  const selectedRecord = recordsByDay.get(selectedDay);
  const monthLabel = new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(year, month - 1, 1)));
  const selectedDateLabel = new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "2-digit", month: "short", timeZone: "Asia/Kolkata" }).format(new Date(`${monthKey}-${String(selectedDay).padStart(2, "0")}T12:00:00+05:30`));
  const canGoNext = monthKey < currentMonth;
  const moveMonth = (offset: number) => {
    const next = shiftMonthKey(monthKey, offset);
    if (offset > 0 && next > currentMonth) return;
    setMonthKey(next);
    setSelectedDay(next === currentMonth ? Number.parseInt(istBusinessDate().slice(-2), 10) : 1);
  };
  return (
    <SpScreen title="Attendance" back>
      <div className="sp-content">
        <div className="sp-row">
          <button className="sp-icon-action" type="button" aria-label="Previous month" onClick={() => moveMonth(-1)} style={{ border: "solid var(--color-neutral-300)", borderRadius: "var(--radius-md)", borderWidth: "thin" }}><Icon name="KeyboardArrowLeft" size={22} color="var(--color-text-primary)" /></button>
          <strong>{monthLabel}</strong>
          <button className="sp-icon-action" type="button" aria-label="Next month" disabled={!canGoNext} onClick={() => moveMonth(1)} style={{ border: "solid var(--color-neutral-300)", borderRadius: "var(--radius-md)", borderWidth: "thin", opacity: canGoNext ? 1 : 0.4 }}><Icon name="KeyboardArrowRight" size={22} color="var(--color-text-primary)" /></button>
        </div>
        <SpSectionLabel>{monthKey === currentMonth ? "Month to date" : monthLabel}</SpSectionLabel>
        <AttendanceMonthCard
          days={records}
          isError={history.isError}
          isPending={history.isPending}
          monthKey={monthKey}
          selectedDay={selectedDay}
          onRetry={() => { void history.refetch(); }}
          onSelectDay={setSelectedDay}
        />
        <div>
          <SpSectionLabel>{selectedDateLabel}</SpSectionLabel>
          <SpCard padded={false}>
            {selectedRecord?.punched_in_at ? (
              <div className="sp-list">
                <ListRow leading={<Icon name="LocationMarker" size={18} color="var(--color-success)" />} title="Punched in" trailing={<strong>{new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }).format(new Date(selectedRecord.punched_in_at))}</strong>} />
                <ListRow leading={<Icon name="Schedule" size={18} color="var(--color-text-placeholder)" />} title={selectedRecord.punched_out_at ? "Punched out" : "On duty"} trailing={<strong style={{ color: selectedRecord.punched_out_at ? "var(--color-text-primary)" : "var(--color-primary)" }}>{selectedRecord.punched_out_at ? new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }).format(new Date(selectedRecord.punched_out_at)) : "Currently active"}</strong>} />
              </div>
            ) : <p className="sp-copy" style={{ padding: "var(--space-md)" }}>{selectedRecord ? `${selectedRecord.status} · no punch recorded.` : "No attendance recorded."}</p>}
          </SpCard>
        </div>
      </div>
    </SpScreen>
  );
}

export const officialWorkTypes = [
  { value: "meeting", label: "Internal meeting" },
  { value: "training", label: "Training" },
  { value: "collection", label: "Collection follow-up" },
  { value: "other", label: "Other office work" },
] as const;

export function formatDuration(seconds: number) {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remainder = safeSeconds % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function elapsedSecondsSince(startedAt: string, nowMs: number) {
  const startedAtMs = Date.parse(startedAt);
  if (!Number.isFinite(startedAtMs)) return 0;
  return Math.floor(((nowMs || startedAtMs) - startedAtMs) / 1000);
}

export function OfficialWorkScreen() {
  const router = useRouter();
  const current = useOfficialWorkCurrent();
  const mutations = useOfficialWorkMutations();
  const duty = useAttendanceToday();
  const [type, setType] = useState<(typeof officialWorkTypes)[number]["value"]>("meeting");
  const [purpose, setPurpose] = useState("");
  const [notes, setNotes] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const running = current.data?.status === "running" ? current.data : null;
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  if (current.isPending || duty.isPending) return <SpScreen title="Official work" back><div className="sp-content"><Skeleton height={240} radius={12} /></div></SpScreen>;
  if (current.isError || duty.isError) return <SpScreen title="Official work" back><ErrorState onRetry={() => { void current.refetch(); void duty.refetch(); }} /></SpScreen>;
  if (!duty.data?.on_duty) return <SpScreen title="Official work" back><EmptyState icon="Lock" title="Punch in first" message="Official work can start only while you are on duty." actionLabel="Go to attendance" onAction={() => router.push("/sp/more/attendance")} /></SpScreen>;
  const elapsed = running ? elapsedSecondsSince(running.started_at, now) : 0;
  return (
    <SpScreen title="Official work" back>
      <div className="sp-content">
        <SpCard>
          <div style={{ textAlign: "center" }}><p className="sp-section-label">{running ? "In progress" : "Not started"}</p><strong className="sp-metric-value sp-metric-value--display" style={{ color: running ? "var(--color-info)" : "var(--color-text-disabled)" }}>{formatDuration(elapsed)}</strong></div>
        </SpCard>
        <Select label="Work type" fullWidth value={running?.work_type ?? type} disabled={Boolean(running)} onChange={(value) => setType(value as typeof type)} options={officialWorkTypes.map((item) => ({ ...item }))} />
        <TextField label="Purpose" placeholder="Distributor settlement meeting" value={running?.purpose ?? purpose} disabled={Boolean(running)} onChange={(event) => setPurpose((event.target as HTMLInputElement).value)} />
        <TextField label="Notes" placeholder="Optional" multiline rows={3} value={running?.notes ?? notes} disabled={Boolean(running)} onChange={(event) => setNotes((event.target as HTMLInputElement).value)} />
        <Button variant="outlined" color="primary" label="View official work history" onClick={() => router.push("/sp/more/official-work/history")} style={{ backgroundColor: "var(--color-primary-surface)", width: "100%" }} />
        {mutations.start.isError || mutations.end.isError ? <SpInlineAlert tone="error">Official work could not be updated. Your input is preserved; retry the action.</SpInlineAlert> : null}
      </div>
      <SpStickyFooter><Button variant="filled" color={running ? "error" : "primary"} loading={mutations.start.isPending || mutations.end.isPending} disabled={mutations.start.isPending || mutations.end.isPending} label={running ? "End official work" : "Start official work"} onClick={() => running ? mutations.end.mutate(running.id) : mutations.start.mutate({ workType: type, purpose, notes })} style={{ width: "100%" }} /></SpStickyFooter>
    </SpScreen>
  );
}

export function OfficialWorkHistoryScreen() {
  const router = useRouter();
  const history = useOfficialWorkHistory();
  if (history.isPending) return <SpScreen title="Official work" back><div className="sp-content"><Skeleton height={240} radius={12} /></div></SpScreen>;
  if (history.isError) return <SpScreen title="Official work" back><ErrorState onRetry={() => void history.refetch()} /></SpScreen>;
  const records = history.data?.items ?? [];
  if (!records.length) return <SpScreen title="Official work" back><EmptyState icon="Schedule" title="No official work logged" message="Start official work to log meetings, training, or office follow-ups." actionLabel="Start official work" onAction={() => router.push("/sp/more/official-work")} /></SpScreen>;
  const weekTotal = formatDuration(history.data?.summary.total_seconds ?? 0);
  return (
    <SpScreen title="Official work" back>
      <div className="sp-grid" style={{ padding: "var(--space-md)" }}><SpCard><SpMetricStat value={weekTotal} label="This week" tone="var(--color-info)" /></SpCard><SpCard><SpMetricStat value={records.length} label="Tasks" tone="var(--color-primary)" /></SpCard></div>
      <div className="sp-list">{records.map((record) => <ListRow key={record.id} leading={<Icon name="Schedule" size={22} color="var(--color-info)" />} title={officialWorkTypes.find((item) => item.value === record.work_type)?.label ?? record.work_type} subtitle={new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }).format(new Date(record.started_at))} meta={formatDuration(record.duration_seconds ?? 0)} trailing={<StatusChip status="completed" label="Logged" type="outlined" />} />)}</div>
    </SpScreen>
  );
}
