import {
  approveApiV1ApprovalsApprovalIdApprovePost,
  editAndApproveApiV1ApprovalsApprovalIdEditAndApprovePost,
  getApprovalApiV1ApprovalsApprovalIdGet,
  getEditableFieldsApiV1ApprovalsApprovalIdEditableFieldsGet,
  getNotificationApiV1NotificationsNotificationIdGet,
  getSummaryApiV1ApprovalsSummaryGet,
  getTimelineApiV1ApprovalsApprovalIdTimelineGet,
  getUnreadCountApiV1NotificationsUnreadCountGet,
  listApprovalsApiV1ApprovalsGet,
  listMyRequestsApiV1ApprovalsMineGet,
  listNotificationsApiV1NotificationsGet,
  markAllReadApiV1NotificationsReadAllPost,
  markReadApiV1NotificationsNotificationIdReadPost,
  rejectApiV1ApprovalsApprovalIdRejectPost,
  withdrawApiV1ApprovalsApprovalIdWithdrawPost,
  type ApprovalDetailResponse,
  type ApprovalListItem,
  type ApprovalListResponse,
  type ApprovalSummaryResponse,
  type EditableFieldsResponse,
  type MarkAllReadResponse,
  type MarkReadResponse,
  type NotificationItem,
  type NotificationListResponse,
  type TimelineResponse,
  type UnreadCountResponse,
} from "@humbee/api-contract";
import type { UserRole } from "@/src/shared/auth";
import {
  getBrowserApiClient,
  idempotencyHeaders,
} from "@/src/shared/api";

export type ApprovalFilter = "all" | "order" | "beat" | "leave" | "outlet";
export type ApprovalStatus = "pending" | "approved" | "approved_with_edits" | "auto_approved" | "rejected" | "withdrawn" | "expired" | "unknown";
export type ApprovalInboxStatus = Extract<ApprovalStatus, "pending" | "approved">;

export interface ApprovalInboxQuery {
  subjectType: ApprovalFilter;
  status: ApprovalInboxStatus;
  from?: string;
  to?: string;
}

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function client() {
  return getBrowserApiClient();
}

