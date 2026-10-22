"use client";

import {
  BottomSheet,
  Button,
  DateField,
  EmptyState,
  ErrorState,
  FAB,
  Icon,
  ListRow,
  Select,
  SkeletonRow,
  StatusChip,
  TextField,
} from "humbee-design-system";
import type { DetailBlock, LeaveRequestItem } from "@humbee/api-contract";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ulid } from "ulid";
import { ApiClientError, createIdempotencyKey } from "@/src/shared/api";
import { useConnectivity } from "@/src/shared/capabilities";
import { useInfiniteScrollTrigger } from "@/src/shared/state";
import { submittedRelativeLabel } from "@/src/features/approvals/service";
import { useApprovalDetail, useApprovalTimeline } from "@/src/features/approvals/hooks";
import { SpCard, SpInlineAlert, SpScreen, SpSectionLabel, SpStatusRow, SpStickyFooter, StatusHistory } from "@/src/features/shell/components";
import type { StatusHistoryStep } from "@/src/features/shell/components";
import { SpInlineSkeleton } from "@/src/features/shell/loading";
import { LeaveCalendar } from "./calendar";
import {
  MAX_LEAVE_DAYS,
  balanceLabel,
  dayLabel,
  formatLeaveDate,
  leaveChipStatus,
  leaveDateRange,
  leaveSpanDays,
  leaveStatusLabel,
  leaveTypeLabel,
} from "./format";
import {
  useLeaveBalances,
  useLeavePreview,
  useMyLeave,
  useSubmitLeave,
  useWithdrawLeave,
} from "./hooks";
import {
  LEAVE_TYPES,
  type LeaveType,
} from "./service";

export type LeaveJourneyPaths = {
  home: string;
  apply: string;
  detail: (id: string, approvalId: string) => string;
};

export type LeaveShellProps = {
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  bottomAction?: ReactNode;
  offline?: boolean;
};

export const spLeavePaths: LeaveJourneyPaths = {
  home: "/sp/more/leave",
  apply: "/sp/more/leave/apply",
  detail: (id, approvalId) => `/sp/more/leave/detail?id=${encodeURIComponent(id)}&approvalId=${encodeURIComponent(approvalId)}`,
};

function spLeaveShell({ title, children, footer, bottomAction, offline }: LeaveShellProps) {
  return (
    <SpScreen title={title} back offline={offline} bottomAction={bottomAction}>
      {children}
      {footer ? <SpStickyFooter>{footer}</SpStickyFooter> : null}
    </SpScreen>
  );
}

type LeaveScreenProps = {
  paths?: LeaveJourneyPaths;
  renderShell?: (props: LeaveShellProps) => ReactNode;
};

const availableDays = (value?: number) => String(Number((value ?? 0).toFixed(1)));

function leaveRequestSubtitle(item: LeaveRequestItem) {
  const days = dayLabel(item.day_count);
  if (item.status === "pending") return `${submittedRelativeLabel(item.applied_at)} · ${days}`;
  if (item.status === "rejected" && item.decision_note) return `${days} · ${item.decision_note}`;
  return days;
}

function LeaveBalanceCards({
  items,
}: {
  items: Array<{ available_days: number; leave_type: string }>;
}) {
  return (
    <div className="sp-leave-balances">
      {LEAVE_TYPES.map((type) => {
        const available = availableDays(items.find((item) => item.leave_type === type.value)?.available_days);
        return (
          <article
            aria-label={`${available} ${type.label} available`}
            className="sp-leave-balance"
            data-type={type.value}
            key={type.value}
          >
            <span className="sp-leave-balance__abbr">{type.abbr}</span>
            <span className="sp-leave-balance__label">{type.shortLabel}</span>
            <strong className="sp-leave-balance__value">{available}</strong>
          </article>
        );
      })}
    </div>
  );
}

