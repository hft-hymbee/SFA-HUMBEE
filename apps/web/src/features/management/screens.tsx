"use client";

import {
  ApprovalTimeline,
  BottomSheet,
  Button,
  Checkbox,
  DateField,
  EmptyState,
  ErrorState,
  GeoScopePicker,
  Icon,
  IconButton,
  ListRow,
  Radio,
  RadioGroup,
  Select,
  Skeleton,
  StatusChip,
  Tabs,
  TextField,
  ToggleSwitch,
  type GeoScopeSelection,
} from "humbee-design-system";
import { useQuery } from "@tanstack/react-query";
import type {
  DetailBlock,
  ApprovalListItem,
  BeatDetailResponse,
  CombinedVisitResponse,
  CoverageResponse,
  CoverageRow,
  BeatListItem,
  EmployeeResponse,
  GeoScopeResponse,
  MoveCandidateListResponse,
  OrderDetailOut,
  OrderSummaryOut,
  ShopCategory,
  TeamAttendanceResponse,
  TeamAttendanceRow,
  TreeNodeResponse,
} from "@humbee/api-contract";
import {
  coverageTeamApiV1CoverageTeamGet,
  getTeamApiV1AttendanceTeamGet,
} from "@humbee/api-contract";
import { useSearchParams } from "next/navigation";
import { Fragment, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type { CSSProperties, ReactNode } from "react";
import { LogoutConfirmSheet } from "@/src/features/identity/screens";
import {
  flattenApprovals,
  useApprovalDecision,
  useApprovalDetail,
  useApprovalEditableFields,
  useApprovalInbox,
  useApprovalSummary,
  useApprovalTimeline,
} from "@/src/features/approvals/hooks";
import type { ApprovalFilter, ApprovalInboxStatus } from "@/src/features/approvals/service";
import { NotificationsFeed } from "@/src/features/approvals/screens";
import { isBeatPlannedOnDate, mapBeat, mapOutlet, useBeat, useBeatDetail, useBeats, useBeatMutations, useScopeOutlets } from "@/src/features/beats/service";
import type { OutletChoice } from "@/src/features/beats/service";
import {
  dayLabel as leaveDayLabel,
  leaveRoutingSuffix,
  leaveStatusLabel,
  leaveTypeLabel,
} from "@/src/features/leave/format";
import { useTeamLeave } from "@/src/features/leave/hooks";
import {
  ApplyLeaveScreen,
  LeaveDetailScreen,
  LeaveStatusScreen,
  type LeaveJourneyPaths,
  type LeaveShellProps,
} from "@/src/features/leave/screens";
import { newMutationKey, useOrder, useOrders, useRetryOrder } from "@/src/features/orders/hooks";
import {
  OrderSummarySections,
  mapDpOrderSummaryLine,
  mapOrderDetailSummaryLine,
} from "@/src/features/orders/order-summary-ui";
import { TargetEditScreen, TargetsScreen } from "@/src/features/targets/screens";
import {
  AccountActionList,
  ProfileIdentity,
  UserProfilePanel,
  UserProfilePanelSkeleton,
  type AccountAction,
} from "@/src/features/profile/components";
import { getProfile } from "@/src/features/profile/service";
import {
  getServerSession,
  readSessionSync,
  subscribeToSession,
} from "@/src/shared/auth/session";
import { downloadAdminReport } from "./download-report";
import type { GeographyMasterResponse } from "./organization-service";
import {
  useManagementPath,
  useManagementRole,
  useManagementRouter as useRouter,
} from "./role-context";
import type {
  ApprovalRequest,
  DayScope,
  EmployeeFilter,
  ManagementView,
  StatusTone,
} from "./service";
import {
  employeesHref,
  isEmployeeFilter,
} from "./service";
import { mutationErrorMessage, useDebouncedSearchQuery, useInfiniteScrollTrigger } from "@/src/shared/state";
import { ApiClientError, createIdempotencyKey, getBrowserApiClient } from "@/src/shared/api";
import { shopCategoryLabel } from "@/src/shared/geography-master";
import { filterOutletsByQuery, sortOutletsTakenLast } from "@/src/shared/outlet-list";
import { SpProcessProgress, StatusHistory } from "@/src/features/shell/components";
import type { StatusHistoryStep } from "@/src/features/shell/components";
import { SpInlineSkeleton } from "@/src/features/shell/loading";
import {
  useCombinedVisit,
  useCombinedVisitMutations,
  useCombinedVisits,
  useRouteDay,
  useTeamCoverage,
} from "@/src/features/routes/service";
import { RouteDayTimeline, RouteDayTimelineLoading } from "@/src/features/routes/day-timeline";
import { useCallsKpis } from "@/src/features/kpi/hooks";
import type { CallsKpiRowOut, CallsKpiScope, CallsKpiTotalsOut } from "@/src/features/kpi/service";
import {
  AdminKpiHomeDashboardScreen,
  ManagerKpiHomeDashboardScreen,
  ManagerTeamPerformanceScreen,
} from "@/src/features/kpi/home-dashboard";
import { DataRow, ManagementScreen, Notice, Section, SummaryGrid, viewTitles } from "./ui";
import {
  useEmployee,
  useEmployees,
  useGeographyMaster,
  useGeographyScope,
  useMoveCandidates,
  useOrganizationMutations,
  useOrganizationTree,
} from "./organization-hooks";
import { fetchAllPages } from "@/src/shared/pagination";
import styles from "./management.module.css";

const UNTITLED_BEAT = "Untitled beat";

function isEmptyBeatDraft(beat: BeatListItem) {
  return beat.lifecycle_state === "draft"
    && beat.display_name === UNTITLED_BEAT
    && beat.outlet_count === 0;
}

function visibleAdminBeatRows(items: BeatListItem[]) {
  const seen = new Set<string>();
  return items.filter((beat) => {
    if (isEmptyBeatDraft(beat) || seen.has(beat.id)) return false;
    seen.add(beat.id);
    return true;
  });
}

type BeatRunSection = "assigned_beat" | "unplanned_beat" | "draft_beat";

function beatRunSectionOrder(section: BeatRunSection) {
  if (section === "assigned_beat") return 0;
  if (section === "unplanned_beat") return 1;
  return 2;
}

function beatRunSectionLabel(section: BeatRunSection) {
  if (section === "assigned_beat") return "Assigned beats";
  if (section === "unplanned_beat") return "Unplanned beats";
  return "Draft beats";
}

function beatRunSectionForListItem(item: Pick<BeatListItem, "lifecycle_state" | "run_origin">): BeatRunSection {
  if (item.lifecycle_state === "draft") return "draft_beat";
  return item.run_origin === "assigned_beat" ? "assigned_beat" : "unplanned_beat";
}

type ManagementBeatFrequency = "daily" | "weekly" | "fortnightly" | "monthly";

function asShopCategories(values: string[]): ShopCategory[] {
  return values as ShopCategory[];
}

const beatFrequencyOptions: Array<{ value: ManagementBeatFrequency; label: string }> = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "fortnightly", label: "Fortnightly" },
  { value: "monthly", label: "Monthly" },
];

function isManagementBeatFrequency(value: unknown): value is ManagementBeatFrequency {
  return value === "daily" || value === "weekly" || value === "fortnightly" || value === "monthly";
}

function beatFrequencyFromApi(value: BeatListItem["frequency"]): ManagementBeatFrequency {
  return isManagementBeatFrequency(value.frequency) ? value.frequency : "daily";
}

function beatNumberArray(value: BeatListItem["frequency"], key: string) {
  const candidate = value[key];
  return Array.isArray(candidate) ? candidate.filter((item): item is number => typeof item === "number") : [];
}

function beatStringArray(value: BeatDetailResponse["geo_scope"], key: string) {
  const candidate = value[key];
  return Array.isArray(candidate) ? candidate.filter((item): item is string => typeof item === "string") : [];
}

function hasBeatFrequencyDetails(frequency: ManagementBeatFrequency, days: number[], weeks: number[]) {
  return frequency === "daily" || (days.length > 0 && (frequency === "weekly" || weeks.length > 0));
}

function beatScopeOptions(master: GeographyMasterResponse, assignedScope: GeoScopeResponse, savedScopes: BeatDetailResponse["geo_scope"][]) {
  const withSaved = (assigned: string[], key: string) => [...new Set([...assigned, ...savedScopes.flatMap((geoScope) => beatStringArray(geoScope, key))])];
  const pool = { zones: withSaved(assignedScope.zones, "zones"), states: withSaved(assignedScope.states, "states"), districts: withSaved(assignedScope.districts, "districts"), categories: [] as ShopCategory[] };
  return {
    pool,
    zones: master.zones.filter((zone) => pool.zones.includes(zone.id)).map((zone) => ({ id: zone.id, label: zone.name })),
    states: master.states.filter((state) => pool.states.includes(state.id)).map((state) => ({ id: state.id, label: state.name, zoneId: state.zone_id })),
    districts: master.districts.filter((district) => pool.districts.includes(district.id)).map((district) => ({ id: district.id, label: district.name, stateId: district.state_id })),
    categories: master.cats.map((category) => ({ id: category.id, label: category.name })),
  };
}