export const approvalService = {
  async listInbox(query: ApprovalInboxQuery, cursor?: string, signal?: AbortSignal): Promise<ApprovalListResponse> {
    return unwrap(await listApprovalsApiV1ApprovalsGet({
      client: client(),
      query: {
        cursor,
        from: query.from,
        limit: 30,
        status: query.status,
        subject_type: query.subjectType === "all" ? undefined : query.subjectType,
        to: query.to,
      },
      signal,
      throwOnError: true,
    }));
  },

  async listMine(cursor?: string, signal?: AbortSignal): Promise<ApprovalListResponse> {
    return unwrap(await listMyRequestsApiV1ApprovalsMineGet({
      client: client(),
      query: { cursor, limit: 30 },
      signal,
      throwOnError: true,
    }));
  },

  async getSummary(signal?: AbortSignal): Promise<ApprovalSummaryResponse> {
    return unwrap(await getSummaryApiV1ApprovalsSummaryGet({
      client: client(),
      signal,
      throwOnError: true,
    }));
  },

  async getDetail(approvalId: string, signal?: AbortSignal): Promise<ApprovalDetailResponse> {
    return unwrap(await getApprovalApiV1ApprovalsApprovalIdGet({
      client: client(),
      path: { approval_id: approvalId },
      signal,
      throwOnError: true,
    }));
  },

  async getTimeline(approvalId: string, signal?: AbortSignal): Promise<TimelineResponse> {
    return unwrap(await getTimelineApiV1ApprovalsApprovalIdTimelineGet({
      client: client(),
      path: { approval_id: approvalId },
      signal,
      throwOnError: true,
    }));
  },

  async getEditableFields(approvalId: string, signal?: AbortSignal): Promise<EditableFieldsResponse> {
    return unwrap(await getEditableFieldsApiV1ApprovalsApprovalIdEditableFieldsGet({
      client: client(),
      path: { approval_id: approvalId },
      signal,
      throwOnError: true,
    }));
  },

  async approve(approvalId: string, subjectVersion: number, idempotencyKey: string): Promise<ApprovalListItem> {
    return unwrap(await approveApiV1ApprovalsApprovalIdApprovePost({
      client: client(),
      path: { approval_id: approvalId },
      body: {},
      headers: { ...idempotencyHeaders(idempotencyKey), "If-Match": subjectVersion },
      throwOnError: true,
    }));
  },

  async reject(approvalId: string, subjectVersion: number, reason: string, idempotencyKey: string): Promise<ApprovalListItem> {
    return unwrap(await rejectApiV1ApprovalsApprovalIdRejectPost({
      client: client(),
      path: { approval_id: approvalId },
      body: { reason },
      headers: { ...idempotencyHeaders(idempotencyKey), "If-Match": subjectVersion },
      throwOnError: true,
    }));
  },

  async editAndApprove(approvalId: string, subjectVersion: number, patch: Record<string, unknown>, idempotencyKey: string): Promise<ApprovalListItem> {
    return unwrap(await editAndApproveApiV1ApprovalsApprovalIdEditAndApprovePost({
      client: client(),
      path: { approval_id: approvalId },
      body: { patch },
      headers: { ...idempotencyHeaders(idempotencyKey), "If-Match": subjectVersion },
      throwOnError: true,
    }));
  },

  async withdraw(approvalId: string, subjectVersion: number | undefined, idempotencyKey: string): Promise<ApprovalListItem> {
    return unwrap(await withdrawApiV1ApprovalsApprovalIdWithdrawPost({
      client: client(),
      path: { approval_id: approvalId },
      body: {},
      headers: {
        ...idempotencyHeaders(idempotencyKey),
        ...(subjectVersion !== undefined ? { "If-Match": subjectVersion } : {}),
      },
      throwOnError: true,
    }));
  },

  async listNotifications(cursor?: string, signal?: AbortSignal): Promise<NotificationListResponse> {
    return unwrap(await listNotificationsApiV1NotificationsGet({
      client: client(),
      query: { cursor, limit: 30 },
      signal,
      throwOnError: true,
    }));
  },

  async getNotification(notificationId: string, signal?: AbortSignal): Promise<NotificationItem> {
    return unwrap(await getNotificationApiV1NotificationsNotificationIdGet({
      client: client(),
      path: { notification_id: notificationId },
      signal,
      throwOnError: true,
    }));
  },

  async getUnreadCount(signal?: AbortSignal): Promise<UnreadCountResponse> {
    return unwrap(await getUnreadCountApiV1NotificationsUnreadCountGet({
      client: client(),
      signal,
      throwOnError: true,
    }));
  },

  async markNotificationRead(notificationId: string): Promise<MarkReadResponse> {
    return unwrap(await markReadApiV1NotificationsNotificationIdReadPost({
      client: client(),
      path: { notification_id: notificationId },
      throwOnError: true,
    }));
  },

  async markAllNotificationsRead(): Promise<MarkAllReadResponse> {
    return unwrap(await markAllReadApiV1NotificationsReadAllPost({
      client: client(),
      throwOnError: true,
    }));
  },
};

export function approvalStatus(status: string): ApprovalStatus {
  const known: ApprovalStatus[] = ["pending", "approved", "approved_with_edits", "auto_approved", "rejected", "withdrawn", "expired"];
  return known.includes(status as ApprovalStatus) ? status as ApprovalStatus : "unknown";
}

export type RequestChipTone = "pending" | "approved" | "partially-completed" | "cancelled" | "default";

function sentenceLabel(value: string) {
  const label = value.replace(/_/g, " ").trim().toLowerCase();
  return label ? `${label.charAt(0).toUpperCase()}${label.slice(1)}` : "—";
}

export function requestDisplayTitle(request: Pick<ApprovalListItem, "subject_type" | "title">) {
  if (!request.subject_type.startsWith("beat")) return request.title || "Request";
  const normalized = request.title.trim().replace(/^(Beat|Edit):\s*/i, "").trim();
  return normalized || "Coverage plan request";
}