export function LeaveStatusScreen({
  paths = spLeavePaths,
  renderShell = spLeaveShell,
}: LeaveScreenProps = {}) {
  const router = useRouter();
  const { isOnline } = useConnectivity();
  const calendar = useMyLeave("all");
  const balances = useLeaveBalances();
  const calendarItems = useMemo(
    () => calendar.data?.pages.flatMap((page) => page.items) ?? [],
    [calendar.data],
  );
  const loadOlderLeave = () => {
    if (calendar.hasNextPage && !calendar.isFetchingNextPage) void calendar.fetchNextPage();
  };
  const requestListRef = useInfiniteScrollTrigger<HTMLDivElement>({
    hasNextPage: calendar.hasNextPage,
    isFetchingNextPage: calendar.isFetchingNextPage,
    fetchNextPage: calendar.fetchNextPage,
  });
  const openLeave = (item: LeaveRequestItem) => {
    router.push(paths.detail(item.id, item.approval_request_id));
  };
  const applyAction = <FAB iconName="Add" label="Apply leave" onClick={() => router.push(paths.apply)} style={{ position: "static" }} />;
  const shell = (children: ReactNode) => renderShell({
    title: "Leave",
    children,
    bottomAction: applyAction,
    offline: !isOnline,
  });

  if (calendar.isPending) {
    return shell(<div className="sp-content">{[0, 1, 2].map((item) => <SkeletonRow key={item} />)}</div>);
  }
  if (calendar.isError && !calendarItems.length) {
    return shell(
      <ErrorState
        title="Leave unavailable"
        message="Your leave calendar could not be loaded."
        onRetry={() => { void calendar.refetch(); }}
      />,
    );
  }

  return shell(
    <>
      {balances.data ? (
        <div className="sp-content">
          <LeaveBalanceCards items={balances.data.items} />
        </div>
      ) : balances.isError ? (
        <div className="sp-content">
          <SpInlineAlert tone="error">Leave balances are unavailable. The calendar is still current.</SpInlineAlert>
        </div>
      ) : null}
      <div className="sp-content">
        <LeaveCalendar items={calendarItems} onOpenRequest={openLeave} onReachOldest={loadOlderLeave} />
      </div>
      {calendarItems.length ? (
        <div className="sp-content">
          <SpSectionLabel>Requests</SpSectionLabel>
          <div className="sp-list" ref={requestListRef}>
            {calendarItems.map((item) => (
              <ListRow
                key={item.id}
                leading={<Icon name="Calendar" size={22} color="var(--color-primary)" />}
                title={`${leaveTypeLabel(item.leave_type)} · ${leaveDateRange(item.from_date, item.to_date)}`}
                subtitle={leaveRequestSubtitle(item)}
                trailing={<StatusChip status={leaveChipStatus(item.status)} label={leaveStatusLabel(item.status)} type="outlined" />}
                showChevron
                onClick={() => openLeave(item)}
              />
            ))}
          </div>
        </div>
      ) : null}
    </>,
  );
}

function todayInIndia() {
  const parts = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).formatToParts(new Date());
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
  return `${value("year")}-${value("month")}-${value("day")}`;
}