function ManagementBeatFrequencyFields({
  frequency,
  days,
  weeks,
  onFrequencyChange,
  onDaysChange,
  onWeeksChange,
}: {
  frequency: ManagementBeatFrequency;
  days: number[];
  weeks: number[];
  onFrequencyChange: (frequency: ManagementBeatFrequency) => void;
  onDaysChange: (days: number[]) => void;
  onWeeksChange: (weeks: number[]) => void;
}) {
  const dayLabels = ["S", "M", "T", "W", "T", "F", "S"];
  return (
    <Section label="Visit frequency">
      <div className={styles.form}>
        <Select
          label="Frequency"
          fullWidth
          value={frequency}
          onChange={(value) => onFrequencyChange(isManagementBeatFrequency(value) ? value : "daily")}
          options={beatFrequencyOptions}
        />
        {frequency !== "daily" ? (
          <div className="sp-day-grid">
            {dayLabels.map((day, index) => (
              <button
                aria-label={`Visit ${days.includes(index) ? "selected" : "not selected"} for day ${index + 1}`}
                className="sp-day-button"
                data-active={days.includes(index)}
                key={`${day}-${index}`}
                onClick={() => onDaysChange(days.includes(index) ? days.filter((value) => value !== index) : [...days, index])}
                type="button"
              >
                {day}
              </button>
            ))}
          </div>
        ) : null}
        {frequency === "fortnightly" || frequency === "monthly" ? (
          <div className="sp-week-grid">
            {[1, 2, 3, 4].map((week) => (
              <button
                className="sp-week-button"
                data-active={weeks.includes(week)}
                key={week}
                onClick={() => onWeeksChange(weeks.includes(week) ? weeks.filter((value) => value !== week) : [...weeks, week])}
                type="button"
              >
                W{week}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </Section>
  );
}

function istDateISO(date = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(date);
}

function useManagementActorId() {
  return useSyncExternalStore(subscribeToSession, readSessionSync, getServerSession)?.employeeId ?? "";
}

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function useTeamAttendanceList(businessDate: string) {
  const actorId = useManagementActorId();
  return useQuery({
    queryKey: ["attendance", { actorId, businessDate }, "team-list"],
    queryFn: ({ signal }): Promise<TeamAttendanceResponse> => fetchAllPages(async (page) => unwrap(await getTeamApiV1AttendanceTeamGet({
      client: getBrowserApiClient(),
      query: { business_date: businessDate, page, page_size: 100 },
      signal,
      throwOnError: true,
    }))),
    enabled: Boolean(actorId),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}

function shiftIsoDate(iso: string, days: number) {
  const date = new Date(`${iso}T12:00:00+05:30`);
  date.setDate(date.getDate() + days);
  return istDateISO(date);
}

function defaultApprovalHistoryRange() {
  const to = istDateISO();
  return { from: shiftIsoDate(to, -6), to };
}

function formatBusinessDate(iso: string) {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(new Date(`${iso}T12:00:00+05:30`));
}

function formatBusinessDateShort(iso: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(`${iso}T12:00:00+05:30`));
}

function isIsoBusinessDate(value: string | null): value is string {
  return Boolean(value && /^\d{4}-\d{2}-\d{2}$/.test(value));
}

function formatRupees(value: number) {
  return `₹ ${value.toLocaleString("en-IN")}`;
}

function parseOrderValue(value: string) {
  const match = value.replace(/,/g, "").match(/([\d.]+)\s*([KL])?/i);
  if (!match) return 0;
  const amount = Number(match[1]);
  const unit = match[2]?.toUpperCase();
  if (unit === "L") return amount * 100000;
  if (unit === "K") return amount * 1000;
  return amount;
}

function formatCompactRupees(value: number) {
  if (!value) return "—";
  if (value >= 100000) return `₹ ${(value / 100000).toFixed(1).replace(/\.0$/, "")}L`;
  if (value >= 1000) return `₹ ${(value / 1000).toFixed(1).replace(/\.0$/, "")}K`;
  return formatRupees(Math.round(value));
}

function moneyFromPaise(paise: number | null | undefined) {
  return formatRupees(Math.round((paise ?? 0) / 100));
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function employeeSubtitle(employee: EmployeeResponse) {
  return [
    employeeRoleLabel(employee.role_code),
    employee.login_enabled ? "Active" : "Inactive",
  ].filter(Boolean).join(" · ");
}

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value.includes("T") ? value : `${value}T12:00:00+05:30`));
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return undefined;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value));
}

function statusTone(status: string): StatusTone {
  const normalized = status.toLowerCase();
  if (["approved", "registered", "completed", "active", "auto_approved"].includes(normalized)) return "verified";
  if (["rejected", "failed", "inactive", "cancelled", "withdrawn"].includes(normalized)) return "cancelled";
  if (["approved_with_edits"].includes(normalized)) return "partially-completed";
  if (["submission_failed", "terminal_failure"].includes(normalized)) return "not-verified";
  if (["pending", "pending_approval", "queued", "running", "draft"].includes(normalized)) return "pending";
  return "default";
}

function timelineState(state: string): StatusHistoryStep["state"] {
  if (state === "done" || state === "edited" || state === "rejected" || state === "current") return state;
  return "pending";
}

const timelineActionLabels: Record<string, string> = {
  submitted: "Submitted",
  routed: "Routed",
  escalated: "Escalated",
  edited: "Edited",
  approved: "Approved",
  rejected: "Rejected",
  auto_approved: "Auto-approved",
  withdrawn: "Withdrawn",
  awaiting_decision: "Awaiting decision",
};

function humanLabel(value: string) {
  const label = value.replace(/_/g, " ").trim().toLowerCase();
  return label ? `${label.charAt(0).toUpperCase()}${label.slice(1)}` : "—";
}

function outletCountLabel(count: number) {
  return `${count} outlet${count === 1 ? "" : "s"}`;
}

function beatDisplayTitle(beat: Pick<BeatListItem, "display_name">) {
  return beat.display_name.trim() || "Coverage plan";
}

function beatDisplaySubtitle(beat: Pick<BeatListItem, "outlet_count" | "frequency">) {
  return `${outletCountLabel(beat.outlet_count)} · ${humanLabel(String(beat.frequency.frequency ?? "daily"))}`;
}

function beatFrequencyDisplay(frequency: BeatDetailResponse["frequency"]) {
  const cadence = beatFrequencyFromApi(frequency);
  const days = beatNumberArray(frequency, "visit_days");
  const weeks = beatNumberArray(frequency, "week_cycle");
  const dayLabels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  if (cadence === "daily") return "Daily";
  const selectedDays = days.map((day) => dayLabels[day]).filter(Boolean).join(", ");
  const selectedWeeks = weeks.map((week) => `W${week}`).join(", ");
  return [humanLabel(cadence), selectedDays, selectedWeeks].filter(Boolean).join(" · ");
}

function beatGeoLabelItems(scope: BeatDetailResponse["geo_scope"], key: string) {
  const labels = scope.labels;
  if (!labels || typeof labels !== "object" || Array.isArray(labels)) return [];
  const candidates = (labels as Record<string, unknown>)[key];
  if (!Array.isArray(candidates)) return [];
  return candidates.flatMap((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return [];
    const label = item as Record<string, unknown>;
    return typeof label.id === "string" && typeof label.name === "string"
      ? [{ id: label.id, name: label.name }]
      : [];
  });
}

function beatGeoLabels(scope: BeatDetailResponse["geo_scope"], key: string, ids: string[]) {
  if (!ids.length) return "—";
  const lookup = new Map(beatGeoLabelItems(scope, key).map((item) => [item.id, item.name]));
  const labels = ids.map((id) => lookup.get(id)).filter((label): label is string => Boolean(label));
  return labels.length ? labels.join(", ") : "Label unavailable";
}

function categoryLabels(ids: string[]) {
  return ids.length ? ids.map((id) => shopCategoryLabel(id as ShopCategory)).join(", ") : "All categories";
}

function beatApprovalTitle(title: string) {
  const normalized = title.trim().replace(/^(Beat|Edit):\s*/i, "").trim();
  return normalized || "Coverage plan request";
}

function approvalDisplayTitle(request: ApprovalListItem) {
  if (!request.subject_type.startsWith("beat")) return request.title;
  return beatApprovalTitle(request.title);
}

function approvalDisplaySubtitle(request: ApprovalListItem) {
  if (!request.subject_type.startsWith("beat")) return request.subtitle;
  const outletCount = request.subtitle.match(/\b\d+\s+outlets?\b/i)?.[0];
  return outletCount ? humanLabel(outletCount) : request.subtitle;
}

const approvedApprovalStatuses = new Set(["approved", "approved_with_edits", "auto_approved"]);

function matchesApprovalInboxStatus(request: ApprovalListItem, status: ApprovalInboxStatus) {
  if (status === "pending") return request.status === "pending";
  return approvedApprovalStatuses.has(request.status);
}

function matchesApprovalFilter(request: ApprovalListItem, filter: ApprovalFilter) {
  if (filter === "all") return true;
  if (filter === "order") return request.subject_type === "dp_order";
  if (filter === "beat") return request.subject_type === "beat_create" || request.subject_type === "beat_edit";
  if (filter === "leave") return request.subject_type === "leave";
  return request.subject_type === "outlet_verification";
}

function approvalSubjectLabel(subjectType: string) {
  if (subjectType === "dp_order") return "Order";
  return humanLabel(subjectType);
}

function timelineActionLabel(action: string) {
  return timelineActionLabels[action] ?? humanLabel(action);
}

function timelineDetail(note: string | null | undefined) {
  return note?.trim() || undefined;
}

function payloadEntries(payload: Record<string, unknown>) {
  return Object.entries(payload).filter(([, value]) => value !== null && value !== undefined);
}

function payloadLabel(key: string) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function payloadText(value: unknown, key?: string): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) {
    const items: string[] = value.map((item) => payloadText(item)).filter((item) => item !== "—");
    return items.length ? items.join(", ") : "—";
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number" && key && /paise|total/i.test(key)) return moneyFromPaise(value);
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function diffText(item: Record<string, unknown>) {
  if (!("from_display" in item) && !("to_display" in item)) return null;
  const fromValue = payloadText(item.from_display);
  const toValue = payloadText(item.to_display);
  const added = Array.isArray(item.added) ? item.added.length : 0;
  const removed = Array.isArray(item.removed) ? item.removed.length : 0;
  const movement = fromValue === toValue ? toValue : `${fromValue} -> ${toValue}`;
  const countDelta = added || removed ? `+${added} / -${removed}` : null;
  return [movement, countDelta].filter(Boolean).join(" · ");
}

function renderDetailRow(label: string, value: unknown, key: string, className?: string) {
  return (
    <div className={className ? `${styles.detailRow} ${className}` : styles.detailRow} key={key}>
      <span>{label}</span>
      <strong>{payloadText(value, label)}</strong>
    </div>
  );
}

function blockByLabel(blocks: DetailBlock[], label: string) {
  return blocks.find((block) => block.label.toLowerCase() === label.toLowerCase());
}

interface DpOrderLineView {
  key: string;
  productName: string;
  qty: number;
  unitLabel: string | null;
  unitPriceNetPaise: number | null;
  lineNetPaise: number;
  lineGstAmountPaise: number;
  lineTotalPaise: number;
}

interface DpOrderRequestDetails {
  outlet: string | null;
  manufacturer: string | null;
  sourcePo: string | null;
  subtotalNetPaise: number;
  productDiscountPaise: number;
  schemeDiscountPaise: number;
  schemeLabel: string | null;
  gstAmountPaise: number;
  grossTotalPaise: number;
  pricedLines: DpOrderLineView[];
  quantityOnlyLines: DpOrderLineView[];
}

function normalizePayloadKey(key: string) {
  return key.replace(/[\s_]+/g, "").trim().toLowerCase();
}

function payloadValueByAliases(payload: Record<string, unknown>, aliases: string[]) {
  for (const alias of aliases) {
    if (alias in payload) return payload[alias];
  }
  const normalized = new Map(
    Object.entries(payload).map(([key, value]) => [normalizePayloadKey(key), value]),
  );
  for (const alias of aliases) {
    const candidate = normalized.get(normalizePayloadKey(alias));
    if (candidate !== undefined) return candidate;
  }
  return undefined;
}

function numericPayloadValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function textPayloadValue(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  if (!normalized || normalized === "—") return null;
  return normalized;
}

function extractBlockLines(block: DetailBlock | undefined) {
  if (!block) return [] as unknown[];
  if (Array.isArray(block.payload.lines)) return block.payload.lines;
  if (Array.isArray(block.payload.diff)) return block.payload.diff;
  return [] as unknown[];
}

function toOrderLineView(line: unknown, index: number, keyPrefix: string): DpOrderLineView | null {
  if (!line || typeof line !== "object" || Array.isArray(line)) return null;
  const payload = line as Record<string, unknown>;
  const qty = Math.max(
    0,
    Math.round(
      numericPayloadValue(payloadValueByAliases(payload, ["qty", "approved_qty", "requested_qty"])) ?? 0,
    ),
  );
  const lineNetPaise = Math.max(0, Math.round(
    numericPayloadValue(payloadValueByAliases(payload, ["line_net_paise", "line_net"])) ?? 0,
  ));
  const lineGstAmountPaise = Math.max(0, Math.round(
    numericPayloadValue(payloadValueByAliases(payload, ["line_gst_amount_paise", "line_gst"])) ?? 0,
  ));
  const lineTotalPaise = Math.max(0, Math.round(
    numericPayloadValue(payloadValueByAliases(payload, ["line_total_paise", "gross_total_paise", "line_total"]))
    ?? (lineNetPaise + lineGstAmountPaise),
  ));
  const unitPriceNetPaise = numericPayloadValue(
    payloadValueByAliases(payload, ["unit_price_net_paise", "unit_price_paise"]),
  );
  const unitLabel = textPayloadValue(
    payloadValueByAliases(payload, ["unit_label", "pack_size", "uom", "uom_snapshot"]),
  );
  const productName = textPayloadValue(payloadValueByAliases(payload, ["product_name", "name", "label"]))
    ?? `Line ${index + 1}`;
  return {
    key: `${keyPrefix}-${index}-${productName}`,
    productName,
    qty,
    unitLabel,
    unitPriceNetPaise,
    lineNetPaise,
    lineGstAmountPaise,
    lineTotalPaise,
  };
}

function parseDpOrderRequestDetails(blocks: DetailBlock[]): DpOrderRequestDetails | null {
  const orderBlock = blockByLabel(blocks, "Order");
  if (!orderBlock) return null;
  const orderPayload = orderBlock.payload;
  const subtotalNetPaise = Math.max(0, Math.round(
    numericPayloadValue(payloadValueByAliases(orderPayload, ["subtotal_net_paise", "subtotal", "subtotal_paise"])) ?? 0,
  ));
  const rawSchemeDiscount = Math.max(0, Math.round(
    numericPayloadValue(payloadValueByAliases(orderPayload, ["scheme_discount_paise", "scheme_discount"])) ?? 0,
  ));
  const schemeDiscountPaise = Math.min(rawSchemeDiscount, subtotalNetPaise);
  const productDiscountPaise = Math.max(0, Math.round(
    numericPayloadValue(payloadValueByAliases(orderPayload, ["product_discount_paise", "product_discount"])) ?? 0,
  ));
  const schemeLabel = textPayloadValue(
    payloadValueByAliases(orderPayload, ["scheme_label", "Scheme label"]),
  );
  const grossTotalPaise = Math.max(0, Math.round(
    numericPayloadValue(payloadValueByAliases(orderPayload, ["gross_total_paise", "total"])) ?? 0,
  ));
  const taxableBasePaise = subtotalNetPaise - schemeDiscountPaise;
  const gstAmountPaise = Math.max(
    0,
    Math.round(
      numericPayloadValue(payloadValueByAliases(orderPayload, ["gst_amount_paise", "gst"]))
      ?? (grossTotalPaise - taxableBasePaise),
    ),
  );

  const pricedItemsBlock = blockByLabel(blocks, "Priced items");
  const quantityOnlyItemsBlock = blockByLabel(blocks, "Quantity-only items");
  const pricedLines = extractBlockLines(pricedItemsBlock)
    .map((line, index) => toOrderLineView(line, index, "priced"))
    .filter((line): line is DpOrderLineView => Boolean(line));
  const quantityOnlyLines = extractBlockLines(quantityOnlyItemsBlock)
    .map((line, index) => toOrderLineView(line, index, "quantity-only"))
    .filter((line): line is DpOrderLineView => Boolean(line));

  if (!pricedLines.length && !quantityOnlyLines.length) {
    const legacyLines = extractBlockLines(blockByLabel(blocks, "Line items"))
      .map((line, index) => toOrderLineView(line, index, "legacy"))
      .filter((line): line is DpOrderLineView => Boolean(line));
    for (const line of legacyLines) {
      if (line.unitPriceNetPaise == null) quantityOnlyLines.push(line);
      else pricedLines.push(line);
    }
  }

  return {
    outlet: textPayloadValue(payloadValueByAliases(orderPayload, ["Outlet", "outlet"])),
    manufacturer: textPayloadValue(payloadValueByAliases(orderPayload, ["Manufacturer", "manufacturer"])),
    sourcePo: textPayloadValue(payloadValueByAliases(orderPayload, ["Source PO", "source_po"])),
    subtotalNetPaise,
    productDiscountPaise,
    schemeDiscountPaise,
    schemeLabel,
    gstAmountPaise,
    grossTotalPaise,
    pricedLines,
    quantityOnlyLines,
  };
}

function meaningfulPayloadText(value: unknown, key?: string) {
  const text = payloadText(value, key);
  return text === "—" ? null : text;
}

function blockPayloadValue(block: DetailBlock | undefined, key: string) {
  return block?.payload[key];
}

function outletDocumentRow(firm: DetailBlock | undefined): [string, string] {
  const gstin = meaningfulPayloadText(blockPayloadValue(firm, "GSTIN"), "GSTIN");
  if (gstin) return ["GSTIN", gstin];
  return ["PAN", meaningfulPayloadText(blockPayloadValue(firm, "PAN"), "PAN") ?? "—"];
}

function outletAddressText(block: DetailBlock | undefined, includeLocation: boolean) {
  const lineValues = ["Line 1", "Line 2", "Line 3"]
    .map((key) => meaningfulPayloadText(blockPayloadValue(block, key), key))
    .filter(Boolean);
  const state = meaningfulPayloadText(blockPayloadValue(block, "State"), "State");
  const district = meaningfulPayloadText(blockPayloadValue(block, "District"), "District");
  const location = includeLocation ? meaningfulPayloadText(blockPayloadValue(block, "Locality"), "Locality") : null;
  const pincode = includeLocation ? meaningfulPayloadText(blockPayloadValue(block, "Pincode"), "Pincode") : null;
  return [
    ...lineValues,
    state ? `State ${state}` : null,
    district ? `District ${district}` : null,
    location ? `Location ${location}` : null,
    pincode,
  ].filter(Boolean).join(", ") || "—";
}

function outletRoleText(line: unknown) {
  if (!line || typeof line !== "object" || Array.isArray(line)) return payloadText(line);
  const item = line as Record<string, unknown>;
  const manufacturer = meaningfulPayloadText(item.manufacturer ?? item.manufacturer_name, "manufacturer");
  const role = meaningfulPayloadText(item.label ?? item.role ?? item.role_name, "role");
  return [manufacturer, role].filter(Boolean).join(" · ") || payloadText(item);
}

function renderOutletRoleRows(roles: DetailBlock) {
  const lines = Array.isArray(roles.payload.lines) ? roles.payload.lines : [];
  if (!lines.length) return renderDetailRow("Roles", "No roles requested", "outlet-role-empty", styles.approvalDetailRow);
  return lines.map((line, index) => renderDetailRow(
    `Role ${index + 1}`,
    outletRoleText(line),
    `outlet-role-${index}`,
    styles.approvalDetailRow,
  ));
}

function outletIndustryText(line: unknown) {
  if (!line || typeof line !== "object" || Array.isArray(line)) return payloadText(line);
  const item = line as Record<string, unknown>;
  const primary = meaningfulPayloadText(item.primary ?? item.primary_industry_name, "primary");
  const secondary = meaningfulPayloadText(item.secondary ?? item.secondary_industry, "secondary");
  const role = meaningfulPayloadText(item.role ?? item.role_name ?? item.label, "role");
  return [[primary, secondary].filter(Boolean).join(" > "), role].filter(Boolean).join(" - ") || payloadText(item);
}

function renderOutletIndustryRows(industries: DetailBlock) {
  const lines = Array.isArray(industries.payload.lines) ? industries.payload.lines : [];
  if (!lines.length) return renderDetailRow("Industries", "No industries requested", "outlet-industry-empty", styles.approvalDetailRow);
  return lines.map((line, index) => renderDetailRow(
    `Industry ${index + 1}`,
    outletIndustryText(line),
    `outlet-industry-${index}`,
    styles.approvalDetailRow,
  ));
}

function outletApprovalSummary(blocks: DetailBlock[], request: ApprovalListItem) {
  const firm = blockByLabel(blocks, "Firm");
  const operational = blockByLabel(blocks, "Operational address");
  const roles = blockByLabel(blocks, "Roles requested");
  const industries = blockByLabel(blocks, "Industries requested");
  const title = meaningfulPayloadText(blockPayloadValue(firm, "Name"), "Name")
    ?? request.title.replace(/^Onboard:\s*/i, "").trim()
    ?? approvalDisplayTitle(request);
  const [, documentValue] = outletDocumentRow(firm);
  const roleCount = Array.isArray(roles?.payload.lines) ? roles.payload.lines.length : 0;
  const industryCount = Array.isArray(industries?.payload.lines) ? industries.payload.lines.length : 0;
  const pincode = meaningfulPayloadText(blockPayloadValue(operational, "Pincode"), "Pincode");
  const subtitle = [
    documentValue !== "—" ? documentValue : null,
    roleCount + industryCount > 0 ? `${roleCount + industryCount} association${roleCount + industryCount === 1 ? "" : "s"}` : null,
    pincode,
  ].filter(Boolean).join(" · ");
  return { title, subtitle };
}

function renderOutletApprovalDetails(blocks: DetailBlock[], candidateId: string) {
  const firm = blockByLabel(blocks, "Firm");
  const registered = blockByLabel(blocks, "Registered address");
  const operational = blockByLabel(blocks, "Operational address");
  const roles = blockByLabel(blocks, "Roles requested");
  const industries = blockByLabel(blocks, "Industries requested");
  if (!firm && !registered && !operational) return null;

  const [documentLabel, documentValue] = outletDocumentRow(firm);
  const documentRow = documentValue === "—"
    ? renderDetailRow("Document", "No document submitted", "outlet-document", styles.approvalDetailRow)
    : renderDetailRow(documentLabel, documentValue, "outlet-document", styles.approvalDetailRow);
  return (
    <>
      <Section label="Owner and document">
        <div className={styles.card} style={{ padding: 0 }}>
          {renderDetailRow("Owner phone", payloadText(blockPayloadValue(firm, "Owner phone"), "Owner phone"), "outlet-owner-phone", styles.approvalDetailRow)}
          {documentRow}
          {renderDetailRow("Candidate ID", candidateId, "outlet-candidate-id", styles.approvalDetailRow)}
        </div>
      </Section>

      <Section label="Address details">
        <div className={styles.card} style={{ padding: 0 }}>
          {renderDetailRow("Registered", outletAddressText(registered, false), "outlet-registered-address", styles.approvalDetailRow)}
          {renderDetailRow("Operational", outletAddressText(operational, true), "outlet-operational-address", styles.approvalDetailRow)}
        </div>
      </Section>

      {roles ? (
        <Section label="Manufacturer roles">
          <div className={styles.card} style={{ padding: 0 }}>
            {renderOutletRoleRows(roles)}
          </div>
        </Section>
      ) : null}

      {industries ? (
        <Section label="Industries">
          <div className={styles.card} style={{ padding: 0 }}>
            {renderOutletIndustryRows(industries)}
          </div>
        </Section>
      ) : null}
    </>
  );
}

function renderDetailBlock(block: DetailBlock, rowClassName?: string) {
  if (block.kind === "date_range") {
    const fromDate = payloadText(block.payload.from_date);
    const toDate = payloadText(block.payload.to_date);
    const dayCount = payloadText(block.payload.day_count);
    const halfDay = block.payload.is_half_day === true ? " · Half day" : "";
    return renderDetailRow(
      block.label,
      `${formatDate(fromDate)} to ${formatDate(toDate)} · ${dayCount} ${Number(block.payload.day_count) === 1 ? "day" : "days"}${halfDay}`,
      `${block.kind}-${block.label}`,
      rowClassName,
    );
  }

  if (block.kind === "key_values") {
    const entries = payloadEntries(block.payload);
    return entries.length
      ? entries.map(([key, value]) => renderDetailRow(payloadLabel(key), value, `${block.kind}-${block.label}-${key}`, rowClassName))
      : renderDetailRow(block.label, "No additional fields", `${block.kind}-${block.label}`, rowClassName);
  }

  if (block.kind === "line_items") {
    const lines = Array.isArray(block.payload.lines) ? block.payload.lines : Array.isArray(block.payload.diff) ? block.payload.diff : null;
    if (!lines) return renderDetailRow(block.label, block.payload, `${block.kind}-${block.label}`, rowClassName);
    if (!lines.length) return renderDetailRow(block.label, "No items", `${block.kind}-${block.label}`, rowClassName);
    return lines.map((line, index) => {
      if (!line || typeof line !== "object" || Array.isArray(line)) return renderDetailRow(`${block.label} ${index + 1}`, line, `${block.kind}-${block.label}-${index}`, rowClassName);
      const item = line as Record<string, unknown>;
      const title = payloadText(item.label ?? item.product_name ?? item.name ?? item.field ?? `${block.label} ${index + 1}`);
      const diff = diffText(item);
      const value = diff ?? payloadEntries(item)
        .filter(([key]) => !["label", "product_name", "field", "name"].includes(key))
        .map(([key, itemValue]) => `${payloadLabel(key)}: ${payloadText(itemValue, key)}`)
        .join(" · ");
      return renderDetailRow(title, value || "—", `${block.kind}-${block.label}-${index}`, rowClassName);
    });
  }

  const entries = payloadEntries(block.payload);
  return renderDetailRow(
    block.label,
    entries.length ? entries.map(([key, value]) => `${payloadLabel(key)}: ${payloadText(value, key)}`).join(" · ") : "No additional fields",
    `${block.kind}-${block.label}`,
    rowClassName,
  );
}

function BeatRequestFrequency({ beatId }: { beatId: string }) {
  const loaded = useBeatDetail(beatId, { pendingEdit: true });
  const detail = loaded.draft ?? loaded.detail;
  if (!detail) return null;
  return beatFrequencyDisplay(detail.frequency);
}

function scopeOutletsComplete(query: { isSuccess: boolean; isFetching: boolean; hasNextPage: boolean }) {
  return query.isSuccess && !query.isFetching && !query.hasNextPage;
}

function selectableOutletIds(outletIds: string[], scopeOutlets: OutletChoice[]) {
  const selectable = new Set(scopeOutlets.filter((outlet) => !outlet.takenBy).map((outlet) => outlet.id));
  return outletIds.filter((id) => selectable.has(id));
}

function droppedOutletsNotice(count: number) {
  return `${outletCountLabel(count)} ${count === 1 ? "is" : "are"} outside the selected scope or already on another beat and will be removed when you save.`;
}

function BeatApprovalSubjectDetails({ beatId, canEditOutlets, onOutletSavePendingChange }: { beatId: string; canEditOutlets?: boolean; onOutletSavePendingChange?: (pending: boolean) => void }) {
  const loaded = useBeatDetail(beatId, { pendingEdit: true });
  const scopeOutlets = useScopeOutlets(beatId, "", Boolean(canEditOutlets));
  const mutations = useBeatMutations();
  const [outletIds, setOutletIds] = useState<string[]>([]);
  const [outletQuery, setOutletQuery] = useState("");
  const [showAvailableOutlets, setShowAvailableOutlets] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const outletSavePending = mutations.replaceOutlets.isPending;
  const detail = loaded.draft ?? loaded.detail;

  useEffect(() => {
    onOutletSavePendingChange?.(outletSavePending);
    return () => onOutletSavePendingChange?.(false);
  }, [onOutletSavePendingChange, outletSavePending]);

  useEffect(() => {
    if (!detail) return;
    queueMicrotask(() => {
      setOutletIds(detail.outlets.map((outlet) => outlet.outlet_ref));
      setOutletQuery("");
      setShowAvailableOutlets(false);
      setSaveError(null);
    });
  }, [detail]);

  const currentOutlets = (detail?.outlets ?? []).map((outlet) => ({
    id: outlet.outlet_ref,
    name: outlet.name,
    location: outlet.locality?.trim() || "",
    category: outlet.category ? shopCategoryLabel(outlet.category) : "",
  }));
  const scopeChoices = scopeOutlets.data?.map(mapOutlet) ?? [];
  const scopeComplete = Boolean(canEditOutlets) && scopeOutletsComplete(scopeOutlets);
  const availableOutlets: Array<Pick<OutletChoice, "id" | "name" | "location" | "category" | "takenBy">> = scopeOutlets.data ? scopeChoices : currentOutlets;
  const sortedOutlets = useMemo(() => sortOutletsTakenLast(availableOutlets, "location_then_name"), [availableOutlets]);
  const filteredOutlets = useMemo(() => filterOutletsByQuery(sortedOutlets, outletQuery), [outletQuery, sortedOutlets]);

  if (loaded.isPending) {
    return (
      <Section label="Beat details">
        <Skeleton height={280} radius={12} />
      </Section>
    );
  }

  if (loaded.isError || !detail) {
    return (
      <Section label="Beat details">
        <ErrorState title="Beat details unavailable" message="The submitted beat could not be loaded from the approval subject." onRetry={() => { void loaded.refetch(); }} />
      </Section>
    );
  }

  const zones = beatStringArray(detail.geo_scope, "zones");
  const states = beatStringArray(detail.geo_scope, "states");
  const districts = beatStringArray(detail.geo_scope, "districts");
  const categories = beatStringArray(detail.geo_scope, "cats");
  const savableOutletIds = scopeComplete ? selectableOutletIds(outletIds, scopeChoices) : outletIds;
  const droppedOutletCount = outletIds.length - savableOutletIds.length;
  const visibleOutlets = showAvailableOutlets
    ? filteredOutlets
    : filteredOutlets.filter((outlet) => savableOutletIds.includes(outlet.id));
  const saveOutlets = async () => {
    if (outletSavePending || !scopeComplete) return;
    setSaveError(null);
    try {
      await mutations.replaceOutlets.mutateAsync({ beatId, outletRefs: savableOutletIds });
      await loaded.refetch();
    } catch (error) {
      setSaveError(mutationErrorMessage(error));
    }
  };
  const toggleOutlet = (outlet: Pick<OutletChoice, "id" | "takenBy">) => {
    if (outlet.takenBy) return;
    setOutletIds((current) => current.includes(outlet.id) ? current.filter((id) => id !== outlet.id) : [...current, outlet.id]);
  };

  return (
    <>
      <Section label="Geography scope">
        <div className={styles.card} style={{ padding: 0 }}>
          <EmployeeDetailRow expandable label="Zones" value={beatGeoLabels(detail.geo_scope, "zones", zones)} />
          <EmployeeDetailRow expandable label="States" value={beatGeoLabels(detail.geo_scope, "states", states)} />
          <EmployeeDetailRow expandable label="Districts" value={beatGeoLabels(detail.geo_scope, "districts", districts)} />
          <EmployeeDetailRow expandable label="Shop categories" value={categoryLabels(categories)} />
        </div>
      </Section>
      <Section label={`Outlets in this beat · ${detail.outlets.length}`}>
        <div className={styles.outletEditorStack}>
          <div className="sp-search-toolbar">
            <TextField
              placeholder="Search outlets"
              startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
              value={outletQuery}
              onChange={(event) => setOutletQuery((event.target as HTMLInputElement).value)}
            />
          </div>
          {canEditOutlets ? (
            <>
              <Button
                variant="outlined"
                color="primary"
                size="small"
                label={showAvailableOutlets ? "Show selected outlets only" : "Add outlets from scope"}
                leftIcon={<Icon name={showAvailableOutlets ? "Check" : "Add"} size={18} color="currentColor" />}
                disabled={outletSavePending}
                onClick={() => setShowAvailableOutlets((current) => !current)}
                style={{ width: "100%" }}
              />
              <Notice>Clear an outlet checkbox to remove it. Show available outlets to add more outlets from the beat scope.</Notice>
              {droppedOutletCount > 0 ? <Notice tone="warning">{droppedOutletsNotice(droppedOutletCount)}</Notice> : null}
              {saveError ? <Notice tone="warning">{saveError}</Notice> : null}
            </>
          ) : null}
          {showAvailableOutlets && (scopeOutlets.isFetching || scopeOutlets.hasNextPage) && !(scopeOutlets.data?.length) ? (
            <Skeleton height={160} radius={12} />
          ) : visibleOutlets.length ? (
            <div className={styles.card} style={{ padding: 0 }}>
              {visibleOutlets.map((outlet) => (
                <ListRow
                  key={outlet.id}
                  leading={canEditOutlets
                    ? <Checkbox checked={savableOutletIds.includes(outlet.id)} disabled={Boolean(outlet.takenBy)} onChange={(event) => { event.stopPropagation(); toggleOutlet(outlet); }} />
                    : <Icon name="LocationMarker" size={22} color="var(--color-primary)" />}
                  title={outlet.name}
                  subtitle={outlet.takenBy ? `Already on beat ${outlet.takenBy}` : outlet.location || undefined}
                  meta={outlet.category || undefined}
                  disabled={Boolean(canEditOutlets && outlet.takenBy)}
                  onClick={canEditOutlets && !outlet.takenBy ? () => toggleOutlet(outlet) : undefined}
                />
              ))}
            </div>
          ) : outletQuery.trim() && sortedOutlets.length ? (
            <EmptyState icon="SearchOutlined" title={`No outlets match "${outletQuery}"`} message="Try another outlet name." actionLabel="Clear search" onAction={() => setOutletQuery("")} />
          ) : (
            <EmptyState icon="LocationMarker" title="No outlets" message="No outlets are linked to this beat." />
          )}
          {canEditOutlets ? (
            <Button
              variant="filled"
              color="primary"
              size="small"
              label="Save outlet changes"
              loading={outletSavePending}
              disabled={!scopeComplete || !savableOutletIds.length || outletSavePending}
              onClick={() => { void saveOutlets(); }}
              style={{ width: "100%" }}
            />
          ) : null}
        </div>
      </Section>
    </>
  );
}

function approvalHref(kind: ApprovalRequest["kind"], id: string) {
  if (kind === "order") return "/mgmt/approval-detail";
  return `/mgmt/approval-detail?kind=${kind}&id=${id}`;
}

function orderChip(status: string): { status: StatusTone; label: string } {
  if (status === "edited") return { status: "partially-completed", label: "Edited" };
  if (status === "failed") return { status: "not-verified", label: "Dispatch failed" };
  if (status === "pending") return { status: "pending", label: "Pending" };
  return { status: "approved", label: "Approved" };
}

function dayDataScope(tab: DayScope, pickedDate: string): DayScope | null {
  if (tab !== "pick") return tab;
  if (!pickedDate) return null;
  const today = istDateISO();
  if (pickedDate === today) return "today";
  if (pickedDate === shiftIsoDate(today, -1)) return "yesterday";
  return "pick";
}

function ManagerDashboard() {
  return <ManagerKpiHomeDashboardScreen />;
}

function AdminDashboard() {
  return <AdminKpiHomeDashboardScreen />;
}

function DashboardDrill() {
  const router = useRouter();
  const orders = useOrders();
  const rows = orders.data?.pages.flatMap((page) => page.items) ?? [];
  const totalValue = rows.reduce((sum, row: OrderSummaryOut) => sum + row.gross_total_paise, 0);
  const listRef = useInfiniteScrollTrigger<HTMLDivElement>({
    hasNextPage: orders.hasNextPage,
    isFetchingNextPage: orders.isFetchingNextPage,
    fetchNextPage: orders.fetchNextPage,
  });
  return (
    <ManagementScreen view="dashboard-drill">
      <div className={styles.content}>
        {orders.isPending ? (
          <>
            <Skeleton height={92} radius={12} />
            <Skeleton height={72} radius={12} />
          </>
        ) : orders.isError ? (
          <ErrorState title="Orders unavailable" message="Scoped order history could not be loaded." onRetry={() => { void orders.refetch(); }} />
        ) : (
          <>
            <SummaryGrid items={[[String(rows.length), "Visible orders", "var(--color-primary)"], [moneyFromPaise(totalValue), "Visible value", "var(--color-success)"]]} />
            <Section label="Recent orders">
              <div className={styles.card} style={{ padding: 0 }} ref={listRef}>
                {rows.length ? rows.map((row: OrderSummaryOut) => (
                  <DataRow key={row.id} title={row.order_number} subtitle={`${row.outlet_name} · ${row.counterparty_name} · ${formatDate(row.business_date)}`} trailing={<StatusChip status={statusTone(row.status)} label={humanLabel(row.status)} type="outlined" />} onClick={() => router.push(`/mgmt/order?id=${encodeURIComponent(row.id)}`)} />
                )) : <EmptyState icon="ShoppingCartOutlined" title="No orders" message="Scoped SFA orders will appear here after submission." />}
              </div>
            </Section>
          </>
        )}
      </div>
    </ManagementScreen>
  );
}

function ApprovalInbox({ approvals: _approvals }: { approvals?: ApprovalRequest[] }) {
  const router = useRouter();
  const [filter, setFilter] = useState<ApprovalFilter>("all");
  const [statusFilter, setStatusFilter] = useState<ApprovalInboxStatus>("pending");
  const [range, setRange] = useState(defaultApprovalHistoryRange);
  const approvals = useApprovalInbox({
    subjectType: filter,
    status: statusFilter,
    from: range.from,
    to: range.to,
  });
  const rows = flattenApprovals(approvals.data)
    .filter((approval) => matchesApprovalInboxStatus(approval, statusFilter))
    .filter((approval) => matchesApprovalFilter(approval, filter));
  const listRef = useInfiniteScrollTrigger<HTMLDivElement>({
    hasNextPage: approvals.hasNextPage,
    isFetchingNextPage: approvals.isFetchingNextPage,
    fetchNextPage: approvals.fetchNextPage,
  });
  const filters: Array<[ApprovalFilter, string]> = [["all", "All"], ["order", "Orders"], ["beat", "Beats"], ["leave", "Leave"], ["outlet", "Outlets"]];
  const statusFilters: Array<[ApprovalInboxStatus, string]> = [["pending", "Pending"], ["approved", "Approved"]];
  const handleFromChange = (value: string) => {
    setRange((current) => ({ from: value, to: value > current.to ? value : current.to }));
  };
  const handleToChange = (value: string) => {
    setRange((current) => ({ from: value < current.from ? value : current.from, to: value }));
  };
  return (
    <ManagementScreen view="approvals">
      <div className={styles.statusTabs}>
        {statusFilters.map(([value, label]) => (
          <button data-active={statusFilter === value} key={value} onClick={() => setStatusFilter(value)} type="button">{label}</button>
        ))}
      </div>
      {statusFilter === "approved" ? (
        <div className={styles.pickDate}>
          <div className={styles.optionGrid}>
            <DateField label="From" value={formatBusinessDate(range.from)} dateValue={range.from} onChange={handleFromChange} max={range.to} />
            <DateField label="To" value={formatBusinessDate(range.to)} dateValue={range.to} onChange={handleToChange} min={range.from} />
          </div>
        </div>
      ) : null}
      <div className={styles.filterBar}>
        {filters.map(([value, label]) => (
          <button data-active={filter === value} key={value} onClick={() => setFilter(value)} type="button">{label}</button>
        ))}
      </div>
      {approvals.isPending ? (
        <div className={styles.content}>
          <Skeleton height={72} radius={12} />
          <Skeleton height={72} radius={12} />
          <Skeleton height={72} radius={12} />
        </div>
      ) : approvals.isError ? (
        <div className={styles.content}>
          <ErrorState title="Approvals unavailable" message={`${statusFilter === "approved" ? "Approved history" : "Pending approvals"} could not be loaded.`} onRetry={() => { void approvals.refetch(); }} />
        </div>
      ) : rows.length ? (
        <div className={styles.listBody} ref={listRef}>
          {rows.map((approval) => (
            <ListRow
              key={approval.id}
              leading={<span className={styles.leadingIcon}><Icon name="CheckCircle" size={20} color="var(--color-primary)" /></span>}
              title={approvalDisplayTitle(approval)}
              subtitle={approvalDisplaySubtitle(approval)}
              meta={formatDateTime(statusFilter === "approved" ? approval.decided_at ?? approval.submitted_at : approval.submitted_at)}
              trailing={<StatusChip status={statusTone(approval.status)} label={humanLabel(approval.status)} type="outlined" />}
              showChevron
              onClick={() => router.push(`/mgmt/approval-detail?id=${encodeURIComponent(approval.id)}`)}
            />
          ))}
        </div>
      ) : (
        <div className={styles.content}>
          <EmptyState
            icon="CheckCircle"
            title={statusFilter === "approved" ? "No approved history" : "All caught up"}
            message={statusFilter === "approved" ? "No approved requests match this date range." : filter === "all" ? "No pending approvals right now. New requests will appear here." : "No requests match this filter."}
            actionLabel={filter === "all" ? undefined : "Show all"}
            onAction={filter === "all" ? undefined : () => setFilter("all")}
          />
        </div>
      )}
    </ManagementScreen>
  );
}

function ApprovalDetail() {
  const searchParams = useSearchParams();
  const approvalId = searchParams.get("id") ?? "";
  const router = useRouter();
  const detail = useApprovalDetail(approvalId);
  const timeline = useApprovalTimeline(approvalId);
  const editableFields = useApprovalEditableFields(approvalId);
  const decision = useApprovalDecision(approvalId);
  const [sheet, setSheet] = useState<"reject" | "edit" | null>(null);
  const [reason, setReason] = useState("");
  const [patch, setPatch] = useState<Record<string, string>>({});
  const [outletSavePending, setOutletSavePending] = useState(false);
  const handleOutletSavePendingChange = useCallback((pending: boolean) => {
    setOutletSavePending(pending);
  }, []);

  if (!approvalId) {
    return <ManagementScreen view="approval-detail"><EmptyState icon="CheckCircle" title="No approval selected" message="Open an approval from the inbox." actionLabel="Approvals" onAction={() => router.push("/mgmt/approvals")} /></ManagementScreen>;
  }
  if (detail.isPending || timeline.isPending) {
    return <ManagementScreen view="approval-detail"><div className={styles.content}><Skeleton height={92} radius={12} /><Skeleton height={160} radius={12} /></div></ManagementScreen>;
  }
  if (detail.isError || !detail.data) {
    return <ManagementScreen view="approval-detail"><div className={styles.content}><ErrorState title="Approval unavailable" message="This approval could not be loaded." onRetry={() => { void Promise.all([detail.refetch(), timeline.refetch(), editableFields.refetch()]); }} /></div></ManagementScreen>;
  }

  const request = detail.data.request;
  const isBeatRequest = request.subject_type.startsWith("beat");
  const outletSummary = request.subject_type === "outlet_verification"
    ? outletApprovalSummary(detail.data.blocks, request)
    : null;
  const outletDetails = request.subject_type === "outlet_verification"
    ? renderOutletApprovalDetails(detail.data.blocks, request.subject_id)
    : null;
  const dpOrderDetails = request.subject_type === "dp_order"
    ? parseDpOrderRequestDetails(detail.data.blocks)
    : null;
  const beatSubjectId = isBeatRequest && !(request.subject_type === "beat_create" && request.status === "rejected") ? request.subject_id : "";
  const summaryTitle = outletSummary?.title ?? (isBeatRequest ? approvalDisplayTitle(request) : approvalDisplaySubtitle(request));
  const summarySubtitle = outletSummary?.subtitle ?? (beatSubjectId
    ? <BeatRequestFrequency beatId={beatSubjectId} />
    : `${approvalSubjectLabel(request.subject_type)} · ${formatDateTime(request.submitted_at)}`);
  const steps: StatusHistoryStep[] = (timeline.data?.items ?? detail.data.timeline).map((step) => ({
    label: timelineActionLabel(step.action),
    detail: timelineDetail(step.note),
    time: formatDateTime(step.occurred_at),
    state: timelineState(step.state),
  }));
  const fields = editableFields.data?.items ?? detail.data.editable_fields;
  const detailBlocks = beatSubjectId || outletDetails || dpOrderDetails ? [] : detail.data.blocks;
  const canDecideRequest = request.is_pending && request.can_decide;
  const decisionPending = decision.approve.isPending || decision.reject.isPending || decision.editAndApprove.isPending;
  const pending = decisionPending || outletSavePending;
  const approve = () => {
    if (pending) return;
    void decision.approve.mutateAsync({ subjectVersion: request.subject_version, idempotencyKey: createIdempotencyKey() })
      .then(() => router.push("/mgmt/approvals"));
  };
  const reject = () => {
    if (!reason.trim() || pending) return;
    void decision.reject.mutateAsync({ subjectVersion: request.subject_version, reason: reason.trim(), idempotencyKey: createIdempotencyKey() })
      .then(() => router.push("/mgmt/approvals"));
  };
  const editAndApprove = () => {
    const normalized = Object.fromEntries(Object.entries(patch).filter(([, value]) => value.trim()));
    if (!Object.keys(normalized).length || pending) return;
    void decision.editAndApprove.mutateAsync({ subjectVersion: request.subject_version, patch: normalized, idempotencyKey: createIdempotencyKey() })
      .then(() => router.push("/mgmt/approvals"));
  };
  const dpOrderPricedSummaryLines = dpOrderDetails?.pricedLines.map(mapDpOrderSummaryLine) ?? [];
  const dpOrderQuantityOnlySummaryLines = dpOrderDetails?.quantityOnlyLines.map(mapDpOrderSummaryLine) ?? [];
  const dpOrderTotalItemCount = [...dpOrderPricedSummaryLines, ...dpOrderQuantityOnlySummaryLines]
    .reduce((total, line) => total + line.approvedQty, 0);

  return (
    <ManagementScreen
      view="approval-detail"
      title={outletSummary?.title ?? approvalDisplayTitle(request)}
      footer={canDecideRequest ? (
        <>
          <Button variant="outlined" color="error" label="Reject" disabled={pending} onClick={() => setSheet("reject")} />
          {detail.data.is_editable && fields.length ? <Button variant="outlined" color="neutral" label="Edit" disabled={pending} leftIcon={<Icon name="Edit" size={18} color="currentColor" />} onClick={() => setSheet("edit")} /> : null}
          <Button variant="filled" color="success" label="Approve" loading={decision.approve.isPending} disabled={pending} onClick={approve} />
        </>
      ) : undefined}
    >
      <div className={styles.content}>
        <div className={styles.card}>
          <div className={styles.teamTop}>
            <span className={styles.rowCopy}><strong>{summaryTitle}</strong><span>{summarySubtitle}</span></span>
            <StatusChip status={statusTone(request.status)} label={humanLabel(request.status)} type="filled" />
          </div>
          {request.amount_paise ? <strong className="sp-metric-value" style={{ color: "var(--color-primary)", marginTop: 12 }}>{moneyFromPaise(request.amount_paise)}</strong> : null}
        </div>
        {detail.data.advisories.map((advisory) => <Notice key={advisory.code} tone={advisory.severity === "warning" ? "warning" : "info"}>{advisory.message}</Notice>)}
        {beatSubjectId ? <BeatApprovalSubjectDetails beatId={beatSubjectId} canEditOutlets={canDecideRequest} onOutletSavePendingChange={handleOutletSavePendingChange} /> : null}
        {dpOrderDetails ? (
          <>
            <Section label="Order details">
              <div className={styles.card} style={{ padding: 0 }}>
                {renderDetailRow("Outlet", dpOrderDetails.outlet ?? "—", "dp-order-outlet", styles.approvalDetailRow)}
                {renderDetailRow("Manufacturer", dpOrderDetails.manufacturer ?? "—", "dp-order-manufacturer", styles.approvalDetailRow)}
                {dpOrderDetails.sourcePo ? renderDetailRow("Source PO", dpOrderDetails.sourcePo ?? "—", "dp-order-source-po", styles.approvalDetailRow) : null}
              </div>
            </Section>
            <OrderSummarySections
              pricedLines={dpOrderPricedSummaryLines}
              quantityOnlyLines={dpOrderQuantityOnlySummaryLines}
              schemeLabel={dpOrderDetails.schemeLabel}
              priceSummary={dpOrderDetails.pricedLines.length ? {
                itemCount: dpOrderTotalItemCount,
                subtotalPaise: dpOrderDetails.subtotalNetPaise,
                productDiscountPaise: dpOrderDetails.productDiscountPaise,
                schemeDiscountPaise: dpOrderDetails.schemeDiscountPaise,
                gstPaise: dpOrderDetails.gstAmountPaise,
                totalPaise: dpOrderDetails.grossTotalPaise,
              } : null}
            />
          </>
        ) : null}
        {detailBlocks.length ? (
          <Section label="Request details">
            <div className={styles.card} style={{ padding: 0 }}>
              {detailBlocks.map((block) => renderDetailBlock(block, styles.approvalDetailRow))}
            </div>
          </Section>
        ) : null}
        {outletDetails}
        <StatusHistory steps={steps} historyKey={approvalId} />
      </div>
      <BottomSheet open={sheet === "reject"} onClose={() => { if (!pending) setSheet(null); }} title="Reject request">
        <p className={styles.meta} style={{ margin: "0 0 var(--space-sm)" }}>Add a reason. The requester will see it.</p>
        <TextField placeholder="Reason" multiline rows={3} value={reason} disabled={pending} onChange={(event) => setReason((event.target as HTMLInputElement).value)} />
        <div style={{ marginTop: 16 }}>
          <Button variant="filled" color="error" label="Reject request" loading={decision.reject.isPending} disabled={!reason.trim() || pending} onClick={reject} style={{ width: "100%" }} />
        </div>
      </BottomSheet>
      <BottomSheet open={sheet === "edit"} onClose={() => { if (!pending) setSheet(null); }} title="Edit before approving">
        <div className={styles.form}>
          {fields.map((field) => (
            <TextField
              key={field.key}
              label={field.label}
              value={patch[field.key] ?? String(field.current_value ?? "")}
              disabled={pending}
              onChange={(event) => setPatch((current) => ({ ...current, [field.key]: (event.target as HTMLInputElement).value }))}
            />
          ))}
        </div>
        <div style={{ marginTop: "var(--space-md)" }}>
          <Button variant="filled" color="success" label="Approve with edits" loading={decision.editAndApprove.isPending} disabled={pending} onClick={editAndApprove} style={{ width: "100%" }} />
        </div>
      </BottomSheet>
    </ManagementScreen>
  );
}

function loginCopy(active: boolean) {
  return active
    ? {
        chipStatus: "verified" as const,
        chipLabel: "Active",
        detail: "Can sign in",
        effect: "They can sign in with this phone number and an OTP.",
      }
    : {
        chipStatus: "cancelled" as const,
        chipLabel: "Inactive",
        detail: "Cannot sign in",
        effect: "They cannot receive an OTP or start a session. Their record, visits, and orders stay on file.",
      };
}

function ScopedTeamOverview() {
  const router = useRouter();
  const employees = useEmployees();
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const rows = useMemo(
    () => (employees.data?.items ?? []).filter((employee) =>
      !needle
      || `${employee.full_name} ${employee.employee_code}`.toLowerCase().includes(needle)
    ),
    [employees.data, needle],
  );
  return (
    <ManagementScreen view="team">
      <div className={styles.listHeader}>
        <TextField
          placeholder="Search your team"
          value={query}
          onChange={(event) => setQuery((event.target as HTMLInputElement).value)}
          startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
        />
      </div>
      {employees.isPending || employees.isError ? (
        <EmployeeQueryState error={employees.isError} loading={employees.isPending} onRetry={() => { void employees.refetch(); }} />
      ) : rows.length ? (
        <div className={styles.listBody}>
          {rows.map((employee) => (
            <ListRow
              key={employee.id}
              leading={<span className={`${styles.avatar} ${employeeStatusActive(employee) ? "" : styles.avatarMuted}`}>{employee.display_initials}</span>}
              title={employee.full_name}
              subtitle={`${employeeRoleLabel(employee.role_code)} · ${employee.employee_code}`}
              trailing={<StatusChip status={employeeStatusActive(employee) ? "verified" : "cancelled"} label={employee.login_enabled ? "Active" : "Inactive"} type="outlined" />}
              showChevron
              onClick={() => router.push(`/mgmt/employee?id=${encodeURIComponent(employee.id)}`)}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon="PersonRounded"
          title={needle ? "No people match" : "No one in your team"}
          message={needle ? "Try another name or employee code." : "People in your server-authorized subtree will appear here."}
          actionLabel={needle ? "Clear search" : undefined}
          onAction={needle ? () => setQuery("") : undefined}
        />
      )}
    </ManagementScreen>
  );
}

function TeamDay() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAdmin } = useManagementRole();
  const employeeId = searchParams.get("id") ?? "";
  const employeeName = searchParams.get("name") ?? "";
  const requestedDate = searchParams.get("date");
  const [businessDate, setBusinessDate] = useState(() => isIsoBusinessDate(requestedDate) ? requestedDate : istDateISO());
  useEffect(() => {
    setBusinessDate(isIsoBusinessDate(requestedDate) ? requestedDate : istDateISO());
  }, [requestedDate]);
  const route = useRouteDay(businessDate, { enabled: Boolean(employeeId) }, employeeId);
  const retryRoute = () => { void route.refetch(); };
  const footer = !isAdmin
    ? <Button variant="filled" color="primary" label="Schedule combined visit" onClick={() => router.push(startCombinedVisitPath(employeeId || undefined))} />
    : undefined;
  const punchInSubtitle = employeeName ? `${employeeName} started duty` : "Duty started";
  const punchOutSubtitle = employeeName ? `${employeeName} ended duty` : "Duty ended";
  return (
    <ManagementScreen view="team-day" title={employeeName || undefined} footer={footer}>
      <div className={styles.content}>
        {employeeId ? <DateField label="Business date" value={formatBusinessDate(businessDate)} dateValue={businessDate} onChange={setBusinessDate} /> : null}
        {!employeeId ? (
          <EmptyState icon="Map" title="No employee selected" message="Open this screen from a coverage row to see that employee's day." actionLabel="Back to coverage" onAction={() => router.push("/mgmt/coverage")} />
        ) : route.isPending ? (
          <RouteDayTimelineLoading />
        ) : route.isError ? (
          <ErrorState title="Day timeline unavailable" message="This report's route plan could not be loaded." onRetry={retryRoute} />
        ) : !route.data ? (
          <ErrorState title="Day timeline unavailable" message="This report's route plan could not be loaded." onRetry={retryRoute} />
        ) : (
          <RouteDayTimeline
            routeDay={route.data}
            locationQueryScope={`team-day:${employeeId}:${businessDate}`}
            mapLabelWithMarkers="Route check-ins"
            mapLabelWithoutMarkers="No check-in pins yet"
            punchInSubtitle={punchInSubtitle}
            punchOutSubtitle={punchOutSubtitle}
          />
        )}
      </div>
    </ManagementScreen>
  );
}

function useOpenEmployee() {
  const router = useRouter();
  return (id: string) => {
    router.push(`/mgmt/employee?id=${encodeURIComponent(id)}`);
  };
}

function employeeRoleLabel(roleCode: string) {
  if (roleCode === "admin") return "Admin";
  if (roleCode === "manager") return "Manager";
  return "Sales Person";
}

const DESIGNATIONS_BY_ROLE: Record<"mgr" | "sp", { value: string; label: string }[]> = {
  mgr: [
    { value: "national_sales_head", label: "National Sales Head" },
    { value: "segment_business_head", label: "Segment Business Head" },
    { value: "regional_sales_manager", label: "Regional Sales Manager" },
    { value: "area_sales_manager", label: "Area Sales Manager" },
  ],
  sp: [
    { value: "network_officer_salesperson", label: "Network Officer - Salesperson" },
    {
      value: "territory_development_officer_salesperson",
      label: "Territory Development Officer - Salesperson",
    },
  ],
};

const MANAGER_DESIGNATION_RANK = DESIGNATIONS_BY_ROLE.mgr.reduce<Record<string, number>>((acc, option, index) => {
  acc[option.value] = index;
  return acc;
}, {});

function canReportToManagerDesignation(subjectDesignationCode: string, managerDesignationCode: string) {
  const subjectRank = MANAGER_DESIGNATION_RANK[subjectDesignationCode];
  const managerRank = MANAGER_DESIGNATION_RANK[managerDesignationCode];
  if (subjectRank === undefined || managerRank === undefined) return true;
  return managerRank < subjectRank;
}

function designationLabel(designationCode: string) {
  if (designationCode === "all") return "All levels";
  if (designationCode === "admin") return "Admin";
  for (const options of Object.values(DESIGNATIONS_BY_ROLE)) {
    const match = options.find((option) => option.value === designationCode);
    if (match) return match.label;
  }
  return designationCode;
}

function needsManagerAssignment(employee: EmployeeResponse) {
  return employee.role_code === "sales_person" && !employee.manager_employee_id;
}

function employeeStatusActive(employee: EmployeeResponse) {
  return employee.status === "active" && employee.login_enabled;
}

function EmployeeQueryState({
  error,
  loading,
  onRetry,
}: {
  error: boolean;
  loading: boolean;
  onRetry: () => void;
}) {
  if (loading) {
    return (
      <div className={styles.content}>
        <Skeleton height={72} radius={12} />
        <Skeleton height={72} radius={12} />
        <Skeleton height={72} radius={12} />
      </div>
    );
  }
  if (error) {
    return (
      <div className={styles.content}>
        <ErrorState
          title="Organization unavailable"
          message="The scoped organization data could not be loaded."
          onRetry={onRetry}
        />
      </div>
    );
  }
  return null;
}

function EmployeeList() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAdmin } = useManagementRole();
  const openEmployee = useOpenEmployee();
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedSearchQuery(query);
  const requested = searchParams.get("filter");
  const chip: EmployeeFilter = isEmployeeFilter(requested) ? requested : "all";
  const employees = useEmployees({
    query: debouncedQuery.trim() || undefined,
    role: chip === "sp" ? "sales_person" : chip === "mgr" ? "manager" : undefined,
    status: chip === "active" ? "active" : chip === "inactive" ? "inactive" : undefined,
  });
  const visible = useMemo(
    () => (employees.data?.items ?? []).filter((employee) => {
      if (chip === "missing-manager") return needsManagerAssignment(employee);
      return true;
    }),
    [employees.data, chip],
  );
  const chips: Array<[EmployeeFilter, string]> = isAdmin
    ? [["all", "All"], ["sp", "Sales"], ["mgr", "Managers"], ["active", "Active"], ["inactive", "Inactive"], ["missing-manager", "No manager"]]
    : [["all", "All"], ["sp", "Sales"], ["mgr", "Managers"], ["inactive", "Inactive"]];
  const addEmployee = isAdmin
    ? <Button variant="filled" color="primary" label="Add employee" leftIcon={<Icon name="Add" size={18} color="currentColor" />} onClick={() => router.push("/mgmt/employee-add")} />
    : undefined;
  const countLabel = chip === "all"
    ? (isAdmin ? `${employees.data?.total ?? 0} employees` : `${employees.data?.total ?? 0} in your tree`)
    : `${visible.length} matching`;
  const queryState = (
    <EmployeeQueryState
      error={employees.isError}
      loading={employees.isPending}
      onRetry={() => { void employees.refetch(); }}
    />
  );
  return (
    <ManagementScreen view="employees" title={isAdmin ? "Employees" : "My team"} footer={addEmployee}>
      <div className={styles.listHeader}>
        <TextField placeholder="Search by name or geography" value={query} onChange={(event) => setQuery((event.target as HTMLInputElement).value)} startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />} />
        <div className={styles.chipRow}>{chips.map(([value, label]) => <button data-active={chip === value} key={value} onClick={() => router.replace(employeesHref(value))} type="button">{label}</button>)}</div>
      </div>
      <p className={styles.countCaption}>{countLabel}</p>
      {employees.isPending || employees.isError ? queryState : visible.length ? (
        <div className={styles.listBody}>
          {visible.map((employee) => (
            <ListRow
              key={employee.id}
              leading={<span className={`${styles.avatar} ${employeeStatusActive(employee) ? "" : styles.avatarMuted}`}>{employee.display_initials}</span>}
              title={employee.full_name}
              subtitle={`${employeeRoleLabel(employee.role_code)} · ${employee.employee_code}`}
              trailing={<StatusChip status={employeeStatusActive(employee) ? "verified" : "cancelled"} label={employee.login_enabled ? "Active" : "Inactive"} type="outlined" />}
              showChevron
              onClick={() => openEmployee(employee.id)}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon="PersonRounded"
          title="No employees found"
          message="Adjust filters, or add an employee to get started."
          actionLabel={chip !== "all" ? "Show all" : isAdmin ? "Add employee" : undefined}
          onAction={chip !== "all" ? () => router.replace(employeesHref()) : isAdmin ? () => router.push("/mgmt/employee-add") : undefined}
        />
      )}
    </ManagementScreen>
  );
}

function labelledCluster(
  ids: string[] | undefined,
  labels: Array<{ id: string; name: string }> | undefined,
) {
  if (!ids?.length) return "Not assigned";
  const byId = new Map((labels ?? []).map((label) => [label.id, label.name]));
  return ids.map((id) => byId.get(id) ?? id).join(", ");
}

function labelledDistrictCluster(
  ids: string[] | undefined,
  labels: Array<{ id: string; name: string; state_name: string }> | undefined,
) {
  if (!ids?.length) return "Not assigned";
  const byId = new Map((labels ?? []).map((label) => [label.id, label]));
  const nameCounts = new Map<string, number>();
  for (const id of ids) {
    const name = byId.get(id)?.name ?? id;
    nameCounts.set(name, (nameCounts.get(name) ?? 0) + 1);
  }
  return ids.map((id) => {
    const label = byId.get(id);
    if (!label) return id;
    return (nameCounts.get(label.name) ?? 0) > 1 ? `${label.name} (${label.state_name})` : label.name;
  }).join(", ");
}

function ExpandableClusterValue({
  value,
  accent,
}: {
  value: string;
  accent?: boolean;
}) {
  const probeRef = useRef<HTMLElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);

  useLayoutEffect(() => {
    const probe = probeRef.current;
    if (!probe) return;
    const update = () => {
      const computed = getComputedStyle(probe);
      const parsedLineHeight = Number.parseFloat(computed.lineHeight);
      const lineHeight = Number.isFinite(parsedLineHeight)
        ? parsedLineHeight
        : Number.parseFloat(computed.fontSize) * 1.25;
      setOverflows(probe.scrollHeight > lineHeight * 2 + 1);
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(probe);
    return () => observer.disconnect();
  }, [value]);

  return (
    <div className={styles.clusterValue}>
      <strong
        className={`${accent ? styles.clusterAccent : ""} ${expanded ? styles.clusterTextOpen : styles.clusterText}`}
      >
        {value}
      </strong>
      {value === "Not assigned" ? null : (
        <strong ref={probeRef} aria-hidden className={styles.clusterProbe}>
          {value}
        </strong>
      )}
      {overflows ? (
        <button
          aria-expanded={expanded}
          className={`${styles.clusterExpand} ${expanded ? styles.clusterExpandOpen : ""}`}
          onClick={() => setExpanded((open) => !open)}
          type="button"
        >
          {expanded ? "Show less" : "Show more"}
          <Icon name="KeyboardArrowDown" size={16} color="var(--color-primary)" />
        </button>
      ) : null}
    </div>
  );
}

function EmployeeDetailRow({
  label,
  value,
  expandable,
  onClick,
}: {
  label: string;
  value: string;
  expandable?: boolean;
  onClick?: () => void;
}) {
  if (expandable) {
    return (
      <div className={`${styles.detailRow} ${styles.detailRowCluster}`}>
        <span>{label}</span>
        <div className={styles.clusterBody}>
          <ExpandableClusterValue value={value} accent={Boolean(onClick)} />
          {onClick ? (
            <button aria-label={label} className={styles.clusterNav} onClick={onClick} type="button">
              <Icon name="KeyboardArrowRight" size={18} color="var(--color-primary)" />
            </button>
          ) : null}
        </div>
      </div>
    );
  }
  if (onClick) {
    return (
      <button className={styles.detailRow} onClick={onClick} type="button">
        <span>{label}</span>
        <span className={styles.detailValue}>{value}<Icon name="KeyboardArrowRight" size={18} color="var(--color-primary)" /></span>
      </button>
    );
  }
  return (
    <div className={styles.detailRow}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function employeeInitials(name: string) {
  return name.split(" ").filter(Boolean).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function OrgTreeNode({
  node,
  collapsed,
  onToggle,
  openEmployee,
}: {
  node: TreeNodeResponse;
  collapsed: Set<string>;
  onToggle: (id: string) => void;
  openEmployee: (id: string) => void;
}) {
  const children = node.children ?? [];
  const hasChildren = children.length > 0;
  const isCollapsed = collapsed.has(node.id);
  const toggleLabel = hasChildren ? `${isCollapsed ? "Expand" : "Collapse"} ${node.full_name}` : `${node.full_name} has no reports`;
  return (
    <>
      <div className={styles.treeItem} data-level={node.depth} style={{ "--level": node.depth } as CSSProperties}>
        <button
          aria-expanded={hasChildren ? !isCollapsed : undefined}
          aria-label={toggleLabel}
          className={styles.treeToggle}
          disabled={!hasChildren}
          onClick={() => onToggle(node.id)}
          type="button"
        >
          {hasChildren ? (
            <Icon name={isCollapsed ? "KeyboardArrowRight" : "KeyboardArrowDown"} size={20} color="var(--color-primary)" />
          ) : null}
        </button>
        <button className={styles.treeNode} onClick={() => openEmployee(node.id)} type="button">
          <div className={styles.card}>
            <div className={styles.teamTop}>
              <span className={`${styles.avatar} ${node.status === "active" ? "" : styles.avatarMuted}`}>
                {employeeInitials(node.full_name)}
              </span>
              <span className={styles.rowCopy}>
                <strong>{node.full_name}</strong>
                <span>{designationLabel(node.designation_code)}</span>
              </span>
              {node.is_actor ? <StatusChip status="verified" label="You" type="outlined" /> : null}
            </div>
          </div>
        </button>
      </div>
      {hasChildren && !isCollapsed ? children.map((child) => (
        <OrgTreeNode
          collapsed={collapsed}
          key={child.id}
          node={child}
          onToggle={onToggle}
          openEmployee={openEmployee}
        />
      )) : null}
    </>
  );
}

function OrgTree() {
  const router = useRouter();
  const { isAdmin } = useManagementRole();
  const openEmployee = useOpenEmployee();
  const tree = useOrganizationTree();
  const nodes = tree.data?.roots ?? [];
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const toggleNode = useCallback((id: string) => {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);
  const addEmployee = isAdmin
    ? <Button variant="filled" color="primary" label="Add employee" leftIcon={<Icon name="Add" size={18} color="currentColor" />} onClick={() => router.push("/mgmt/employee-add")} />
    : undefined;
  return (
    <ManagementScreen view="org-tree" footer={addEmployee}>
      <div className={styles.content}>
        {tree.isPending || tree.isError ? (
          <EmployeeQueryState
            error={tree.isError}
            loading={tree.isPending}
            onRetry={() => { void tree.refetch(); }}
          />
        ) : nodes.length ? (
          <div className={styles.tree}>
            {nodes.map((node) => (
              <OrgTreeNode
                collapsed={collapsed}
                key={node.id}
                node={node}
                onToggle={toggleNode}
                openEmployee={openEmployee}
              />
            ))}
          </div>
        ) : (
          <EmptyState icon="AccountTree" title="No reporting tree" message={isAdmin ? "Add an employee to start the hierarchy." : "No one reports to you yet."} />
        )}
      </div>
    </ManagementScreen>
  );
}

function EmployeeDetail() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAdmin } = useManagementRole();
  const employeeId = searchParams.get("id");
  const employee = useEmployee(employeeId);
  const manager = useEmployee(employee.data?.manager_employee_id);
  const geography = useGeographyScope(employeeId);
  if (!employeeId) {
    return <ManagementScreen view="employee"><EmptyState icon="PersonRounded" title="No employee selected" message="Open an employee from the list." actionLabel="Employees" onAction={() => router.push("/mgmt/employees")} /></ManagementScreen>;
  }
  if (employee.isPending || employee.isError) {
    return <ManagementScreen view="employee"><EmployeeQueryState error={employee.isError} loading={employee.isPending} onRetry={() => { void employee.refetch(); }} /></ManagementScreen>;
  }
  const member = employee.data;
  if (!member) return null;
  const reportsTo = manager.data ? `${manager.data.full_name} (Manager)` : "Top level";
  const isActive = employeeStatusActive(member);
  const isSalesPerson = member.role_code === "sales_person";
  const canScheduleCombinedVisit = !isAdmin && isSalesPerson;
  const todayCoverageHref = `/mgmt/team-day?id=${encodeURIComponent(member.id)}&name=${encodeURIComponent(member.full_name)}&date=${encodeURIComponent(istDateISO())}`;
  const footer = isAdmin
    ? <Button variant="filled" color="primary" label="Edit employee" onClick={() => router.push(`/mgmt/employee-edit?id=${encodeURIComponent(member.id)}`)} />
    : canScheduleCombinedVisit
      ? <Button variant="filled" color="primary" label="Schedule combined visit" disabled={!isActive} onClick={() => router.push(startCombinedVisitPath(member.id))} />
      : undefined;
  const scope = geography.data;
  const labels = scope?.geo_labels;
  const geographyActionLabel = scope?.districts?.length ? "Edit geography scope" : "Assign geography scope";
  const sections: Array<{
    label: string;
    rows: Array<[string, string, (() => void) | undefined, boolean?]>;
  }> = [
    {
      label: "Role and reporting",
      rows: [
        ["Role", employeeRoleLabel(member.role_code), undefined],
        ["Designation", designationLabel(member.designation_code), undefined],
        ["Reports to", reportsTo, isAdmin ? () => router.push(`/mgmt/hierarchy?id=${encodeURIComponent(member.id)}`) : undefined],
      ],
    },
    {
      label: "Geography scope",
      rows: [
        ["Zone cluster", labelledCluster(scope?.zones, labels?.zones), undefined, true],
        ["State cluster", labelledCluster(scope?.states, labels?.states), undefined, true],
        ["District cluster", labelledDistrictCluster(scope?.districts, labels?.districts), isAdmin ? () => router.push(`/mgmt/geography?id=${encodeURIComponent(member.id)}`) : undefined, true],
      ],
    },
  ];
  return (
    <ManagementScreen view="employee" title={member.full_name} footer={footer}>
      <div className={styles.content}>
        <div className={styles.card}>
          <div className={styles.teamTop}>
            <span className={styles.avatarWrap} aria-label={isActive ? "Active" : "Inactive"}>
              <span className={`${styles.avatar} ${isActive ? "" : styles.avatarMuted}`} style={{ height: 56, width: 56 }}>{member.display_initials}</span>
              <i aria-hidden className={`${styles.statusDot} ${isActive ? "" : styles.statusDotInactive}`} />
            </span>
            <span className={styles.rowCopy}>
              <strong>{member.full_name}</strong>
              <span>{employeeRoleLabel(member.role_code)} · {member.employee_code}</span>
            </span>
            {member.phone_e164 ? (
              <a aria-label={`Call ${member.full_name}`} className={styles.callButton} href={`tel:${member.phone_e164}`}>
                <Icon name="Call" size={30} color="var(--color-primary)" />
              </a>
            ) : null}
          </div>
        </div>
        {member.login_enabled ? null : <Notice tone="warning">{loginCopy(false).effect} Reactivation is not available in the released API.</Notice>}
        {geography.isError ? <Notice tone="warning">Geography assignment is unavailable right now.</Notice> : null}
        {sections.map((section) => (
          <Section key={section.label} label={section.label}>
            <div className={styles.card} style={{ padding: 0 }}>
              {section.rows.map(([label, value, onClick, expandable]) => (
                <EmployeeDetailRow key={label} expandable={expandable} label={label} onClick={onClick} value={value} />
              ))}
            </div>
            {isAdmin && section.label === "Geography scope" ? (
              <Button
                variant="outlined"
                color="primary"
                label={geographyActionLabel}
                onClick={() => router.push(`/mgmt/geography?id=${encodeURIComponent(member.id)}`)}
                style={{ width: "100%" }}
              />
            ) : null}
          </Section>
        ))}
        {isSalesPerson ? (
          <Section label="Actions">
            <div className={styles.form}>
              <Button variant="outlined" color="primary" label="Show today's coverage" onClick={() => router.push(todayCoverageHref)} style={{ width: "100%" }} />
              {isAdmin
              ? <Button variant="outlined" color="primary" label="View geography scope" onClick={() => router.push(`/mgmt/geography?id=${encodeURIComponent(member.id)}`)} style={{ width: "100%" }} />
              : null}
            </div>
          </Section>
        ) : null}
      </div>
    </ManagementScreen>
  );
}

function EmployeeForm({ mode }: { mode: "add" | "edit" }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const employeeId = mode === "edit" ? searchParams.get("id") : null;
  const employee = useEmployee(employeeId);
  if (mode === "edit" && !employeeId) {
    return <ManagementScreen view="employee-edit"><EmptyState icon="PersonRounded" title="No employee selected" message="Open an employee before editing." actionLabel="Employees" onAction={() => router.push("/mgmt/employees")} /></ManagementScreen>;
  }
  if (mode === "edit" && (employee.isPending || employee.isError)) {
    return <ManagementScreen view="employee-edit"><EmployeeQueryState error={employee.isError} loading={employee.isPending} onRetry={() => { void employee.refetch(); }} /></ManagementScreen>;
  }
  return <EmployeeFormFields mode={mode} editing={employee.data ?? null} />;
}

function EmployeeFormFields({
  mode,
  editing,
}: {
  mode: "add" | "edit";
  editing: EmployeeResponse | null;
}) {
  const router = useRouter();
  const isEdit = mode === "edit";
  const employeeId = editing?.id ?? null;
  const managers = useEmployees({ role: "manager", status: "active" });
  const mutations = useOrganizationMutations();
  const [fullName, setFullName] = useState(editing?.full_name ?? "");
  const [phone, setPhone] = useState("");
  const [employeeRole, setEmployeeRole] = useState(editing?.role_code === "manager" ? "mgr" : "sp");
  const [designation, setDesignation] = useState(editing?.designation_code ?? "");
  const [parentId, setParentId] = useState(editing?.manager_employee_id ?? "");
  const [active, setActive] = useState(editing?.login_enabled ?? true);
  const [confirmDisable, setConfirmDisable] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const digits = phone.replace(/\D/g, "");
  const nameError = submitted && !fullName.trim();
  const phoneError = !isEdit && submitted && digits.length !== 10;
  const designationOptions = DESIGNATIONS_BY_ROLE[employeeRole as "mgr" | "sp"];
  const designationError = submitted && !designation;
  const setRole = (value: string) => {
    setEmployeeRole(value);
    if (!DESIGNATIONS_BY_ROLE[value as "mgr" | "sp"].some((option) => option.value === designation)) {
      setDesignation("");
    }
  };
  const login = loginCopy(active);
  const options = useMemo(
    () => (managers.data?.items ?? [])
      .filter((manager) => manager.id !== employeeId)
      .filter((manager) => {
        if (employeeRole !== "mgr" || !designation) return true;
        return canReportToManagerDesignation(designation, manager.designation_code);
      })
      .map((manager) => ({ value: manager.id, label: `${manager.full_name} (Manager)` })),
    [managers.data, employeeId, employeeRole, designation],
  );
  useEffect(() => {
    if (!parentId) return;
    if (!options.some((option) => option.value === parentId)) setParentId("");
  }, [options, parentId]);
  const save = async () => {
    setSubmitted(true);
    setError(null);
    if (!fullName.trim() || (!isEdit && digits.length !== 10) || !designation) return;
    try {
      let savedId = employeeId;
      if (isEdit && editing) {
        await mutations.updateEmployee.mutateAsync({
          employeeId: editing.id,
          body: {
            full_name: fullName.trim(),
            role_code: employeeRole === "mgr" ? "manager" : "sales_person",
            designation_code: designation,
          },
        });
        if (editing.login_enabled && !active) {
          await mutations.deactivateEmployee.mutateAsync({
            employeeId: editing.id,
            reason: "Deactivated by administrator",
          });
        }
      } else {
        const roleCode = employeeRole === "mgr" ? "manager" : "sales_person";
        const created = await mutations.createEmployee.mutateAsync({
          employee_code: `${roleCode === "manager" ? "MGR" : "SP"}-${digits}`,
          full_name: fullName.trim(),
          phone_e164: `+91${digits}`,
          role_code: roleCode,
          designation_code: designation,
          manager_employee_id: parentId || null,
          login_enabled: active,
        });
        savedId = created.id;
      }
      if (savedId) router.push(`/mgmt/employee?id=${encodeURIComponent(savedId)}`);
    } catch (saveError) {
      setError(mutationErrorMessage(saveError));
    }
  };
  const pending = mutations.createEmployee.isPending
    || mutations.updateEmployee.isPending
    || mutations.deactivateEmployee.isPending;
  return (
    <ManagementScreen view={isEdit ? "employee-edit" : "employee-add"} footer={<Button variant="filled" color="primary" label={isEdit ? "Save employee" : "Create employee"} disabled={pending} onClick={() => { void save(); }} />}>
      <div className={`${styles.content} ${styles.form}`}>
        {error ? <Notice tone="warning">{error}</Notice> : null}
        <TextField label="Full name" placeholder="e.g. Rahul Kumar" value={fullName} onChange={(event) => setFullName((event.target as HTMLInputElement).value)} error={nameError} helperText={nameError ? "Name is required" : undefined} required />
        {isEdit ? <TextField label="Employee ID" placeholder="e.g. HB-SP-2049" value={editing?.employee_code ?? ""} disabled helperText="Employee ID cannot be changed" required /> : null}
        <TextField label="Mobile number" placeholder={isEdit ? editing?.phone_e164 : "98765 43210"} value={isEdit ? "" : phone} onChange={isEdit ? undefined : (event) => { const value = (event.target as HTMLInputElement).value.replace(/\D/g, '').slice(0, 10); setPhone(value); }} inputProps={!isEdit ? { inputMode: 'numeric', maxLength: 10, pattern: '[0-9]*' } : undefined} disabled={isEdit} helperText={isEdit ? "Phone changes are not supported by the released API" : phoneError ? "Enter a 10-digit mobile number" : "This number is the login. Sign-in is phone + OTP."} error={phoneError} required={!isEdit} />
        <RadioGroup label="Role" value={employeeRole} onChange={setRole} row options={[{ value: "sp", label: "Sales Person" }, { value: "mgr", label: "Manager" }]} />
        <Select label="Designation" fullWidth value={designation} onChange={setDesignation} error={designationError} helperText={designationError ? "Designation is required" : undefined} options={[{ value: "", label: "— Select designation —" }, ...designationOptions]} />
        {isEdit ? null : <Select label="Reports to" fullWidth value={parentId} onChange={setParentId} options={[{ value: "", label: "— Top level —" }, ...options]} />}
        <Section label="Login">
          <div className={styles.card}>
            <ToggleSwitch
              label={login.chipLabel}
              checked={active}
              disabled={isEdit && !editing?.login_enabled}
              onChange={(event) => {
                if (event.target.checked) setActive(true);
                else setConfirmDisable(true);
              }}
            />
            <p className={styles.meta} style={{ margin: "var(--space-sm) 0 0" }}>{login.effect}</p>
          </div>
          {isEdit && !editing?.login_enabled ? <Notice tone="warning">Reactivation is blocked because the released contract has no reactivation operation.</Notice> : null}
          {active ? null : <Notice tone="warning">Saving will deactivate this account and revoke its sessions.</Notice>}
        </Section>
      </div>
      <BottomSheet open={confirmDisable} title="Turn off login?" onClose={() => setConfirmDisable(false)}>
        <p className={styles.meta} style={{ margin: "0 0 var(--space-md)" }}>They will not be able to sign in or receive an OTP. Existing sessions will be revoked. Their employee record, visits, and orders stay on file.</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
          <Button variant="filled" color="error" label="Turn off login" onClick={() => { setActive(false); setConfirmDisable(false); }} style={{ width: "100%" }} />
          <Button variant="outlined" color="neutral" label="Keep login on" onClick={() => setConfirmDisable(false)} style={{ width: "100%" }} />
        </div>
      </BottomSheet>
    </ManagementScreen>
  );
}

function Hierarchy() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const employeeId = searchParams.get("id");
  const employee = useEmployee(employeeId);
  const candidates = useMoveCandidates(employeeId);
  const managers = useEmployees({ role: "manager", status: "active" });
  const currentManager = useEmployee(employee.data?.manager_employee_id);
  const needsDesignationFilter = employee.data?.role_code === "manager";
  if (!employeeId) {
    return <ManagementScreen view="hierarchy"><EmptyState icon="PersonRounded" title="No employee selected" message="Open an employee, then move them in the hierarchy." actionLabel="Employees" onAction={() => router.push("/mgmt/employees")} /></ManagementScreen>;
  }
  if (
    employee.isPending
    || employee.isError
    || candidates.isPending
    || candidates.isError
    || (needsDesignationFilter && managers.isPending)
    || (needsDesignationFilter && managers.isError)
  ) {
    return <ManagementScreen view="hierarchy"><EmployeeQueryState error={employee.isError || candidates.isError || (needsDesignationFilter && managers.isError)} loading={employee.isPending || candidates.isPending || (needsDesignationFilter && managers.isPending)} onRetry={() => { void Promise.all([employee.refetch(), candidates.refetch(), managers.refetch()]); }} /></ManagementScreen>;
  }
  const member = employee.data;
  if (!member) return null;
  return (
    <HierarchyEditor
      member={member}
      candidates={candidates.data?.items ?? []}
      managers={managers.data?.items ?? []}
      currentManagerName={currentManager.data?.full_name ?? "Top level"}
    />
  );
}

function HierarchyEditor({
  member,
  candidates,
  managers,
  currentManagerName,
}: {
  member: EmployeeResponse;
  candidates: MoveCandidateListResponse["items"];
  managers: EmployeeResponse[];
  currentManagerName: string;
}) {
  const router = useRouter();
  const mutations = useOrganizationMutations();
  const [nextId, setNextId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const options = useMemo(() => {
    const managerDesignationById = new Map(managers.map((manager) => [manager.id, manager.designation_code]));
    return [
      { value: "", label: "— Top level —" },
      ...candidates
        .filter((candidate) => {
          if (member.role_code !== "manager") return true;
          const candidateDesignationCode = managerDesignationById.get(candidate.id);
          if (!candidateDesignationCode) return true;
          return canReportToManagerDesignation(member.designation_code, candidateDesignationCode);
        })
        .map((candidate) => ({
          value: candidate.id,
          label: `${candidate.full_name} (${employeeRoleLabel(candidate.role_code)})`,
        })),
    ];
  }, [candidates, managers, member.designation_code, member.role_code]);
  useEffect(() => {
    if (!nextId) return;
    if (!options.some((option) => option.value === nextId)) setNextId("");
  }, [nextId, options]);
  const nextManager = candidates.find((candidate) => candidate.id === nextId);
  const move = async () => {
    setError(null);
    try {
      await mutations.moveEmployee.mutateAsync({ employeeId: member.id, managerId: nextId || null });
      router.push(`/mgmt/employee?id=${encodeURIComponent(member.id)}`);
    } catch (moveError) {
      setError(mutationErrorMessage(moveError));
    }
  };
  return (
    <ManagementScreen view="hierarchy" footer={<Button variant="filled" color="primary" label="Confirm move" disabled={mutations.moveEmployee.isPending || nextId === (member.manager_employee_id ?? "")} onClick={() => { void move(); }} />}>
      <div className={styles.content}>
        {error ? <Notice tone="warning">{error}</Notice> : null}
        <Section label="Employee"><div className={styles.card}><DataRow initials={member.display_initials} title={member.full_name} subtitle={employeeRoleLabel(member.role_code)} /></div></Section>
        <Section label="Current → new manager">
          <div className={styles.card}><div className={styles.teamTop}><span>{currentManagerName}</span><Icon name="ArrowRight" size={18} color="var(--color-primary)" /><strong>{nextManager?.full_name ?? "Top level"}</strong></div></div>
        </Section>
        <Select label="New manager" fullWidth value={nextId} onChange={setNextId} options={options} />
        <Notice>The server validates hierarchy cycles and scope before applying this move.</Notice>
      </div>
    </ManagementScreen>
  );
}

function Geography() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const employeeId = searchParams.get("id");
  const employee = useEmployee(employeeId);
  const master = useGeographyMaster();
  const assigned = useGeographyScope(employeeId);
  if (!employeeId) {
    return <ManagementScreen view="geography"><EmptyState icon="LocationMarker" title="No employee selected" message="Open an employee, then assign geography." actionLabel="Employees" onAction={() => router.push("/mgmt/employees")} /></ManagementScreen>;
  }
  if (employee.isPending || employee.isError || master.isPending || master.isError || assigned.isPending || assigned.isError) {
    return <ManagementScreen view="geography"><EmployeeQueryState error={employee.isError || master.isError || assigned.isError} loading={employee.isPending || master.isPending || assigned.isPending} onRetry={() => { void Promise.all([employee.refetch(), master.refetch(), assigned.refetch()]); }} /></ManagementScreen>;
  }
  if (!employee.data || !master.data || !assigned.data) return null;
  return (
    <GeographyEditor
      employee={employee.data}
      master={master.data}
      assignedScope={assigned.data}
    />
  );
}

function GeographyEditor({
  employee,
  master,
  assignedScope,
}: {
  employee: EmployeeResponse;
  master: GeographyMasterResponse;
  assignedScope: GeoScopeResponse;
}) {
  const router = useRouter();
  const mutations = useOrganizationMutations();
  const [scope, setScope] = useState<GeoScopeSelection>(() => ({
    zones: assignedScope.zones,
    states: assignedScope.states,
    districts: assignedScope.districts,
    shopCategories: [],
    outletCount: 0,
  }));
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setError(null);
    try {
      await mutations.assignGeography.mutateAsync({
        employeeId: employee.id,
        body: {
          zones: scope.zones,
          states: scope.states,
          districts: scope.districts,
        },
      });
      router.push(`/mgmt/employee?id=${encodeURIComponent(employee.id)}`);
    } catch (saveError) {
      setError(mutationErrorMessage(saveError));
    }
  };
  const pool = master.pool;
  return (
    <ManagementScreen
      view="geography"
      footer={<Button variant="filled" color="primary" label="Assign scope" disabled={!scope.districts.length || mutations.assignGeography.isPending} onClick={() => { void save(); }} />}
    >
      <div className={styles.content}>
        {error ? <Notice tone="warning">{error}</Notice> : null}
        <Notice>{`Assigning geography clusters for ${employee.full_name}.`}</Notice>
        <GeoScopePicker
          zones={master.zones.map((zone) => ({ id: zone.id, label: zone.name }))}
          states={master.states.map((state) => ({ id: state.id, label: state.name, zoneId: state.zone_id }))}
          districts={master.districts.map((district) => ({ id: district.id, label: district.name, stateId: district.state_id }))}
          assigned={pool ? {
            zones: pool.zones,
            states: pool.states,
            districts: pool.districts,
          } : undefined}
          value={scope}
          onChange={setScope}
        />
      </div>
    </ManagementScreen>
  );
}

function CombinedVisit() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAdmin } = useManagementRole();
  const scheduling = searchParams.get("schedule") === "1";
  const employeeId = searchParams.get("employeeId") ?? "";
  useEffect(() => {
    if (!scheduling || isAdmin) return;
    router.replace(startCombinedVisitPath(employeeId || undefined));
  }, [employeeId, isAdmin, router, scheduling]);
  if (scheduling && !isAdmin) {
    return <ManagementScreen view="combined-visits" title="Combined visit"><div className={styles.content}><Skeleton height={72} radius={12} /></div></ManagementScreen>;
  }
  return <CombinedVisitList />;
}

function CombinedVisitList() {
  const router = useRouter();
  const { isAdmin } = useManagementRole();
  const combinedVisits = useCombinedVisits();
  const rows = combinedVisits.data?.items ?? [];
  return (
    <ManagementScreen
      view="combined-visits"
      title="Combined visits"
      footer={!isAdmin ? <Button variant="filled" color="primary" label="Schedule combined visit" onClick={() => router.push(startCombinedVisitPath())} /> : undefined}
    >
      <div className={styles.content}>
        {combinedVisits.isPending ? (
          <>
            <Skeleton height={72} radius={12} />
            <Skeleton height={72} radius={12} />
          </>
        ) : combinedVisits.isError ? (
          <ErrorState title="Combined visits unavailable" message="Scheduled combined visits could not be loaded." onRetry={() => { void combinedVisits.refetch(); }} />
        ) : rows.length ? (
          <div className={styles.card} style={{ padding: 0 }}>
            {rows.map((item) => (
              <CombinedVisitRow
                key={item.id}
                item={item}
                onClick={() => router.push(`/mgmt/visit-feedback?id=${encodeURIComponent(item.id)}`)}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            icon="PersonRounded"
            title="No combined visits"
            message={isAdmin ? "Combined visits scheduled by managers appear here." : "Schedule a tag-along when a manager needs to accompany a sales person."}
            actionLabel={isAdmin ? undefined : "Schedule combined visit"}
            onAction={isAdmin ? undefined : () => router.push(startCombinedVisitPath())}
          />
        )}
      </div>
    </ManagementScreen>
  );
}

function CombinedVisitRow({
  compact = false,
  item,
  onClick,
}: {
  compact?: boolean;
  item: CombinedVisitResponse;
  onClick: () => void;
}) {
  const beat = useBeat(item.beat_id);
  const salesPerson = useEmployee(item.sales_person_employee_id);
  if (beat.isPending || salesPerson.isPending) {
    return (
      <div className={styles.row}>
        <div className={styles.rowCopy}>
          <SpInlineSkeleton width="42%" height={14} />
          <div style={{ marginTop: 6 }}>
            <SpInlineSkeleton width={compact ? "60%" : "76%"} height={12} />
          </div>
        </div>
        {compact ? null : <SpInlineSkeleton width={84} height={24} />}
      </div>
    );
  }
  const outlet = beat.data?.outlets.find((beatOutlet) => beatOutlet.outlet_ref === item.outlet_ref);
  const title = outlet?.name ?? "Outlet details unavailable";
  const salesPersonLabel = salesPerson.data?.full_name ?? "Sales person";
  const beatLabel = beat.data?.display_name ?? "Beat";
  const subtitle = compact
    ? `${salesPersonLabel} · ${formatDate(item.scheduled_business_date)} · ${humanLabel(item.state)}`
    : `${salesPersonLabel} · ${beatLabel} · ${formatDate(item.scheduled_business_date)}`;

  return (
    <DataRow
      icon="PersonRounded"
      title={title}
      subtitle={subtitle}
      trailing={compact ? undefined : <StatusChip status={statusTone(item.state)} label={humanLabel(item.state)} type="outlined" />}
      onClick={onClick}
    />
  );
}

type CombinedVisitStep = "sales_person" | "beat" | "outlet" | "day";

const COMBINED_VISIT_STEPS = ["Sales person", "Beat", "Outlet", "Day"];

function startCombinedVisitPath(employeeId?: string) {
  return employeeId
    ? scheduleCombinedVisitPath("beat", { employeeId })
    : scheduleCombinedVisitPath("sales_person");
}

function scheduleCombinedVisitPath(
  step: CombinedVisitStep,
  params: { employeeId?: string; beatId?: string; outletRef?: string } = {},
) {
  const view = step === "sales_person"
    ? "combined-visit-sales-person"
    : step === "beat"
      ? "combined-visit-beat"
      : step === "outlet"
        ? "combined-visit-outlet"
        : "combined-visit-day";
  const search = new URLSearchParams();
  if (params.employeeId) search.set("employeeId", params.employeeId);
  if (params.beatId) search.set("beatId", params.beatId);
  if (params.outletRef) search.set("outletRef", params.outletRef);
  const query = search.toString();
  return query ? `/mgmt/${view}?${query}` : `/mgmt/${view}`;
}

function CombinedVisitProgress({ step }: { step: number }) {
  return <SpProcessProgress steps={COMBINED_VISIT_STEPS} activeStep={step} />;
}

function CombinedVisitSalesPersonPage() {
  const router = useRouter();
  const { isAdmin } = useManagementRole();
  const employees = useEmployees({ role: "sales_person", status: "active" });
  const salesPeople = useMemo(() => employees.data?.items.filter(employeeStatusActive) ?? [], [employees.data]);
  useEffect(() => {
    router.prefetch(scheduleCombinedVisitPath("beat"));
  }, [router]);
  if (isAdmin) return <CombinedVisitList />;
  return (
    <ManagementScreen view="combined-visit-sales-person">
      <div className={styles.content}>
        <CombinedVisitProgress step={0} />
        {employees.isPending ? (
          <>
            <Skeleton height={72} radius={12} />
            <Skeleton height={72} radius={12} />
          </>
        ) : employees.isError ? (
          <ErrorState title="Sales people unavailable" message="The scoped team list could not be loaded." onRetry={() => { void employees.refetch(); }} />
        ) : salesPeople.length ? (
          <div className={styles.card} style={{ padding: 0 }}>
            {salesPeople.map((employee) => (
              <DataRow
                key={employee.id}
                initials={initials(employee.full_name)}
                title={employee.full_name}
                subtitle={employee.employee_code}
                onClick={() => router.push(scheduleCombinedVisitPath("beat", { employeeId: employee.id }))}
              />
            ))}
          </div>
        ) : (
          <EmptyState icon="PersonRounded" title="No active sales people" message="No active sales people are available under your scope." />
        )}
      </div>
    </ManagementScreen>
  );
}

function CombinedVisitBeatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAdmin } = useManagementRole();
  const employeeId = searchParams.get("employeeId") ?? "";
  const beats = useBeats("approved");
  const employeeBeats = useMemo(
    () => (beats.data?.items ?? [])
      .filter((item) => item.owner_employee_id === employeeId && item.lifecycle_state === "approved" && item.activation_state === "active")
      .map((item) => ({ item, section: beatRunSectionForListItem(item) }))
      .sort((left, right) => {
        const sectionOrder = beatRunSectionOrder(left.section) - beatRunSectionOrder(right.section);
        if (sectionOrder !== 0) return sectionOrder;
        return beatDisplayTitle(left.item).localeCompare(beatDisplayTitle(right.item));
      })
      .map(({ item }) => item),
    [beats.data, employeeId],
  );
  useEffect(() => {
    if (employeeId) router.prefetch(scheduleCombinedVisitPath("outlet", { employeeId }));
  }, [employeeId, router]);
  if (isAdmin) return <CombinedVisitList />;
  if (!employeeId) {
    return (
      <ManagementScreen view="combined-visit-beat">
        <div className={styles.content}>
          <EmptyState icon="PersonRounded" title="Choose a sales person first" message="Pick the sales person you will accompany, then choose their beat." actionLabel="Choose sales person" onAction={() => router.replace(scheduleCombinedVisitPath("sales_person"))} />
        </div>
      </ManagementScreen>
    );
  }
  return (
    <ManagementScreen view="combined-visit-beat">
      <div className={styles.content}>
        <CombinedVisitProgress step={1} />
        {beats.isPending ? (
          <>
            <Skeleton height={72} radius={12} />
            <Skeleton height={72} radius={12} />
          </>
        ) : beats.isError ? (
          <ErrorState title="Beats unavailable" message="Approved beats could not be loaded." onRetry={() => { void beats.refetch(); }} />
        ) : employeeBeats.length ? (
          <div className={styles.card} style={{ padding: 0 }}>
            {employeeBeats.map((item) => (
              <DataRow
                key={item.id}
                icon="Calendar"
                title={beatDisplayTitle(item)}
                subtitle={beatDisplaySubtitle(item)}
                onClick={() => router.push(scheduleCombinedVisitPath("outlet", { employeeId, beatId: item.id }))}
              />
            ))}
          </div>
        ) : (
          <EmptyState icon="Calendar" title="No active approved beats" message="This sales person does not have an active approved beat in your scope." actionLabel="Choose another sales person" onAction={() => router.push(scheduleCombinedVisitPath("sales_person"))} />
        )}
      </div>
    </ManagementScreen>
  );
}

function CombinedVisitOutletPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAdmin } = useManagementRole();
  const employeeId = searchParams.get("employeeId") ?? "";
  const beatId = searchParams.get("beatId") ?? "";
  const beatDetail = useBeat(beatId);
  const outlets = beatDetail.data?.outlets ?? [];
  useEffect(() => {
    if (employeeId && beatId) router.prefetch(scheduleCombinedVisitPath("day", { employeeId, beatId }));
  }, [beatId, employeeId, router]);
  if (isAdmin) return <CombinedVisitList />;
  if (!employeeId || !beatId) {
    return (
      <ManagementScreen view="combined-visit-outlet">
        <div className={styles.content}>
          <EmptyState icon="Calendar" title="Choose a beat first" message="Pick a sales person and beat before choosing an outlet." actionLabel="Choose beat" onAction={() => router.replace(employeeId ? scheduleCombinedVisitPath("beat", { employeeId }) : scheduleCombinedVisitPath("sales_person"))} />
        </div>
      </ManagementScreen>
    );
  }
  return (
    <ManagementScreen view="combined-visit-outlet">
      <div className={styles.content}>
        <CombinedVisitProgress step={2} />
        {beatDetail.isPending ? (
          <>
            <Skeleton height={72} radius={12} />
            <Skeleton height={72} radius={12} />
          </>
        ) : beatDetail.isError ? (
          <ErrorState title="Beat details unavailable" message="Current outlets for this beat could not be loaded." onRetry={() => { void beatDetail.refetch(); }} />
        ) : outlets.length ? (
          <div className={styles.card} style={{ padding: 0 }}>
            {outlets.map((item) => {
              const subtitle = [item.locality, item.category ? shopCategoryLabel(item.category) : null].filter(Boolean).join(" · ");
              return (
                <DataRow
                  key={item.outlet_ref}
                  icon="LocationMarker"
                  title={item.name}
                  subtitle={subtitle || undefined}
                  onClick={() => router.push(scheduleCombinedVisitPath("day", { employeeId, beatId, outletRef: item.outlet_ref }))}
                />
              );
            })}
          </div>
        ) : (
          <EmptyState icon="LocationMarker" title="No current outlets" message="This beat has no selected outlets available for scheduling." actionLabel="Choose another beat" onAction={() => router.push(scheduleCombinedVisitPath("beat", { employeeId }))} />
        )}
      </div>
    </ManagementScreen>
  );
}

function CombinedVisitDayPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAdmin } = useManagementRole();
  const employeeId = searchParams.get("employeeId") ?? "";
  const beatId = searchParams.get("beatId") ?? "";
  const outletRef = searchParams.get("outletRef") ?? "";
  const [day, setDay] = useState("");
  const [error, setError] = useState<string | null>(null);
  const beatDetail = useBeat(beatId);
  const frequency = beatDetail.data?.frequency;
  const outletName = beatDetail.data?.outlets.find((item) => item.outlet_ref === outletRef)?.name;
  const mutations = useCombinedVisitMutations();
  const plannedDay = (iso: string) => isBeatPlannedOnDate(frequency, iso);
  if (isAdmin) return <CombinedVisitList />;
  if (!employeeId || !beatId || !outletRef) {
    return (
      <ManagementScreen view="combined-visit-day">
        <div className={styles.content}>
          <EmptyState icon="LocationMarker" title="Choose an outlet first" message="Pick a sales person, beat, and outlet before choosing the day." actionLabel="Choose outlet" onAction={() => router.replace(employeeId && beatId ? scheduleCombinedVisitPath("outlet", { employeeId, beatId }) : startCombinedVisitPath(employeeId || undefined))} />
        </div>
      </ManagementScreen>
    );
  }
  const schedule = async () => {
    setError(null);
    if (!plannedDay(day)) {
      setError("Choose a planned visit day for this beat.");
      return;
    }
    try {
      await mutations.create.mutateAsync({
        beat_id: beatId,
        outlet_ref: outletRef,
        sales_person_employee_id: employeeId,
        scheduled_business_date: day,
      });
      router.push("/mgmt/combined-visits");
    } catch (scheduleError) {
      setError(mutationErrorMessage(scheduleError));
    }
  };
  const scheduleLabel = mutations.create.isPending
    ? "Scheduling..."
    : outletName && day
      ? `Schedule tag-along · ${outletName} · ${formatDate(day)}`
      : "Schedule tag-along";
  return (
    <ManagementScreen
      view="combined-visit-day"
      footer={<Button variant="filled" color="primary" label={scheduleLabel} disabled={!outletName || !day || !plannedDay(day) || mutations.create.isPending} onClick={() => { void schedule(); }} />}
    >
      <div className={styles.content}>
        <CombinedVisitProgress step={3} />
        {error ? <Notice tone="warning">{error}</Notice> : null}
        {beatDetail.isPending ? (
          <Skeleton height={280} radius={12} />
        ) : beatDetail.isError ? (
          <ErrorState title="Beat details unavailable" message="Outlet details for this visit could not be loaded." onRetry={() => { void beatDetail.refetch(); }} />
        ) : !outletName ? (
          <EmptyState icon="LocationMarker" title="Outlet unavailable" message="This outlet is no longer on the selected beat." actionLabel="Choose outlet" onAction={() => router.replace(scheduleCombinedVisitPath("outlet", { employeeId, beatId }))} />
        ) : (
          <Section label={outletName}>
            <div className={styles.card}>
              {frequency ? <p className={styles.sectionLabel}>{beatFrequencyDisplay(frequency)}</p> : null}
              <DateField
                label="Visit day"
                dateValue={day}
                onChange={setDay}
                inline
                isDateEnabled={plannedDay}
              />
            </div>
          </Section>
        )}
      </div>
    </ManagementScreen>
  );
}