export function requestDisplaySubtitle(request: Pick<ApprovalListItem, "routing_reason" | "subject_type" | "subtitle">) {
  if (!request.subject_type.startsWith("beat")) return request.subtitle;
  const outletCount = request.subtitle.match(/\b\d+\s+outlets?\b/i)?.[0];
  return outletCount ? sentenceLabel(outletCount) : sentenceLabel(request.routing_reason);
}

export function requestSubjectHref(request: Pick<ApprovalListItem, "id" | "status" | "subject_id" | "subject_type">) {
  if (request.subject_type === "dp_order") {
    return `/sp/orders/detail?orderId=${encodeURIComponent(request.subject_id)}`;
  }
  if (request.subject_type === "beat_create" && request.status === "rejected") return null;
  if (request.subject_type === "beat_create" || request.subject_type === "beat_edit") {
    return `/sp/beats/detail?beatId=${encodeURIComponent(request.subject_id)}`;
  }
  if (request.subject_type === "leave") {
    return `/sp/more/leave/detail?id=${encodeURIComponent(request.subject_id)}&approvalId=${encodeURIComponent(request.id)}`;
  }
  if (request.subject_type === "outlet_verification") {
    return `/sp/outlets/detail?candidateId=${encodeURIComponent(request.subject_id)}`;
  }
  return null;
}

export function requestChip(status: string): { label: string; status: RequestChipTone } {
  const resolved = approvalStatus(status);
  return {
    label: {
      pending: "Pending",
      approved: "Approved",
      approved_with_edits: "Edited",
      auto_approved: "Auto-approved",
      rejected: "Rejected",
      withdrawn: "Withdrawn",
      expired: "Expired",
      unknown: "Unavailable",
    }[resolved],
    status: resolved === "approved_with_edits"
      ? "partially-completed"
      : ["rejected", "withdrawn", "expired"].includes(resolved)
        ? "cancelled"
        : resolved === "auto_approved"
          ? "approved"
          : resolved === "pending" || resolved === "approved"
            ? resolved
            : "default",
  };
}

export function submittedRelativeLabel(submittedAt: string, now = Date.now()) {
  const then = Date.parse(submittedAt);
  if (!Number.isFinite(then)) return "";
  const minutes = Math.floor(Math.max(0, now - then) / 60_000);
  if (minutes < 1) return "Submitted just now";
  if (minutes < 60) return `Submitted ${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Submitted ${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `Submitted ${days}d ago`;
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
    year: new Date(then).getFullYear() === new Date(now).getFullYear() ? undefined : "numeric",
  }).format(new Date(then));
}

export function notificationHref(
  notification: Pick<NotificationItem, "deep_link_id" | "deep_link_type" | "source_request_id">,
  role: UserRole,
): string | null {
  const id = notification.deep_link_id;
  if (!id) return null;

  if (notification.deep_link_type === "order") {
    return role === "sp"
      ? `/sp/orders/detail?orderId=${encodeURIComponent(id)}`
      : `/mgmt/order?id=${encodeURIComponent(id)}`;
  }
  if (notification.deep_link_type === "beat") {
    return role === "sp"
      ? `/sp/beats/detail?beatId=${encodeURIComponent(id)}`
      : "/mgmt/beats";
  }
  if (notification.deep_link_type === "leave") {
    const approvalId = notification.source_request_id;
    const approvalQuery = approvalId ? `&approvalId=${encodeURIComponent(approvalId)}` : "";
    return role === "sp"
      ? `/sp/more/leave/detail?id=${encodeURIComponent(id)}${approvalQuery}`
      : `/mgmt/leave-detail?id=${encodeURIComponent(id)}${approvalQuery}`;
  }
  if (notification.deep_link_type === "outlet") {
    return role === "sp"
      ? `/sp/outlets/detail?candidateId=${encodeURIComponent(id)}`
      : `/mgmt/approval-detail?id=${encodeURIComponent(notification.source_request_id ?? id)}`;
  }
  if (notification.deep_link_type === "approval_request") {
    return role === "sp"
      ? "/sp/more/requests"
      : `/mgmt/approval-detail?id=${encodeURIComponent(id)}`;
  }
  return null;
}