export function ApplyLeaveScreen({
  paths = spLeavePaths,
  renderShell = spLeaveShell,
}: LeaveScreenProps = {}) {
  const router = useRouter();
  const { writesEnabled } = useConnectivity();
  const [type, setType] = useState<LeaveType>("casual");
  const [from, setFrom] = useState(todayInIndia);
  const [to, setTo] = useState(todayInIndia);
  const [reason, setReason] = useState("");
  const [requestId] = useState(ulid);
  const [idempotencyKey] = useState(createIdempotencyKey);
  const [error, setError] = useState<Error | null>(null);
  const currentLeaveYear = Number(todayInIndia().slice(0, 4));
  const preview = useLeavePreview(type, from, to);
  const submit = useSubmitLeave();
  const dateError = to < from
    ? "To date cannot be before From date."
    : leaveSpanDays(from, to) > MAX_LEAVE_DAYS
      ? `A leave request can cover at most ${MAX_LEAVE_DAYS} days.`
      : null;
  const reasonError = reason.length > 500 ? "Reason must be 500 characters or fewer." : null;
  const noAvailableLeave = Boolean(preview.data && preview.data.available_days <= 0);
  const handleFromChange = (value: string) => {
    setFrom(value);
    if (value > to) setTo(value);
  };
  const submitLeave = () => {
    if (dateError || reasonError || !preview.data || submit.isPending || !writesEnabled) return;
    setError(null);
    submit.mutate({
      body: {
        id: requestId,
        leave_type: type,
        from_date: from,
        to_date: to,
        reason: reason.trim() || null,
      },
      idempotencyKey,
    }, {
      onError: (submitError) => setError(submitError),
      onSuccess: () => router.replace(paths.home),
    });
  };
  const overlapping = error instanceof ApiClientError && error.code.toLowerCase() === "overlapping_leave";

  return renderShell({
    title: "Apply leave",
    offline: !writesEnabled,
    footer: (
      <Button
        variant="filled"
        color="primary"
        label={!writesEnabled ? "Connect to submit" : submit.isPending ? "Submitting…" : "Submit for approval"}
        disabled={!writesEnabled || Boolean(dateError || reasonError) || !preview.data || submit.isPending}
        onClick={submitLeave}
        style={{ width: "100%" }}
      />
    ),
    children: (
      <div className="sp-content">
        <Select
          label="Leave type"
          fullWidth
          value={type}
          onChange={(value) => setType(value as LeaveType)}
          options={LEAVE_TYPES}
        />
        <div className="sp-grid">
          <DateField label="From" value={formatLeaveDate(from)} dateValue={from} onChange={handleFromChange} />
          <DateField label="To" value={formatLeaveDate(to)} dateValue={to} onChange={setTo} min={from} />
        </div>
        {dateError ? <SpInlineAlert tone="error">{dateError}</SpInlineAlert> : null}
        {dateError ? null : <SpCard>
          {preview.isPending ? (
            <div className="sp-copy"><SpInlineSkeleton width="64%" height={13} /></div>
          ) : (
            <p className="sp-copy">
              {preview.data
                ? `${dayLabel(preview.data.day_count)} · ${leaveTypeLabel(type).toLowerCase()} balance after: ${balanceLabel(preview.data.balance_after)}${preview.data.period_year === currentLeaveYear ? "" : ` (${preview.data.period_year} leave year)`}`
                : "Leave preview unavailable"}
            </p>
          )}
        </SpCard>}
        {noAvailableLeave ? <SpInlineAlert tone="warning">You do not have any {leaveTypeLabel(type).toLowerCase()} leave balance available. You can still submit it for manager review.</SpInlineAlert> : null}
        {preview.data?.exceeds_balance && !noAvailableLeave ? <SpInlineAlert tone="warning">This exceeds your available balance. You can still submit it for review.</SpInlineAlert> : null}
        {preview.isError ? (
          <div className="sp-stack">
            <SpInlineAlert tone="error">The authoritative day count is unavailable. Retry before submitting.</SpInlineAlert>
            <Button
              variant="outlined"
              color="primary"
              label="Retry preview"
              onClick={() => { void preview.refetch(); }}
            />
          </div>
        ) : null}
        <TextField
          label="Reason"
          placeholder="Add a short reason"
          multiline
          rows={3}
          value={reason}
          error={Boolean(reasonError)}
          onChange={(event) => {
            setError(null);
            setReason((event.target as HTMLInputElement).value);
          }}
        />
        {reasonError ? <SpInlineAlert tone="error">{reasonError}</SpInlineAlert> : null}
        {overlapping ? <SpInlineAlert tone="error">These dates overlap an existing pending or approved leave request.</SpInlineAlert> : null}
        {error && !overlapping ? <SpInlineAlert tone="error">{error.message}</SpInlineAlert> : null}
        <SpInlineAlert>
          This request goes to your reporting manager and stays pending until they decide. If you have no reporting manager, it is approved automatically.
        </SpInlineAlert>
      </div>
    ),
  });
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

function timelineActionLabel(action: string) {
  return timelineActionLabels[action] ?? humanLabel(action);
}

function timelineState(state: string): StatusHistoryStep["state"] {
  if (state === "done" || state === "edited" || state === "rejected" || state === "current") return state;
  return "pending";
}

function formatDateTime(value: string | null) {
  if (!value) return undefined;
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    hour: "numeric",
    minute: "2-digit",
    month: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value));
}

function timelineDetail(note: string | null) {
  return note?.trim() || undefined;
}

function payloadText(value: unknown, key = "") {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    return key.toLowerCase().includes("balance") ? balanceLabel(value) : String(value);
  }
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return formatLeaveDate(value);
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function renderDetailBlock(block: DetailBlock) {
  if (block.kind === "date_range") {
    return (
      <SpStatusRow
        key={`${block.kind}-${block.label}`}
        label={block.label}
        value={`${leaveDateRange(String(block.payload.from_date), String(block.payload.to_date))} · ${dayLabel(Number(block.payload.day_count))}`}
      />
    );
  }

  return Object.entries(block.payload).map(([key, value]) => (
    <SpStatusRow key={`${block.kind}-${block.label}-${key}`} label={key} value={payloadText(value, key)} />
  ));
}