function VisitFeedback() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const combinedVisitId = searchParams.get("id") ?? "";
  const combinedVisit = useCombinedVisit(combinedVisitId);
  const savedFeedback = combinedVisit.data?.feedback;
  if (!combinedVisitId) {
    return <ManagementScreen view="visit-feedback"><div className={styles.content}><EmptyState icon="PersonRounded" title="No combined visit selected" message="Open a combined visit before submitting feedback." actionLabel="Combined visits" onAction={() => router.push("/mgmt/combined-visits")} /></div></ManagementScreen>;
  }
  if (combinedVisit.isPending) {
    return <ManagementScreen view="visit-feedback"><div className={styles.content}><Skeleton height={72} radius={12} /></div></ManagementScreen>;
  }
  if (combinedVisit.isError) {
    return <ManagementScreen view="visit-feedback"><div className={styles.content}><ErrorState title="Combined visit unavailable" message="The selected combined visit could not be loaded." onRetry={() => { void combinedVisit.refetch(); }} /></div></ManagementScreen>;
  }
  return <VisitFeedbackForm key={`${combinedVisitId}:${savedFeedback?.submitted_at ?? "new"}`} combinedVisitId={combinedVisitId} feedback={savedFeedback} />;
}

function VisitFeedbackForm({
  combinedVisitId,
  feedback,
}: {
  combinedVisitId: string;
  feedback?: CombinedVisitResponse["feedback"];
}) {
  const router = useRouter();
  const mutations = useCombinedVisitMutations();
  const [rating, setRating] = useState(feedback?.overall_rating === "needs_work" ? "poor" : feedback?.overall_rating ?? "good");
  const [wentWell, setWentWell] = useState(feedback?.responses?.went_well ?? "");
  const [coaching, setCoaching] = useState(feedback?.responses?.needs_coaching ?? feedback?.responses?.coaching ?? "");
  const [nextAction, setNextAction] = useState(feedback?.responses?.next_visit_action ?? feedback?.responses?.next_action ?? "");
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    try {
      await mutations.submitFeedback.mutateAsync({
        combinedVisitId,
        body: {
          overall_rating: rating === "poor" ? "needs_work" : rating as "good" | "average",
          responses: {
            went_well: wentWell,
            needs_coaching: coaching,
            next_visit_action: nextAction,
          },
        },
      });
      router.push("/mgmt/combined-visits");
    } catch (submitError) {
      setError(mutationErrorMessage(submitError));
    }
  };

  return (
    <ManagementScreen view="visit-feedback" footer={<Button variant="filled" color="primary" label={mutations.submitFeedback.isPending ? "Saving..." : feedback ? "Update feedback" : "Submit feedback"} disabled={mutations.submitFeedback.isPending} onClick={() => { void submit(); }} />}>
      <div className={styles.content}>
        {error ? <Notice tone="warning">{error}</Notice> : null}
        <Section label="Overall assessment">
          <RadioGroup value={rating} onChange={setRating} row options={[{ value: "good", label: "Good" }, { value: "average", label: "Average" }, { value: "poor", label: "Needs work" }]} />
        </Section>
        <Section label="Observations">
          <div className={styles.form}>
            <TextField label="What went well" placeholder="Summarize effective field behavior" multiline rows={2} value={wentWell} onChange={(event) => setWentWell((event.target as HTMLInputElement).value)} />
            <TextField label="What needs coaching" placeholder="Note coaching areas" multiline rows={2} value={coaching} onChange={(event) => setCoaching((event.target as HTMLInputElement).value)} />
            <TextField label="Action for next visit" placeholder="Optional" value={nextAction} onChange={(event) => setNextAction((event.target as HTMLInputElement).value)} />
          </div>
        </Section>
      </div>
    </ManagementScreen>
  );
}

