"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryKey,
} from "@tanstack/react-query";
import type {
  ApprovalListItem,
  ApprovalListResponse,
  NotificationListResponse,
} from "@humbee/api-contract";
import { useEffect, useSyncExternalStore } from "react";
import { ApiClientError } from "@/src/shared/api";
import { noteUnreadCount } from "@/src/shared/feedback";
import {
  getServerSession,
  readSessionSync,
  subscribeToSession,
} from "@/src/shared/auth/session";
import { outletOnboardingKeys } from "@/src/features/outlets/service";
import { useAppMutation } from "@/src/shared/state";
import { approvalService, type ApprovalInboxQuery } from "./service";

const actorId = () => readSessionSync()?.employeeId ?? "";
const serverActorId = () => getServerSession()?.employeeId ?? "";

export const approvalKeys = {
  all: (id: string) => ["approvals", { actorId: id }] as const,
  inbox: (id: string, query: ApprovalInboxQuery) => ["approvals", { actorId: id }, "inbox", query] as const,
  mine: (id: string) => ["approvals", { actorId: id }, "mine"] as const,
  detail: (id: string, approvalId: string) => ["approvals", { actorId: id }, "detail", approvalId] as const,
  timeline: (id: string, approvalId: string) => ["approvals", { actorId: id }, "timeline", approvalId] as const,
  editableFields: (id: string, approvalId: string) => ["approvals", { actorId: id }, "editable-fields", approvalId] as const,
  summary: (id: string) => ["approvals", { actorId: id }, "summary"] as const,
  notifications: (id: string) => ["notifications", { actorId: id }, "feed"] as const,
  notification: (id: string, notificationId: string) => ["notifications", { actorId: id }, "detail", notificationId] as const,
  unread: (id: string) => ["notifications", { actorId: id }, "unread-count"] as const,
};

export function useActorId() {
  return useSyncExternalStore(subscribeToSession, actorId, serverActorId);
}