export function LeaveDetailScreen({
  paths = spLeavePaths,
  renderShell = spLeaveShell,
}: LeaveScreenProps = {}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { writesEnabled } = useConnectivity();
  const leaveId = searchParams.get("id") ?? "";
  const requestedApprovalId = searchParams.get("approvalId") ?? "";
  const history = useMyLeave("all");
  const leave = useMemo(
    () => history.data?.pages.flatMap((page) => page.items).find((item) => item.id === leaveId),
    [history.data, leaveId],
  );
  const approvalId = requestedApprovalId || leave?.approval_request_id || "";
  // A deep link may carry only the leave id (notification `deep_link` omits the approval id when
  // the notification has no source request), and the row may sit past the first history page.
  const lookingUpLeave = !requestedApprovalId && !leave;
  const { fetchNextPage, hasNextPage, isFetchingNextPage } = history;
  useEffect(() => {
    if (lookingUpLeave && hasNextPage && !isFetchingNextPage) void fetchNextPage();
  }, [lookingUpLeave, fetchNextPage, hasNextPage, isFetchingNextPage]);
  const detail = useApprovalDetail(approvalId);
  const timeline = useApprovalTimeline(approvalId);
  const withdraw = useWithdrawLeave(approvalId);
  const [error, setError] = useState<Error | null>(null);
  const [confirmWithdraw, setConfirmWithdraw] = useState(false);

  const shell = (children: ReactNode, footer?: ReactNode) => renderShell({
    title: "Leave request",
    children,
    footer,
    offline: !writesEnabled,
  });

  if (!leaveId && !requestedApprovalId) {
    return shell(<EmptyState icon="Calendar" title="No leave selected" message="Open a leave request from the leave list." actionLabel="Back to leave" onAction={() => router.replace(paths.home)} />);
  }

  // `detail` stays `isPending` forever while `approvalId` is empty, because the query is disabled.
  // Resolving the id is therefore its own gate — otherwise an unresolvable leave shows a skeleton
  // that never settles instead of the error below.
  const resolvingApprovalId = lookingUpLeave && (history.isPending || isFetchingNextPage || hasNextPage);
  if (resolvingApprovalId || (Boolean(approvalId) && detail.isPending)) {
    return shell(<div className="sp-content"><SkeletonRow /><SkeletonRow /><SkeletonRow /></div>);
  }

  if (!approvalId || detail.isError || !detail.data || detail.data.request.subject_type !== "leave") {
    return shell(
      <ErrorState
        title="Leave request unavailable"
        message="This leave request could not be loaded from the existing approval API."
        retryLabel="Back to leave"
        onRetry={() => router.replace(paths.home)}
      />,
    );
  }

  const request = detail.data.request;
  const steps: StatusHistoryStep[] = (timeline.data?.items ?? detail.data.timeline).map((step) => ({
    label: timelineActionLabel(step.action),
    detail: timelineDetail(step.note),
    time: formatDateTime(step.occurred_at),
    state: timelineState(step.state),
  }));
  const canWithdraw = detail.data.can_withdraw && request.is_pending;
  const withdrawLeave = () => {
    if (!canWithdraw || withdraw.isPending) return;
    setError(null);
    withdraw.mutate(
      { subjectVersion: request.subject_version, idempotencyKey: createIdempotencyKey() },
      {
        onError: (withdrawError) => {
          setConfirmWithdraw(false);
          setError(withdrawError);
        },
        onSuccess: () => {
          setConfirmWithdraw(false);
          router.replace(paths.home);
        },
      },
    );
  };

  return shell(
    <>
      <div className="sp-content">
        <SpCard>
          <div className="sp-row" style={{ alignItems: "flex-start" }}>
            <div>
              <h2 className="sp-title">{request.title || "Leave request"}</h2>
              <p className="sp-meta">{request.subtitle || `Submitted ${formatDateTime(request.submitted_at) ?? ""}`}</p>
            </div>
            <StatusChip status={leaveChipStatus(request.status)} label={leaveStatusLabel(request.status)} type="filled" />
          </div>
        </SpCard>

        <div>
          <SpSectionLabel>Request information</SpSectionLabel>
          <SpCard>
            <div className="sp-stack">
              {detail.data.blocks.length
                ? detail.data.blocks.map(renderDetailBlock)
                : <SpStatusRow label="Status" value={leaveStatusLabel(request.status)} />}
            </div>
          </SpCard>
        </div>

        {timeline.isError ? (
          <SpInlineAlert tone="error">Approval history could not be refreshed. Showing the latest loaded status.</SpInlineAlert>
        ) : null}
        <StatusHistory steps={steps} historyKey={`${approvalId}-${request.status}`} />
        {error ? <SpInlineAlert tone="error">{error.message}</SpInlineAlert> : null}
      </div>
      <BottomSheet open={confirmWithdraw} title="Withdraw leave request?" onClose={() => setConfirmWithdraw(false)}>
        <div className="sp-stack">
          <p className="sp-copy">Your manager will no longer need to approve or reject this request. The reserved days go back to your balance.</p>
          <Button
            variant="filled"
            color="error"
            label={withdraw.isPending ? "Withdrawing…" : "Withdraw request"}
            disabled={withdraw.isPending}
            onClick={withdrawLeave}
            style={{ width: "100%" }}
          />
          <Button
            variant="outlined"
            color="neutral"
            label="Keep request"
            disabled={withdraw.isPending}
            onClick={() => setConfirmWithdraw(false)}
            style={{ width: "100%" }}
          />
        </div>
      </BottomSheet>
    </>,
    canWithdraw ? (
      <Button
        variant="outlined"
        color="error"
        label={!writesEnabled ? "Connect to withdraw" : withdraw.isPending ? "Withdrawing…" : "Withdraw request"}
        disabled={!writesEnabled || withdraw.isPending}
        onClick={() => setConfirmWithdraw(true)}
        style={{ width: "100%" }}
      />
    ) : undefined,
  );
}