const CALLS_METRICS = [
  ["sc", "SC", "Scheduled", "var(--color-primary)"],
  ["tc", "TC", "Total", "var(--color-info)"],
  ["pc", "PC", "Productive", "var(--color-success)"],
  ["utc", "UTC", "Unique outlets", "var(--color-text-secondary)"],
] as const;

function CallsMetricStrip({
  values,
  labels,
}: {
  values: CallsKpiTotalsOut;
  labels: "code" | "full";
}) {
  return (
    <div className={styles.callsStrip}>
      {CALLS_METRICS.map(([key, code, full, tone]) => (
        <div className={styles.callsStripCell} key={key}>
          <strong style={{ color: tone }}>{values[key]}</strong>
          <span>{labels === "code" ? code : full}</span>
        </div>
      ))}
    </div>
  );
}

function CoverageDrillRow({
  row,
  subtitle,
  onDuty,
  onClick,
}: {
  row: CallsKpiRowOut;
  subtitle: string;
  onDuty?: boolean;
  onClick?: () => void;
}) {
  const body = (
    <>
      <span className={styles.coverageRowHead}>
        <span className={styles.avatarWrap}>
          <span className={styles.avatar}>{initials(row.full_name)}</span>
          {onDuty !== undefined ? (
            <span className={onDuty ? styles.statusDot : `${styles.statusDot} ${styles.statusDotInactive}`} />
          ) : null}
        </span>
        <span className={styles.rowCopy}>
          <strong className="hb-heading">{row.full_name}</strong>
          <span>{subtitle}</span>
        </span>
        {onClick ? <Icon name="KeyboardArrowRight" size={20} color="var(--color-text-placeholder)" /> : null}
      </span>
      <CallsMetricStrip values={row} labels="code" />
    </>
  );
  return onClick ? (
    <button type="button" className={`${styles.coverageRow} ${styles.coverageRowTappable}`} onClick={onClick}>
      {body}
    </button>
  ) : (
    <div className={styles.coverageRow}>{body}</div>
  );
}