export function useApprovalInbox(query: ApprovalInboxQuery) {
  const id = useActorId();
  return useInfiniteQuery({
    queryKey: approvalKeys.inbox(id, query),
    queryFn: ({ pageParam, signal }) => approvalService.listInbox(query, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: Boolean(id && query.from && query.to && query.to >= query.from),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

export function useMyRequests() {
  const id = useActorId();
  return useInfiniteQuery({
    queryKey: approvalKeys.mine(id),
    queryFn: ({ pageParam, signal }) => approvalService.listMine(pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: Boolean(id),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useApprovalSummary() {
  const id = useActorId();
  return useQuery({
    queryKey: approvalKeys.summary(id),
    queryFn: ({ signal }) => approvalService.getSummary(signal),
    enabled: Boolean(id),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}

export function useApprovalDetail(approvalId: string) {
  const id = useActorId();
  return useQuery({
    queryKey: approvalKeys.detail(id, approvalId),
    queryFn: ({ signal }) => approvalService.getDetail(approvalId, signal),
    enabled: Boolean(id && approvalId),
    staleTime: 30_000,
  });
}

export function useApprovalTimeline(approvalId: string) {
  const id = useActorId();
  return useQuery({
    queryKey: approvalKeys.timeline(id, approvalId),
    queryFn: ({ signal }) => approvalService.getTimeline(approvalId, signal),
    enabled: Boolean(id && approvalId),
    staleTime: 30_000,
  });
}

export function useApprovalEditableFields(approvalId: string) {
  const id = useActorId();
  return useQuery({
    queryKey: approvalKeys.editableFields(id, approvalId),
    queryFn: ({ signal }) => approvalService.getEditableFields(approvalId, signal),
    enabled: Boolean(id && approvalId),
    staleTime: 30_000,
  });
}

function subjectInvalidations(id: string, result: ApprovalListItem): QueryKey[] {
  const subjectType = result.subject_type.toLowerCase();
  if (subjectType.includes("leave")) {
    return [
      ["leave", { actorId: id }],
      ["today", { actorId: id }],
    ];
  }
  if (subjectType.includes("order")) {
    return [
      ["orders", { actorId: id }],
      ["today", { actorId: id }],
    ];
  }
  if (subjectType.includes("beat")) {
    return [
      ["beats", { actorId: id }],
      ["beats", id, result.subject_id],
    ];
  }
  if (subjectType.includes("outlet")) {
    return [
      outletOnboardingKeys.candidates(id),
      outletOnboardingKeys.candidate(id, result.subject_id),
    ];
  }
  return [
    ["leave", { actorId: id }],
    ["today", { actorId: id }],
    ["orders", { actorId: id }],
    ["beats", { actorId: id }],
    outletOnboardingKeys.candidates(id),
  ];
}

function approvalInvalidations(id: string, approvalId: string, result: ApprovalListItem) {
  return [
    approvalKeys.all(id),
    approvalKeys.detail(id, approvalId),
    approvalKeys.notifications(id),
    approvalKeys.unread(id),
    ...subjectInvalidations(id, result),
  ];
}

export function useApprovalDecision(approvalId: string) {
  const id = useActorId();
  const queryClient = useQueryClient();
  const onError = (error: Error) => {
    if (error instanceof ApiClientError && ["approval_already_decided", "subject_changed"].includes(error.code.toLowerCase())) {
      void queryClient.invalidateQueries({ queryKey: approvalKeys.detail(id, approvalId) });
    }
  };

  const approve = useAppMutation({
    mutationFn: ({ subjectVersion, idempotencyKey }: { subjectVersion: number; idempotencyKey: string }) =>
      approvalService.approve(approvalId, subjectVersion, idempotencyKey),
    invalidate: (result) => approvalInvalidations(id, approvalId, result),
    onError,
  });
  const reject = useAppMutation({
    mutationFn: ({ subjectVersion, reason, idempotencyKey }: { subjectVersion: number; reason: string; idempotencyKey: string }) =>
      approvalService.reject(approvalId, subjectVersion, reason, idempotencyKey),
    invalidate: (result) => approvalInvalidations(id, approvalId, result),
    onError,
  });
  const editAndApprove = useAppMutation({
    mutationFn: ({ subjectVersion, patch, idempotencyKey }: { subjectVersion: number; patch: Record<string, unknown>; idempotencyKey: string }) =>
      approvalService.editAndApprove(approvalId, subjectVersion, patch, idempotencyKey),
    invalidate: (result) => approvalInvalidations(id, approvalId, result),
    onError,
  });
  const withdraw = useAppMutation({
    mutationFn: ({ subjectVersion, idempotencyKey }: { subjectVersion: number; idempotencyKey: string }) =>
      approvalService.withdraw(approvalId, subjectVersion, idempotencyKey),
    invalidate: (result) => approvalInvalidations(id, approvalId, result),
    onError,
  });

  return { approve, reject, editAndApprove, withdraw };
}

export function useNotifications() {
  const id = useActorId();
  return useInfiniteQuery({
    queryKey: approvalKeys.notifications(id),
    queryFn: ({ pageParam, signal }) => approvalService.listNotifications(pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: Boolean(id),
    staleTime: 30_000,
  });
}

export function useUnreadNotificationCount() {
  const id = useActorId();
  const unread = useQuery({
    queryKey: approvalKeys.unread(id),
    queryFn: ({ signal }) => approvalService.getUnreadCount(signal),
    enabled: Boolean(id),
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });

  useEffect(() => {
    if (!id || unread.data?.count === undefined) return;
    noteUnreadCount(id, unread.data.count);
  }, [id, unread.data?.count]);

  return unread;
}

export function useNotificationDetail(notificationId: string) {
  const id = useActorId();
  return useQuery({
    queryKey: approvalKeys.notification(id, notificationId),
    queryFn: ({ signal }) => approvalService.getNotification(notificationId, signal),
    enabled: Boolean(id && notificationId),
    staleTime: 30_000,
  });
}

export function useNotificationActions() {
  const id = useActorId();
  const queryClient = useQueryClient();
  const feedKey = approvalKeys.notifications(id);
  const unreadKey = approvalKeys.unread(id);

  const markRead = useMutation({
    mutationFn: approvalService.markNotificationRead,
    onSuccess: (result) => {
      queryClient.setQueryData(unreadKey, { count: result.unread_count });
      queryClient.setQueryData<InfiniteData<NotificationListResponse>>(feedKey, (current) => current ? ({
        ...current,
        pages: current.pages.map((page) => ({
          ...page,
          unread_count: result.unread_count,
          items: page.items.map((item) => item.id === result.id
            ? { ...item, is_unread: false, read_at: result.read_at }
            : item),
        })),
      }) : current);
      void queryClient.invalidateQueries({ queryKey: approvalKeys.mine(id) });
    },
  });

  const markAllRead = useMutation({
    mutationFn: approvalService.markAllNotificationsRead,
    onSuccess: (result) => {
      const readAt = new Date().toISOString();
      queryClient.setQueryData(unreadKey, { count: result.unread_count });
      queryClient.setQueryData<InfiniteData<NotificationListResponse>>(feedKey, (current) => current ? ({
        ...current,
        pages: current.pages.map((page) => ({
          ...page,
          unread_count: result.unread_count,
          items: page.items.map((item) => ({ ...item, is_unread: false, read_at: item.read_at ?? readAt })),
        })),
      }) : current);
    },
  });

  return { markRead, markAllRead };
}

export function flattenApprovals(data?: InfiniteData<ApprovalListResponse>): ApprovalListItem[] {
  return data?.pages.flatMap((page) => page.items) ?? [];
}