function coverageHref(businessDate: string, drillPath: string[]) {
  const query = new URLSearchParams({ date: businessDate });
  if (drillPath.length) query.set("path", drillPath.join(","));
  return `/mgmt/coverage?${query.toString()}`;
}

function Coverage() {
  const router = useRouter();
  const { isAdmin } = useManagementRole();
  const searchParams = useSearchParams();
  const requestedDate = searchParams.get("date");
  const businessDate = isIsoBusinessDate(requestedDate) ? requestedDate : istDateISO();
  const drillPath = useMemo(
    () => (searchParams.get("path") ?? "").split(",").filter(Boolean),
    [searchParams],
  );
  const forEmployeeId = drillPath.at(-1) ?? null;
  const parentHref = coverageHref(businessDate, drillPath.slice(0, -1));

  const scopePath: CallsKpiScope = isAdmin ? "org" : "team";
  const calls = useCallsKpis(scopePath, { businessDate, forEmployeeId });
  const coverage = useTeamCoverage({ businessDate, onlySalesPerson: true });
  const coverageByEmployee = useMemo(() => {
    const map = new Map<string, CoverageRow>();
    for (const item of coverage.data?.items ?? []) map.set(item.employee_id, item);
    return map;
  }, [coverage.data?.items]);

  const node = calls.data?.view.root;
  const rows = calls.data?.today.items ?? [];
  const totals = calls.data?.today.totals;

  const rowSubtitle = (row: CallsKpiRowOut) => {
    const designation = designationLabel(row.designation_code);
    if (row.status !== "active") {
      return `${designation} · Deactivated · ${row.direct_reportee_count} active below`;
    }
    if (row.role_code === "sales_person") {
      const live = coverageByEmployee.get(row.employee_id);
      if (!live) return designation;
      return `${designation} · ${live.punched_in_at ? `In ${formatDateTime(live.punched_in_at)}` : live.on_duty ? "On duty" : "No punch-in"}`;
    }
    if (row.direct_reportee_count === 0) return `${designation} · No reportees`;
    return `${designation} · ${row.direct_reportee_count} reportee${row.direct_reportee_count === 1 ? "" : "s"}`;
  };

  const rowAction = (row: CallsKpiRowOut) => {
    if (row.role_code === "sales_person") {
      return () => router.push(
        `/mgmt/team-day?id=${encodeURIComponent(row.employee_id)}&name=${encodeURIComponent(row.full_name)}&date=${encodeURIComponent(businessDate)}`,
      );
    }
    if (row.direct_reportee_count === 0) return undefined;
    return () => router.push(coverageHref(businessDate, [...drillPath, row.employee_id]));
  };

  return (
    <ManagementScreen
      view="coverage"
      title="Team coverage"
      onBack={drillPath.length ? () => router.push(parentHref) : undefined}
    >
      <div className={styles.content}>
        <div className={styles.coverageFilterRow}>
          {node && drillPath.length ? (
            <div className={styles.coverageFocusInline}>
              <span className={`${styles.avatar} ${styles.coverageFocusAvatar}`}>{initials(node.full_name)}</span>
              <span className={styles.coverageFocusCopy}>
                <strong className="hb-heading">{node.full_name}</strong>
                <span className={styles.coverageFocusDesignation}>{designationLabel(node.designation_code)}</span>
              </span>
            </div>
          ) : (
            <p className={`${styles.coverageScopeLabel} hb-heading`}>
              {isAdmin ? "Organization" : "My team"}
            </p>
          )}
          <DateField
            label="Business date"
            style={{ flex: "0 0 auto" }}
            value={formatBusinessDateShort(businessDate)}
            dateValue={businessDate}
            onChange={(value) => router.replace(coverageHref(value, drillPath))}
            compact
          />
        </div>
        {calls.isPending ? (
          <>
            <Skeleton height={92} radius={12} />
            <Skeleton height={104} radius={12} />
            <Skeleton height={104} radius={12} />
          </>
        ) : calls.isError ? (
          <ErrorState title="Coverage unavailable" message="Team coverage could not be loaded." onRetry={() => void calls.refetch()} />
        ) : (
          <>
            {totals ? (
              <div className={styles.coverageNodeCard}>
                <CallsMetricStrip values={totals} labels="full" />
              </div>
            ) : null}
            <Section label={rows.length ? `${rows.length} direct reportee${rows.length === 1 ? "" : "s"}` : "Direct reportees"}>
              <div className={styles.card} style={{ padding: 0 }}>
                {rows.length ? rows.map((row) => (
                  <CoverageDrillRow
                    key={row.employee_id}
                    row={row}
                    subtitle={rowSubtitle(row)}
                    onDuty={coverageByEmployee.get(row.employee_id)?.on_duty}
                    onClick={rowAction(row)}
                  />
                )) : drillPath.length ? (
                  <EmptyState
                    icon="PersonRounded"
                    title="No reportees"
                    message="This employee has no active reportees to drill into."
                    actionLabel="Back"
                    onAction={() => router.push(parentHref)}
                  />
                ) : (
                  <EmptyState
                    icon="LocationMarker"
                    title="No team in scope"
                    message="Coverage appears once active employees report into your scope."
                  />
                )}
              </div>
            </Section>
          </>
        )}
      </div>
    </ManagementScreen>
  );
}

function Attendance() {
  const { isAdmin } = useManagementRole();
  const [businessDate, setBusinessDate] = useState(() => istDateISO());
  const attendance = useTeamAttendanceList(businessDate);
  const rows = attendance.data?.items ?? [];
  return (
    <ManagementScreen view="attendance">
      <div className={styles.content}>
        <div className={`${styles.teamTop} ${styles.attendanceExportTop}`}>
          <div className={styles.attendanceExportDateField}>
            <DateField label="Business date" value={formatBusinessDate(businessDate)} dateValue={businessDate} onChange={setBusinessDate} />
          </div>
        </div>
        {attendance.isPending ? (
          <>
            <Skeleton height={92} radius={12} />
            <Skeleton height={72} radius={12} />
            <Skeleton height={72} radius={12} />
          </>
        ) : attendance.isError ? (
          <ErrorState title="Attendance unavailable" message="Team attendance could not be loaded." onRetry={() => { void attendance.refetch(); }} />
        ) : (
          <>
            <SummaryGrid items={[
              [`${attendance.data?.on_duty_count ?? 0}/${attendance.data?.total ?? 0}`, "On duty", "var(--color-success)"],
              [String(attendance.data?.no_punch_in_count ?? 0), "No punch-in", "var(--color-warning)"],
              [String(attendance.data?.after_9am_count ?? 0), "Late", "var(--color-primary)"],
            ]} />
            {rows.length ? (
              <div className={styles.card} style={{ padding: 0 }}>
                {rows.map((row: TeamAttendanceRow) => <DataRow key={row.employee_id} initials={initials(row.employee_name)} title={row.employee_name} subtitle={row.punched_in_at ? `In ${formatDateTime(row.punched_in_at)}${row.punch_in_address ? ` · ${row.punch_in_address}` : ""}` : "No punch-in"} trailing={<StatusChip status={row.on_duty ? "verified" : row.is_late ? "pending" : "default"} label={row.on_duty ? "On duty" : row.is_late ? "Late" : "No punch-in"} type="outlined" />} />)}
              </div>
            ) : (
              <EmptyState icon="Schedule" title="No attendance rows" message="No scoped attendance records were returned for this business date." />
            )}
          </>
        )}
      </div>
    </ManagementScreen>
  );
}

function ScopedOrder() {
  const router = useRouter();
  const { isAdmin } = useManagementRole();
  const searchParams = useSearchParams();
  const requested = searchParams.get("id") ?? "";
  const order = useOrder(requested);
  const retry = useRetryOrder(requested);
  const footer = isAdmin
    ? <Button variant="outlined" color="neutral" label="Back to orders" onClick={() => router.push("/mgmt/dashboard-drill")} />
    : undefined;
  if (!requested) {
    return <ManagementScreen view="order"><EmptyState icon="ShoppingCartOutlined" title="No order selected" message="Open an order from the scoped order list." actionLabel="Orders" onAction={() => router.push("/mgmt/dashboard-drill")} /></ManagementScreen>;
  }
  if (order.isPending || order.isError || !order.data) {
    return <ManagementScreen view="order"><div className={styles.content}>{order.isPending ? <Skeleton height={160} radius={12} /> : <ErrorState title="Order unavailable" message="This order could not be loaded." onRetry={() => { void order.refetch(); }} />}</div></ManagementScreen>;
  }
  const value: OrderDetailOut = order.data;
  const canRetry = value.retry_budget_remaining > 0 && value.status.includes("failed");
  const pricedLines = value.lines.filter((line) => line.unit_price_net_paise != null);
  const quantityOnlyLines = value.lines.filter((line) => line.unit_price_net_paise == null);
  const pricedSummaryLines = pricedLines.map(mapOrderDetailSummaryLine);
  const quantityOnlySummaryLines = quantityOnlyLines.map(mapOrderDetailSummaryLine);
  const totalItemCount = value.lines.reduce(
    (total, line) => total + (line.approved_qty ?? line.requested_qty),
    0,
  );
  return (
    <ManagementScreen view="order" title={value.order_number} footer={footer}>
      <div className={styles.content}>
        <div className={styles.card}>
          <div className={styles.teamTop}>
            <span className={styles.rowCopy}><strong>{value.outlet_name}</strong><span>{value.counterparty_name} · {value.order_path === "po_backed" ? "PO-backed" : "Direct"}</span></span>
            <StatusChip status={statusTone(value.status)} label={humanLabel(value.status)} type="filled" />
          </div>
          <strong className="sp-metric-value sp-metric-value--h1" style={{ color: "var(--color-primary)", marginTop: 12 }}>{moneyFromPaise(value.gross_total_paise)}</strong>
        </div>
        <OrderSummarySections
          pricedLines={pricedSummaryLines}
          quantityOnlyLines={quantityOnlySummaryLines}
          schemeLabel={value.scheme_label}
          priceSummary={pricedLines.length ? {
            itemCount: totalItemCount,
            subtotalPaise: value.subtotal_net_paise,
            productDiscountPaise: value.product_discount_paise ?? undefined,
            schemeDiscountPaise: value.scheme_discount_paise,
            gstPaise: value.gst_amount_paise,
            totalPaise: value.gross_total_paise,
          } : null}
        />
        <Notice>{value.downstream_dp_order_ref ? `Registered in Humbee as ${value.downstream_dp_order_ref}.` : "This screen stops at SFA capture and Humbee registration evidence. Fulfilment, invoice, dispatch, delivery, return, and payment are outside this boundary."}</Notice>
        {canRetry ? <Button variant="outlined" color="primary" label={retry.isPending ? "Retrying..." : "Retry registration"} disabled={retry.isPending} onClick={() => { void retry.mutateAsync(newMutationKey()); }} /> : null}
      </div>
    </ManagementScreen>
  );
}

function TeamLeave() {
  const router = useRouter();
  const { isAdmin } = useManagementRole();
  const actorId = useManagementActorId();
  const [filter, setFilter] = useState<"all" | "pending" | "approved" | "auto_approved" | "rejected">("all");
  const leave = useTeamLeave(filter);
  const rows = leave.data?.pages.flatMap((page) => page.items) ?? [];
  const listRef = useInfiniteScrollTrigger<HTMLDivElement>({
    hasNextPage: leave.hasNextPage,
    isFetchingNextPage: leave.isFetchingNextPage,
    fetchNextPage: leave.fetchNextPage,
  });
  const filters: Array<[typeof filter, string]> = [["all", "All"], ["pending", "Pending"], ["approved", "Approved"], ["auto_approved", "Auto-approved"], ["rejected", "Rejected"]];
  return (
    <ManagementScreen view="leave">
      <div className={styles.filterBar}>{filters.map(([value, label]) => <button data-active={filter === value} key={value} onClick={() => setFilter(value)} type="button">{label}</button>)}</div>
      <div className={styles.content}>
        <Notice>Employee, leave-type, and date filters remain unavailable because the released team-leave endpoint only supports status.</Notice>
        {leave.isPending ? (
          <>
            <Skeleton height={72} radius={12} />
            <Skeleton height={72} radius={12} />
          </>
        ) : leave.isError ? (
          <ErrorState title="Team leave unavailable" message="Scoped leave requests could not be loaded." onRetry={() => { void leave.refetch(); }} />
        ) : rows.length ? (
          <div className={styles.card} style={{ padding: 0 }} ref={listRef}>
            {rows.map((row) => (
              <DataRow
                key={row.id}
                initials={initials(row.employee_name)}
                title={row.employee_name}
                subtitle={`${leaveTypeLabel(row.leave_type)} · ${formatDate(row.from_date)} to ${formatDate(row.to_date)} · ${leaveDayLabel(row.day_count)}${leaveRoutingSuffix(row.status)}`}
                trailing={<StatusChip status={statusTone(row.status)} label={leaveStatusLabel(row.status)} type="outlined" />}
                onClick={
                  !isAdmin && row.employee_id === actorId
                    ? () => router.push(`/mgmt/leave-detail?id=${encodeURIComponent(row.id)}&approvalId=${encodeURIComponent(row.approval_request_id)}`)
                    : row.status === "pending"
                      ? () => router.push(`/mgmt/approval-detail?id=${encodeURIComponent(row.approval_request_id)}`)
                      : undefined
                }
              />
            ))}
          </div>
        ) : (
          <EmptyState icon="Calendar" title="No leave records" message="No leave requests match this filter." actionLabel={filter === "all" ? undefined : "Show all"} onAction={filter === "all" ? undefined : () => setFilter("all")} />
        )}
      </div>
    </ManagementScreen>
  );
}

function managementLeavePaths(toRolePath: (href: string) => string): LeaveJourneyPaths {
  return {
    home: toRolePath("/mgmt/my-leave"),
    apply: toRolePath("/mgmt/leave-apply"),
    detail: (id, approvalId) => toRolePath(`/mgmt/leave-detail?id=${encodeURIComponent(id)}&approvalId=${encodeURIComponent(approvalId)}`),
  };
}

function ManagementLeaveShell({
  view,
  title,
  children,
  footer,
  bottomAction,
  offline,
}: LeaveShellProps & { view: "my-leave" | "leave-apply" | "leave-detail" }) {
  const router = useRouter();
  return (
    <ManagementScreen
      view={view}
      title={title}
      offline={offline}
      footer={
        footer ?? (bottomAction ? (
          <Button
            variant="filled"
            color="primary"
            label="Apply leave"
            leftIcon={<Icon name="Add" size={18} color="currentColor" />}
            onClick={() => router.push("/mgmt/leave-apply")}
          />
        ) : undefined)
      }
    >
      {children}
    </ManagementScreen>
  );
}

function MyLeave() {
  const toRolePath = useManagementPath();
  return (
    <LeaveStatusScreen
      paths={managementLeavePaths(toRolePath)}
      renderShell={(props) => <ManagementLeaveShell view="my-leave" {...props} />}
    />
  );
}

function ApplyOwnLeave() {
  const toRolePath = useManagementPath();
  return (
    <ApplyLeaveScreen
      paths={managementLeavePaths(toRolePath)}
      renderShell={(props) => <ManagementLeaveShell view="leave-apply" {...props} />}
    />
  );
}

function OwnLeaveDetail() {
  const toRolePath = useManagementPath();
  return (
    <LeaveDetailScreen
      paths={managementLeavePaths(toRolePath)}
      renderShell={(props) => <ManagementLeaveShell view="leave-detail" {...props} />}
    />
  );
}

function Beats() {
  const { isAdmin } = useManagementRole();
  const list = useBeats("all");
  const mutations = useBeatMutations();
  const [creating, setCreating] = useState(false);
  const [createBeatId, setCreateBeatId] = useState("");
  const [viewing, setViewing] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const geography = useGeographyMaster(creating || Boolean(editing));
  const assignedScope = useGeographyScope(ownerId || null);
  const salesPeople = useEmployees({ role: "sales_person", status: "active" });
  const salespersonOptions = useMemo(
    () => (salesPeople.data?.items ?? [])
      .filter(employeeStatusActive)
      .map((employee) => ({ value: employee.id, label: `${employee.full_name} (${employee.employee_code})` })),
    [salesPeople.data],
  );
  const [frequency, setFrequency] = useState<ManagementBeatFrequency>("daily");
  const [days, setDays] = useState<number[]>([]);
  const [weeks, setWeeks] = useState<number[]>([]);
  const [zones, setZones] = useState<string[]>([]);
  const [states, setStates] = useState<string[]>([]);
  const [districts, setDistricts] = useState<string[]>([]);
  const [categories, setCategories] = useState<ShopCategory[]>([]);
  const [outletIds, setOutletIds] = useState<string[]>([]);
  const [createOutletQuery, setCreateOutletQuery] = useState("");
  const [viewOutletQuery, setViewOutletQuery] = useState("");
  const [editOutletQuery, setEditOutletQuery] = useState("");
  const [showAvailableOutlets, setShowAvailableOutlets] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rows = useMemo(() => visibleAdminBeatRows(list.data?.items ?? []), [list.data?.items]);
  const nonDraftRows = useMemo(() => rows.filter((row) => row.lifecycle_state !== "draft"), [rows]);
  const draftRows = useMemo(() => rows.filter((row) => row.lifecycle_state === "draft"), [rows]);
  const unsavedOutletScope = useMemo(() => ({ districts, categories }), [districts, categories]);
  const scopeOutlets = useScopeOutlets(createBeatId, "", Boolean(createBeatId && districts.length), "create", unsavedOutletScope);
  const activeBeatId = editing ?? viewing ?? "";
  const beatDetail = useBeatDetail(activeBeatId, { enabled: Boolean(activeBeatId), pendingEdit: Boolean(editing) });
  const editScopeOutlets = useScopeOutlets(editing ?? "", "", Boolean(editing && districts.length), "editing", unsavedOutletScope);
  const outletChoices = useMemo(() => (scopeOutlets.data ?? []).map(mapOutlet), [scopeOutlets.data]);
  const sortedCreateOutlets = useMemo(() => sortOutletsTakenLast(outletChoices, "location_then_name"), [outletChoices]);
  const visibleCreateOutlets = useMemo(() => filterOutletsByQuery(sortedCreateOutlets, createOutletQuery), [createOutletQuery, sortedCreateOutlets]);
  const createScopeComplete = Boolean(createBeatId && districts.length) && scopeOutletsComplete(scopeOutlets);
  const createOutletIds = createScopeComplete ? selectableOutletIds(outletIds, outletChoices) : outletIds;
  const viewingDetail = useMemo(
    () => (viewing ? beatDetail.detail : null),
    [beatDetail.detail, viewing],
  );
  const sortedViewOutlets = useMemo(
    () => sortOutletsTakenLast(
      (viewingDetail?.outlets ?? []).map((outlet) => ({
        id: outlet.outlet_ref,
        name: outlet.name,
        location: outlet.locality?.trim() || "",
        category: outlet.category ? shopCategoryLabel(outlet.category) : "",
      })),
      "location_then_name",
    ),
    [viewingDetail?.outlets],
  );
  const visibleViewOutlets = useMemo(
    () => filterOutletsByQuery(sortedViewOutlets, viewOutletQuery),
    [sortedViewOutlets, viewOutletQuery],
  );
  const editingDetail = useMemo(
    () => (editing ? beatDetail.detail : null),
    [beatDetail.detail, editing],
  );
  const fallbackEditOutlets = useMemo<OutletChoice[]>(
    () => (editingDetail?.outlets ?? []).map((outlet) => ({
      id: outlet.outlet_ref,
      name: outlet.name,
      zone: "",
      state: "",
      district: "",
      location: outlet.locality?.trim() || "",
      category: outlet.category ? shopCategoryLabel(outlet.category) : "",
      selected: true,
    })),
    [editingDetail?.outlets],
  );
  const editScopeComplete = Boolean(editing && districts.length && scopeOutletsComplete(editScopeOutlets));
  const editOutletChoices = useMemo<OutletChoice[]>(
    () => (editScopeComplete ? editScopeOutlets.data?.map(mapOutlet) ?? [] : fallbackEditOutlets),
    [editScopeComplete, editScopeOutlets.data, fallbackEditOutlets],
  );
  const sortedEditOutlets = useMemo(
    () => sortOutletsTakenLast(editOutletChoices, "location_then_name"),
    [editOutletChoices],
  );
  const filteredEditOutlets = useMemo(
    () => filterOutletsByQuery(sortedEditOutlets, editOutletQuery),
    [editOutletQuery, sortedEditOutlets],
  );
  const editOutletIds = editScopeComplete ? selectableOutletIds(outletIds, editOutletChoices) : outletIds;
  const droppedEditOutletCount = outletIds.length - editOutletIds.length;
  const visibleEditOutlets = showAvailableOutlets
    ? filteredEditOutlets
    : filteredEditOutlets.filter((outlet) => editOutletIds.includes(outlet.id));
  const { current: approvedBeat, draft: pendingBeat } = beatDetail;
  const editingGeoScopes = useMemo(
    () => editing ? [approvedBeat?.geo_scope, pendingBeat?.geo_scope].filter((geoScope) => geoScope !== undefined) : [],
    [approvedBeat, pendingBeat, editing],
  );
  const geographyOptions = useMemo(
    () => geography.data && assignedScope.data ? beatScopeOptions(geography.data, assignedScope.data, editingGeoScopes) : null,
    [geography.data, assignedScope.data, editingGeoScopes],
  );
  const pending = mutations.create.isPending
    || mutations.saveDraft.isPending
    || mutations.replaceOutlets.isPending
    || mutations.submit.isPending
    || mutations.adminUpdate.isPending
    || mutations.deactivate.isPending
    || mutations.reactivate.isPending;

  const resetForm = () => {
    setCreating(false);
    setCreateBeatId("");
    setViewing(null);
    setEditing(null);
    setName("");
    setOwnerId("");
    setFrequency("daily");
    setDays([]);
    setWeeks([]);
    setZones([]);
    setStates([]);
    setDistricts([]);
    setCategories([]);
    setOutletIds([]);
    setCreateOutletQuery("");
    setViewOutletQuery("");
    setEditOutletQuery("");
    setShowAvailableOutlets(false);
    setError(null);
  };

  const startCreate = () => {
    resetForm();
    setCreating(true);
  };

  const confirmCreateOwner = () => {
    if (!ownerId) return;
    setError(null);
    mutations.create.mutate({ ownerEmployeeId: ownerId }, {
      onError: (createError) => setError(mutationErrorMessage(createError)),
      onSuccess: (beat) => setCreateBeatId(beat.id),
    });
  };

  const applyCreateScope = (value: GeoScopeSelection) => {
    setZones(value.zones);
    setStates(value.states);
    setDistricts(value.districts);
    setCategories(asShopCategories(value.shopCategories));
  };

  const setFormFrequency = (nextFrequency: ManagementBeatFrequency) => {
    setFrequency(nextFrequency);
    if (nextFrequency === "daily") {
      setDays([]);
      setWeeks([]);
    }
  };

  const submitCreate = async () => {
    if (!createBeatId || !createScopeComplete) return;
    const outletRefs = createOutletIds;
    setError(null);
    try {
      await mutations.saveDraft.mutateAsync({
        beatId: createBeatId,
        displayName: name.trim(),
        code: name.trim(),
        geoScope: { zones, states, districts, cats: categories },
        frequency: { frequency, visit_days: days, week_cycle: weeks },
      });
      await mutations.replaceOutlets.mutateAsync({ beatId: createBeatId, outletRefs });
      await mutations.submit.mutateAsync(createBeatId);
      resetForm();
    } catch (createError) {
      setError(mutationErrorMessage(createError));
    }
  };

  const save = async (outletRefs: string[]) => {
    if (!editing) return;
    setError(null);
    try {
      await mutations.adminUpdate.mutateAsync({
        beatId: editing,
        body: {
          display_name: name.trim() || undefined,
          owner_employee_id: ownerId.trim() || undefined,
          geo_scope: { zones, states, districts, cats: categories },
          frequency: { frequency, visit_days: days, week_cycle: weeks },
          outlet_refs: outletRefs,
        },
      });
      resetForm();
    } catch (saveError) {
      setError(mutationErrorMessage(saveError));
    }
  };

  const toggleOutlet = (outlet: OutletChoice) => {
    if (outlet.takenBy) return;
    setOutletIds((current) => current.includes(outlet.id) ? current.filter((id) => id !== outlet.id) : [...current, outlet.id]);
  };

  const startEdit = () => {
    if (!viewing) return;
    setError(null);
    setEditOutletQuery("");
    setEditing(viewing);
    setViewing(null);
    setShowAvailableOutlets(false);
  };

  useEffect(() => {
    if (!editing) return;
    const source = beatDetail.detail;
    if (!source) return;
    const beat = mapBeat(source);
    queueMicrotask(() => {
      setName(beat.name);
      setOwnerId(source.owner_employee_id);
      setZones(beat.zones);
      setStates(beat.states);
      setDistricts(beat.districts);
      setCategories(asShopCategories(beat.categories));
      setFrequency(beat.frequencyPlan.cadence);
      setDays(beat.frequencyPlan.days);
      setWeeks(beat.frequencyPlan.weeks);
      setOutletIds(beat.outletIds);
      setEditOutletQuery("");
      setShowAvailableOutlets(false);
    });
  }, [beatDetail.detail, editing]);

  if (creating) {
    if (!createBeatId) {
      return (
        <ManagementScreen view="beats" title="Create beat" footer={<><Button variant="outlined" color="neutral" label="Cancel" disabled={mutations.create.isPending} onClick={resetForm} /><Button variant="filled" color="primary" label="Continue" disabled={!ownerId || mutations.create.isPending} onClick={confirmCreateOwner} /></>}>
          <div className={styles.content}>
            {error ? <Notice tone="error">{error}</Notice> : null}
            {salesPeople.isPending ? (
              <Skeleton height={72} radius={12} />
            ) : salesPeople.isError ? (
              <ErrorState title="Sales people unavailable" message="The salesperson list could not be loaded." onRetry={() => { void salesPeople.refetch(); }} />
            ) : (
              <Select label="Salesperson" fullWidth value={ownerId} onChange={setOwnerId} options={salespersonOptions} />
            )}
            <Notice>Choose the salesperson this beat belongs to. Their assigned zones, states, and districts will filter the geography scope.</Notice>
          </div>
        </ManagementScreen>
      );
    }
    const canSubmit = Boolean(name.trim() && zones.length && states.length && districts.length && createScopeComplete && createOutletIds.length && hasBeatFrequencyDetails(frequency, days, weeks));
    const droppedCreateOutletCount = outletIds.length - createOutletIds.length;
    return (
      <ManagementScreen view="beats" title="Create beat" footer={<><Button variant="outlined" color="neutral" label="Cancel" disabled={pending} onClick={resetForm} /><Button variant="filled" color="primary" label="Create beat" disabled={!canSubmit || pending} onClick={() => { void submitCreate(); }} /></>}>
        <div className={styles.content}>
          {error ? <Notice tone="error">{error}</Notice> : null}
          {geography.isPending || assignedScope.isPending ? (
            <Skeleton height={320} radius={12} />
          ) : geography.isError || assignedScope.isError || !geographyOptions ? (
            <ErrorState title="Geography unavailable" message="Beat scope could not be loaded." onRetry={() => { void geography.refetch(); void assignedScope.refetch(); }} />
          ) : (
            <>
              <TextField label="Beat name" value={name} onChange={(event) => setName((event.target as HTMLInputElement).value)} helperText="This beat goes live immediately, without a separate approval." required />
              <Section label="Geography scope">
                <GeoScopePicker
                  zones={geographyOptions.zones}
                  states={geographyOptions.states}
                  districts={geographyOptions.districts}
                  shopCategories={geographyOptions.categories}
                  assigned={{ zones: geographyOptions.pool.zones, states: geographyOptions.pool.states, districts: geographyOptions.pool.districts, shopCategories: geographyOptions.pool.categories }}
                  value={{ zones, states, districts, shopCategories: categories }}
                  onChange={applyCreateScope}
                />
              </Section>
              <ManagementBeatFrequencyFields frequency={frequency} days={days} weeks={weeks} onFrequencyChange={setFormFrequency} onDaysChange={setDays} onWeeksChange={setWeeks} />
              <Section label={`Outlets in this beat · ${createOutletIds.length}`}>
                {droppedCreateOutletCount > 0 ? <Notice tone="warning">{droppedOutletsNotice(droppedCreateOutletCount)}</Notice> : null}
                {!districts.length ? (
                  <Notice>Select geography scope before choosing outlets.</Notice>
                ) : scopeOutlets.isError ? (
                  <ErrorState title="Outlets unavailable" message={scopeOutlets.error instanceof ApiClientError ? scopeOutlets.error.message : "Outlet choices could not be loaded for this scope."} onRetry={() => { void scopeOutlets.refetch(); }} />
                ) : !createScopeComplete ? (
                  <Skeleton height={160} radius={12} />
                ) : (
                  <>
                    <div className="sp-search-toolbar">
                      <TextField
                        placeholder="Search outlets"
                        startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
                        value={createOutletQuery}
                        onChange={(event) => setCreateOutletQuery((event.target as HTMLInputElement).value)}
                      />
                    </div>
                    {!sortedCreateOutlets.length ? (
                      <EmptyState icon="LocationMarker" title="No outlets" message="No outlets are available for the selected scope." />
                    ) : visibleCreateOutlets.length ? (
                      <div className={styles.card} style={{ padding: 0 }}>
                        {visibleCreateOutlets.map((outlet) => (
                          <ListRow
                            key={outlet.id}
                            leading={<Checkbox checked={createOutletIds.includes(outlet.id)} disabled={Boolean(outlet.takenBy)} onChange={(event) => { event.stopPropagation(); toggleOutlet(outlet); }} />}
                            title={outlet.name}
                            subtitle={outlet.takenBy ? `Already on beat ${outlet.takenBy}` : outlet.location || undefined}
                            meta={outlet.category || undefined}
                            disabled={Boolean(outlet.takenBy)}
                            onClick={outlet.takenBy ? undefined : () => toggleOutlet(outlet)}
                          />
                        ))}
                      </div>
                    ) : (
                      <EmptyState icon="SearchOutlined" title={`No outlets match "${createOutletQuery}"`} message="Try another outlet name." actionLabel="Clear search" onAction={() => setCreateOutletQuery("")} />
                    )}
                  </>
                )}
              </Section>
            </>
          )}
        </div>
      </ManagementScreen>
    );
  }

  if (viewing) {
    const row = rows.find((item) => item.id === viewing);
    const detail = viewingDetail;
    const canEdit = isAdmin || row?.activation_state === "active";
    if (beatDetail.isPending) {
      return (
        <ManagementScreen
          view="beats"
          title="Beat details"
          footer={<Button variant="outlined" color="neutral" label="Back" onClick={resetForm} />}
        >
          <div className={styles.content}>
            <Skeleton height={320} radius={12} />
          </div>
        </ManagementScreen>
      );
    }
    if (beatDetail.isError || !detail) {
      return (
        <ManagementScreen
          view="beats"
          title="Beat details"
          footer={<Button variant="outlined" color="neutral" label="Back" onClick={resetForm} />}
        >
          <div className={styles.content}>
            <ErrorState
              title="Beat details unavailable"
              message="Beat information could not be loaded."
              onRetry={() => { void beatDetail.refetch(); }}
            />
          </div>
        </ManagementScreen>
      );
    }
    const zones = beatStringArray(detail.geo_scope, "zones");
    const states = beatStringArray(detail.geo_scope, "states");
    const districts = beatStringArray(detail.geo_scope, "districts");
    const categories = beatStringArray(detail.geo_scope, "cats");
    return (
      <ManagementScreen
        view="beats"
        title="Beat details"
        footer={
          <>
            <Button variant="outlined" color="neutral" label="Back" onClick={resetForm} />
            {canEdit ? <Button variant="filled" color="primary" label="Edit beat" onClick={startEdit} /> : null}
          </>
        }
      >
        <div className={styles.content}>
          {row ? <div className={styles.card}><div className={styles.teamTop}><span className={styles.rowCopy}><strong>{beatDisplayTitle(row)}</strong><span>{beatDisplaySubtitle(row)}</span><span>Activation: {humanLabel(row.activation_state)}</span></span><StatusChip status={statusTone(row.lifecycle_state)} label={humanLabel(row.lifecycle_state)} type="outlined" /></div></div> : null}
          <Section label="Beat details">
            <div className={styles.card} style={{ padding: 0 }}>
              <EmployeeDetailRow label="Frequency" value={beatFrequencyDisplay(detail.frequency)} />
              <EmployeeDetailRow label="Outlets" value={outletCountLabel(detail.outlet_count)} />
            </div>
          </Section>
          <Section label="Geography scope">
            <div className={styles.card} style={{ padding: 0 }}>
              <EmployeeDetailRow expandable label="Zones" value={beatGeoLabels(detail.geo_scope, "zones", zones)} />
              <EmployeeDetailRow expandable label="States" value={beatGeoLabels(detail.geo_scope, "states", states)} />
              <EmployeeDetailRow expandable label="Districts" value={beatGeoLabels(detail.geo_scope, "districts", districts)} />
              <EmployeeDetailRow expandable label="Shop categories" value={categoryLabels(categories)} />
            </div>
          </Section>
          <Section label={`Outlets in this beat · ${detail.outlets.length}`}>
            {sortedViewOutlets.length ? (
              <>
                <div className="sp-search-toolbar">
                  <TextField
                    placeholder="Search outlets"
                    startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
                    value={viewOutletQuery}
                    onChange={(event) => setViewOutletQuery((event.target as HTMLInputElement).value)}
                  />
                </div>
                {visibleViewOutlets.length ? (
                  <div className={styles.card} style={{ padding: 0 }}>
                    {visibleViewOutlets.map((outlet) => (
                      <ListRow
                        key={outlet.id}
                        leading={<Icon name="LocationMarker" size={22} color="var(--color-primary)" />}
                        title={outlet.name}
                        subtitle={outlet.location || undefined}
                        meta={outlet.category || undefined}
                      />
                    ))}
                  </div>
                ) : (
                  <EmptyState icon="SearchOutlined" title={`No outlets match "${viewOutletQuery}"`} message="Try another outlet name." actionLabel="Clear search" onAction={() => setViewOutletQuery("")} />
                )}
              </>
            ) : (
              <EmptyState icon="LocationMarker" title="No outlets" message="No outlets are linked to this beat." />
            )}
          </Section>
        </div>
      </ManagementScreen>
    );
  }

  if (editing) {
    const row = rows.find((item) => item.id === editing);
    const editDetail = editingDetail;
    const editBeat = editDetail ? mapBeat(editDetail) : null;
    const active = row?.activation_state === "active";
    const pendingApproval = row?.lifecycle_state === "pending_approval";
    // Admin and Manager share the same direct-edit-and-auto-approve form now (R-BEAT-17-style):
    // Manager is scoped to beats owned by Sales Persons in their own tree by `_load`'s server-side
    // OWN_TREE filter, same as every other beat read/write here. Deactivate/reactivate and owner
    // reassignment stay Admin-only.
    const detailsLoading = beatDetail.isPending || geography.isPending || assignedScope.isPending || (isAdmin && salesPeople.isPending);
    const detailsUnavailable =
      beatDetail.isError
      || geography.isError
      || assignedScope.isError
      || (isAdmin && salesPeople.isError)
      || !editBeat
      || !geographyOptions;
    const setEditOwner = (nextOwnerId: string) => {
      if (nextOwnerId === ownerId) return;
      setOwnerId(nextOwnerId);
      setZones([]);
      setStates([]);
      setDistricts([]);
      setCategories([]);
    };
    return (
      <ManagementScreen
        view="beats"
        title="Edit beat"
        footer={<>
          {isAdmin ? <Button variant="outlined" color={active ? "error" : "success"} label={active ? "Deactivate" : "Reactivate"} disabled={pending || pendingApproval || detailsLoading} onClick={() => { void (active ? mutations.deactivate.mutateAsync(editing) : mutations.reactivate.mutateAsync(editing)).then(resetForm).catch((mutationError) => setError(mutationErrorMessage(mutationError))); }} /> : null}
          <Button variant="filled" color="primary" label={pendingApproval ? "Save and activate" : "Save changes"} disabled={pending || detailsLoading || detailsUnavailable || !name.trim() || !zones.length || !states.length || !districts.length || !editScopeComplete || !editOutletIds.length || !hasBeatFrequencyDetails(frequency, days, weeks)} onClick={() => { void save(editOutletIds); }} />
        </>}
      >
        <div className={styles.content}>
          {error ? <Notice tone="error">{error}</Notice> : null}
          {row ? <div className={styles.card}><div className={styles.teamTop}><span className={styles.rowCopy}><strong>{beatDisplayTitle(row)}</strong><span>{beatDisplaySubtitle(row)}</span><span>Activation: {humanLabel(row.activation_state)}</span></span><StatusChip status={statusTone(row.lifecycle_state)} label={humanLabel(row.lifecycle_state)} type="outlined" /></div></div> : null}
          {detailsLoading ? (
            <Skeleton height={360} radius={12} />
          ) : detailsUnavailable ? (
            <ErrorState title="Beat details unavailable" message="The beat scope and outlet details could not be loaded." onRetry={() => { void beatDetail.refetch(); void geography.refetch(); void assignedScope.refetch(); if (isAdmin) void salesPeople.refetch(); }} />
          ) : (
            <>
              <TextField label="Beat name" value={name} onChange={(event) => setName((event.target as HTMLInputElement).value)} helperText={pendingApproval ? "Saving activates this beat without a separate approval." : "Changes apply immediately, without a separate approval."} />
              {isAdmin ? (
                <Select
                  label="Salesperson"
                  fullWidth
                  value={ownerId}
                  onChange={setEditOwner}
                  options={salespersonOptions}
                  helperText="Reassigning clears the geography scope below; choose the new zones, states, and districts to apply."
                />
              ) : null}
              <Section label="Geography scope">
                <GeoScopePicker
                  zones={geographyOptions.zones}
                  states={geographyOptions.states}
                  districts={geographyOptions.districts}
                  shopCategories={geographyOptions.categories}
                  assigned={{ zones: geographyOptions.pool.zones, states: geographyOptions.pool.states, districts: geographyOptions.pool.districts, shopCategories: geographyOptions.pool.categories }}
                  value={{ zones, states, districts, shopCategories: categories }}
                  onChange={(value) => {
                    setZones(value.zones);
                    setStates(value.states);
                    setDistricts(value.districts);
                    setCategories(asShopCategories(value.shopCategories));
                  }}
                />
              </Section>
              <ManagementBeatFrequencyFields frequency={frequency} days={days} weeks={weeks} onFrequencyChange={setFormFrequency} onDaysChange={setDays} onWeeksChange={setWeeks} />
              <Section label={`Outlets in this beat · ${editOutletIds.length}`}>
                <div className={styles.outletEditorStack}>
                  {droppedEditOutletCount > 0 ? <Notice tone="warning">{droppedOutletsNotice(droppedEditOutletCount)}</Notice> : null}
                  <div className="sp-search-toolbar">
                    <TextField
                      placeholder="Search outlets"
                      startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
                      value={editOutletQuery}
                      onChange={(event) => setEditOutletQuery((event.target as HTMLInputElement).value)}
                    />
                  </div>
                  <Button
                    variant="outlined"
                    color="primary"
                    size="small"
                    label={showAvailableOutlets ? "Show selected outlets only" : "Add outlets from scope"}
                    leftIcon={<Icon name={showAvailableOutlets ? "Check" : "Add"} size={18} color="currentColor" />}
                    onClick={() => setShowAvailableOutlets((current) => !current)}
                    style={{ width: "100%" }}
                  />
                  <Notice>Clear an outlet checkbox to remove it. Show available outlets to add more outlets from the beat scope.</Notice>
                  {editScopeOutlets.isError ? (
                    <ErrorState title="Outlets unavailable" message={editScopeOutlets.error instanceof ApiClientError ? editScopeOutlets.error.message : "Outlet choices could not be loaded for this scope."} onRetry={() => { void editScopeOutlets.refetch(); }} />
                  ) : districts.length && !editScopeComplete ? (
                    <Skeleton height={160} radius={12} />
                  ) : visibleEditOutlets.length ? (
                    <div className={styles.card} style={{ padding: 0 }}>
                      {visibleEditOutlets.map((outlet) => (
                        <ListRow
                          key={outlet.id}
                          leading={<Checkbox checked={editOutletIds.includes(outlet.id)} disabled={Boolean(outlet.takenBy)} onChange={(event) => { event.stopPropagation(); toggleOutlet(outlet); }} />}
                          title={outlet.name}
                          subtitle={outlet.takenBy ? `Already on beat ${outlet.takenBy}` : outlet.location || undefined}
                          meta={outlet.category || undefined}
                          disabled={Boolean(outlet.takenBy)}
                          onClick={outlet.takenBy ? undefined : () => toggleOutlet(outlet)}
                        />
                      ))}
                    </div>
                  ) : editOutletQuery.trim() && sortedEditOutlets.length ? (
                    <EmptyState icon="SearchOutlined" title={`No outlets match "${editOutletQuery}"`} message="Try another outlet name." actionLabel="Clear search" onAction={() => setEditOutletQuery("")} />
                  ) : (
                    <EmptyState icon="LocationMarker" title="No outlets" message="No outlets are linked to this beat." />
                  )}
                </div>
              </Section>
              <Notice>{pendingApproval ? "Saving activates this beat without a separate manager approval." : "Changes apply immediately, without a separate approval."}</Notice>
            </>
          )}
          {isAdmin ? <Notice tone="warning">Deactivating a beat hides it from route planning. History is kept.</Notice> : null}
        </div>
      </ManagementScreen>
    );
  }
  return (
    <ManagementScreen view="beats" footer={<Button variant="filled" color="primary" label="Create beat" leftIcon={<Icon name="Add" size={18} color="currentColor" />} onClick={startCreate} />}>
      <div className={styles.content}>
        {list.isPending ? (
          <>
            <Skeleton height={92} radius={12} />
            <Skeleton height={92} radius={12} />
          </>
        ) : list.isError ? (
          <ErrorState title="Beats unavailable" message="Beat management could not be loaded." onRetry={() => { void list.refetch(); }} />
        ) : rows.length ? (
          <>
            {nonDraftRows.length ? (
              <Section label="Approved beats">
              <div className={styles.card} style={{ padding: 0 }}>
                {nonDraftRows.map((beat) => (
                  <ListRow
                    key={beat.id}
                    leading={<Icon name="Calendar" size={22} color="var(--color-primary)" />}
                    title={beatDisplayTitle(beat)}
                    subtitle={`${beatDisplaySubtitle(beat)} · ${humanLabel(beat.activation_state)}`}
                    trailing={<StatusChip status={statusTone(beat.lifecycle_state)} label={humanLabel(beat.lifecycle_state)} type="outlined" />}
                    showChevron
                    onClick={() => {
                      setViewing(beat.id);
                      setViewOutletQuery("");
                      setEditing(null);
                      setError(null);
                      setShowAvailableOutlets(false);
                    }}
                  />
                ))}
              </div>
              </Section>
            ) : null}
            {draftRows.length ? (
              <Section label="Draft beats">
                <div className={styles.card} style={{ padding: 0 }}>
                  {draftRows.map((beat) => (
                    <ListRow
                      key={beat.id}
                      leading={<Icon name="Calendar" size={22} color="var(--color-primary)" />}
                      title={beatDisplayTitle(beat)}
                      subtitle={`${beatDisplaySubtitle(beat)} · ${humanLabel(beat.activation_state)}`}
                      trailing={<StatusChip status={statusTone(beat.lifecycle_state)} label={humanLabel(beat.lifecycle_state)} type="outlined" />}
                      showChevron
                      onClick={() => {
                        setViewing(beat.id);
                        setViewOutletQuery("");
                        setEditing(null);
                        setError(null);
                        setShowAvailableOutlets(false);
                      }}
                    />
                  ))}
                </div>
              </Section>
            ) : null}
          </>
        ) : (
          <EmptyState icon="LocationMarker" title="No beats" message="Released beat records will appear here after creation or approval." />
        )}
      </div>
    </ManagementScreen>
  );
}

const ADMIN_REPORTS: Array<{ id: string; title: string; subtitle: string; icon: string; path: string; filename: string; dated?: boolean }> = [
  {
    id: "geography-mapping",
    title: "Geography mapping report",
    subtitle: "Every employee's assigned zone, state and district",
    icon: "Map",
    path: "/api/v1/reporting/admin/reports/geography-mapping",
    filename: "geography-mapping-report.xlsx",
  },
  {
    id: "employee-hierarchy",
    title: "Org employee hierarchy report",
    subtitle: "Employee, role, designation and manager",
    icon: "AccountTree",
    path: "/api/v1/reporting/admin/reports/employee-hierarchy",
    filename: "employee-hierarchy-report.xlsx",
  },
  {
    id: "beats",
    title: "Beat report",
    subtitle: "Beat name, attached geography and sales person",
    icon: "LocationMarker",
    path: "/api/v1/reporting/admin/reports/beats",
    filename: "beat-report.xlsx",
  },
  {
    id: "beat-outlets",
    title: "Beat-wise attached outlet report",
    subtitle: "Every outlet attached to each beat",
    icon: "InventoryOutlined",
    path: "/api/v1/reporting/admin/reports/beat-outlets",
    filename: "beat-wise-outlet-report.xlsx",
  },
  {
    id: "unassigned-outlets",
    title: "Outlets not assigned to any beat",
    subtitle: "Outlets not on any beat, with zone, state and district",
    icon: "Warning",
    path: "/api/v1/reporting/admin/reports/unassigned-outlets",
    filename: "unassigned-outlets-by-geography-report.xlsx",
  },
  {
    id: "attendance",
    title: "Employee-wise attendance report",
    subtitle: "Uses the date range selected above (up to 4 months)",
    icon: "Schedule",
    path: "/api/v1/reporting/admin/reports/attendance",
    filename: "attendance-report.xlsx",
    dated: true,
  },
];

const ATTENDANCE_RANGE_MONTHS = 4;

function lastAllowedAttendanceDate(fromDate: string): string {
  const start = new Date(`${fromDate}T00:00:00Z`);
  const day = start.getUTCDate();
  const target = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + ATTENDANCE_RANGE_MONTHS, 1));
  const daysInTarget = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(Math.min(day, daysInTarget) - 1);
  return target.toISOString().slice(0, 10);
}

function AdminReports() {
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const today = istDateISO();
  const monthStart = `${today.slice(0, 7)}-01`;
  const [fromDate, setFromDate] = useState(monthStart);
  const [toDate, setToDate] = useState(today);
  const lastAllowedDate = lastAllowedAttendanceDate(fromDate);
  const toMax = lastAllowedDate < today ? lastAllowedDate : today;

  function changeFromDate(value: string) {
    setFromDate(value);
    const lastAllowed = lastAllowedAttendanceDate(value);
    if (toDate > lastAllowed) setToDate(lastAllowed);
  }

  async function runDownload(report: (typeof ADMIN_REPORTS)[number]) {
    setError(null);
    setPendingId(report.id);
    try {
      if (report.dated) {
        await downloadAdminReport(
          `${report.path}?from_date=${fromDate}&to_date=${toDate}`,
          `attendance-report-${fromDate}-to-${toDate}.xlsx`,
        );
      } else {
        await downloadAdminReport(report.path, report.filename);
      }
    } catch {
      setError("Couldn't download the report. Try again.");
    } finally {
      setPendingId(null);
    }
  }

  return (
    <ManagementScreen view="admin-reports">
      <div className={styles.content}>
        <Section label="">
          <div className={styles.optionGrid}>
            <DateField label="From" value={fromDate} max={toDate} onChange={changeFromDate} />
            <DateField label="To" value={toDate} min={fromDate} max={toMax} onChange={setToDate} />
          </div>
        </Section>
        <Section label="Downloads">
          <div className={styles.card} style={{ padding: 0 }}>
            {ADMIN_REPORTS.map((report) => (
              <ListRow
                key={report.id}
                leading={<Icon name={report.icon} size={22} color="var(--color-primary)" />}
                title={report.title}
                subtitle={report.subtitle}
                trailing={
                  <IconButton
                    iconName="DownloadOutlined"
                    color="primary"
                    disabled={pendingId !== null && pendingId !== report.id}
                    onClick={() => runDownload(report)}
                  />
                }
              />
            ))}
          </div>
        </Section>
        {error ? <Notice tone="warning">{error}</Notice> : null}
      </div>
    </ManagementScreen>
  );
}

function Notifications() {
  const toRolePath = useManagementPath();
  return (
    <NotificationsFeed
      resolveHref={toRolePath}
      renderShell={({ children, action, offline }) => (
        <ManagementScreen view="notifications" action={action} offline={offline}>
          {children}
        </ManagementScreen>
      )}
    />
  );
}

function More() {
  const router = useRouter();
  const { isAdmin } = useManagementRole();
  const session = useSyncExternalStore(subscribeToSession, readSessionSync, getServerSession);
  const [confirmLogout, setConfirmLogout] = useState(false);
  const managerGroups: Array<{ label: string; items: AccountAction[] }> = [
    {
      label: "Account",
      items: [
        { icon: "ProfileOutlined", label: "My profile", href: "/mgmt/profile" },
        { icon: "Calendar", label: "Leave", href: "/mgmt/my-leave" },
        { icon: "NotificationsOutlined", label: "Notifications", href: "/mgmt/notifications" },
      ],
    },
    {
      label: "Team",
      items: [
        { icon: "PersonRounded", label: "My team", href: "/mgmt/team" },
        { icon: "PersonRounded", label: "Combined visits", href: "/mgmt/combined-visits" },
        { icon: "LocationMarker", label: "Team coverage", href: "/mgmt/coverage" },
        { icon: "Schedule", label: "Team attendance", href: "/mgmt/attendance" },
        { icon: "Calendar", label: "Team leave", href: "/mgmt/leave" },
      ],
    },
    {
      label: "Operations",
      items: [
        { icon: "LocationMarker", label: "Beat management", href: "/mgmt/beats" },
        { icon: "ShoppingCartOutlined", label: "Orders", href: "/mgmt/dashboard-drill" },
      ],
    },
    {
      label: "Performance",
      items: [
        { icon: "Dashboard", label: "Team performance", href: "/mgmt/team-performance" },
        { icon: "RewardsOutlined", label: "Targets", href: "/mgmt/targets" },
      ],
    },
  ];
  const adminGroups: Array<{ label: string; items: AccountAction[] }> = [
    {
      label: "Account",
      items: [
        { icon: "ProfileOutlined", label: "My profile", href: "/mgmt/profile" },
        { icon: "NotificationsOutlined", label: "Notifications", href: "/mgmt/notifications" },
      ],
    },
    {
      label: "Operations",
      items: [
        { icon: "LocationMarker", label: "Org coverage", href: "/mgmt/coverage" },
        { icon: "LocationMarker", label: "Beat management", href: "/mgmt/beats" },
        { icon: "Schedule", label: "Attendance", href: "/mgmt/attendance" },
      ],
    },
    {
      label: "Performance",
      items: [{ icon: "RewardsOutlined", label: "Targets", href: "/mgmt/targets" }],
    },
    {
      label: "Data",
      items: [
        { icon: "Add", label: "Add employee", href: "/mgmt/employee-add" },
        { icon: "PersonRounded", label: "Reports", href: "/mgmt/admin-reports" },
      ],
    },
  ];
  const groups = isAdmin ? adminGroups : managerGroups;
  return (
    <ManagementScreen view="more">
      <div className={styles.morePage}>
        <div className={styles.content}>
          <div className={styles.card}>
            <ProfileIdentity
              compact
              name={session?.displayName ?? "Employee"}
              subtitle={session ? `${employeeRoleLabel(session.role)} · ${session.employeeId}` : employeeRoleLabel(isAdmin ? "admin" : "manager")}
            />
          </div>
          {groups.map((group) => (
            <Section label={group.label} key={group.label}>
              <AccountActionList actions={group.items} onNavigate={(href) => router.push(href)} />
            </Section>
          ))}
        </div>
        <div className={styles.logoutBar}>
          <Button variant="outlined" color="error" label="Log out" leftIcon={<Icon name="LogoutOutlined" size={20} color="currentColor" />} onClick={() => setConfirmLogout(true)} style={{ width: "100%" }} />
        </div>
      </div>
      {confirmLogout ? <LogoutConfirmSheet onClose={() => setConfirmLogout(false)} /> : null}
    </ManagementScreen>
  );
}

function ManagementProfile() {
  const session = useSyncExternalStore(subscribeToSession, readSessionSync, getServerSession);
  const profile = useQuery({
    queryKey: ["profile", { actorId: session?.employeeId ?? "" }],
    queryFn: ({ signal }) => getProfile(signal),
    enabled: Boolean(session?.employeeId),
  });
  if (profile.isPending) {
    return <ManagementScreen view="profile"><UserProfilePanelSkeleton /></ManagementScreen>;
  }
  if (profile.isError) {
    return (
      <ManagementScreen view="profile">
        <ErrorState
          title="Profile unavailable"
          message="Your profile could not be loaded."
          onRetry={() => { void profile.refetch(); }}
        />
      </ManagementScreen>
    );
  }
  if (!profile.data) {
    return (
      <ManagementScreen view="profile">
        <EmptyState title="Profile unavailable" message="No profile was returned for this account." />
      </ManagementScreen>
    );
  }
  const value = profile.data;
  return (
    <ManagementScreen view="profile">
      <UserProfilePanel
        profile={{
          name: value.name,
          initials: value.initials,
          employeeCode: value.employeeCode,
          roleLabel: employeeRoleLabel(value.role),
          sections: [
            {
              label: "Account",
              details: [
                { icon: "Call", label: "Phone (login)", value: value.phone },
              ],
            },
          ],
        }}
      />
    </ManagementScreen>
  );
}

export function ManagementFeaturePage({ view }: { view: ManagementView }) {
  const router = useRouter();
  const { isAdmin } = useManagementRole();
  const managerBlocked = !isAdmin && ["employee-add", "employee-edit", "hierarchy", "geography"].includes(view);
  const adminOwnLeaveBlocked = isAdmin && ["my-leave", "leave-apply", "leave-detail"].includes(view);
  const adminTeamPerformanceBlocked = isAdmin && view === "team-performance";
  const effectiveView = managerBlocked ? "employees" : adminOwnLeaveBlocked || adminTeamPerformanceBlocked ? "more" : view;
  switch (effectiveView) {
    case "dashboard": return isAdmin ? <AdminDashboard /> : <ManagerDashboard />;
    case "dashboard-drill": return <DashboardDrill />;
    case "approvals": return <ApprovalInbox />;
    case "approval-detail": return <Suspense><ApprovalDetail /></Suspense>;
    case "team": return <ScopedTeamOverview />;
    case "team-day": return <TeamDay />;
    case "employees": return <Suspense><EmployeeList /></Suspense>;
    case "employee": return <Suspense><EmployeeDetail /></Suspense>;
    case "employee-add": return <Suspense><EmployeeForm mode="add" /></Suspense>;
    case "employee-edit": return <Suspense><EmployeeForm mode="edit" /></Suspense>;
    case "org-tree": return <OrgTree />;
    case "hierarchy": return <Suspense><Hierarchy /></Suspense>;
    case "geography": return <Suspense><Geography /></Suspense>;
    case "combined-visits": return <Suspense><CombinedVisit /></Suspense>;
    case "combined-visit-sales-person": return <Suspense><CombinedVisitSalesPersonPage /></Suspense>;
    case "combined-visit-beat": return <Suspense><CombinedVisitBeatPage /></Suspense>;
    case "combined-visit-outlet": return <Suspense><CombinedVisitOutletPage /></Suspense>;
    case "combined-visit-day": return <Suspense><CombinedVisitDayPage /></Suspense>;
    case "visit-feedback": return <Suspense><VisitFeedback /></Suspense>;
    case "coverage": return <Suspense><Coverage /></Suspense>;
    case "attendance": return <Attendance />;
    case "order": return <Suspense><ScopedOrder /></Suspense>;
    case "leave": return <TeamLeave />;
    case "my-leave": return <MyLeave />;
    case "leave-apply": return <ApplyOwnLeave />;
    case "leave-detail": return <Suspense><OwnLeaveDetail /></Suspense>;
    case "targets": return <TargetsScreen />;
    case "target-edit": return <Suspense><TargetEditScreen /></Suspense>;
    case "team-performance": return <ManagerTeamPerformanceScreen />;
    case "beats": return <Beats />;
    case "admin-reports": return <AdminReports />;
    case "notifications": return <Notifications />;
    case "more": return <More />;
    case "profile": return <ManagementProfile />;
    default:
      return (
        <ManagementScreen view={effectiveView}>
          <div className={styles.content}>
            <EmptyState
              icon="Lock"
              title={`${viewTitles[effectiveView]} unavailable`}
              message="This management capability is not available from the released SFA API yet."
              actionLabel="Back to dashboard"
              onAction={() => router.push("/mgmt")}
            />
          </div>
        </ManagementScreen>
      );
  }
}
