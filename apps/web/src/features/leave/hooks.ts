"use client";

import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { ApiClientError } from "@/src/shared/api";
import { useAppMutation } from "@/src/shared/state";
import { approvalKeys, useActorId } from "@/src/features/approvals/hooks";
import { approvalService } from "@/src/features/approvals/service";
import { MAX_LEAVE_DAYS, leaveSpanDays } from "./format";
import {
  leaveService,
  type LeaveHistoryFilter,
  type LeaveType,
  type TeamLeaveFilter,
} from "./service";

export const leaveKeys = {
  all: (actorId: string) => ["leave", { actorId }] as const,
  balances: (actorId: string) => ["leave", { actorId }, "balances"] as const,
  preview: (actorId: string, leaveType: LeaveType, fromDate: string, toDate: string) =>
    ["leave", { actorId }, "preview", { leaveType, fromDate, toDate }] as const,
  mine: (actorId: string, filter: LeaveHistoryFilter) =>
    ["leave", { actorId }, "mine", filter] as const,
  team: (actorId: string, filter: TeamLeaveFilter) =>
    ["leave", { actorId }, "team", filter] as const,
};

export function useLeaveBalances() {
  const actorId = useActorId();
  return useQuery({
    queryKey: leaveKeys.balances(actorId),
    queryFn: ({ signal }) => leaveService.getBalances(signal),
    enabled: Boolean(actorId),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useLeavePreview(
  leaveType: LeaveType,
  fromDate: string,
  toDate: string,
) {
  const actorId = useActorId();
  return useQuery({
    queryKey: leaveKeys.preview(actorId, leaveType, fromDate, toDate),
    queryFn: ({ signal }) => leaveService.preview(leaveType, fromDate, toDate, signal),
    enabled: Boolean(actorId && fromDate && toDate && toDate >= fromDate && leaveSpanDays(fromDate, toDate) <= MAX_LEAVE_DAYS),
    staleTime: 0,
  });
}

export function useMyLeave(filter: LeaveHistoryFilter) {
  const actorId = useActorId();
  return useInfiniteQuery({
    queryKey: leaveKeys.mine(actorId, filter),
    queryFn: ({ pageParam, signal }) => leaveService.listMine(filter, pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: (page, pages) => page.items.length === 30 ? pages.length * 30 : undefined,
    enabled: Boolean(actorId),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useTeamLeave(filter: TeamLeaveFilter) {
  const actorId = useActorId();
  return useInfiniteQuery({
    queryKey: leaveKeys.team(actorId, filter),
    queryFn: ({ pageParam, signal }) => leaveService.listTeam(filter, pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: (page, pages) => page.items.length === 30 ? pages.length * 30 : undefined,
    enabled: Boolean(actorId),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

function leaveInvalidations(actorId: string) {
  return [
    leaveKeys.all(actorId),
    approvalKeys.all(actorId),
    approvalKeys.notifications(actorId),
    approvalKeys.unread(actorId),
    ["today", { actorId }],
  ];
}

export function useSubmitLeave() {
  const actorId = useActorId();
  return useAppMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: Parameters<typeof leaveService.submit>[0];
      idempotencyKey: string;
    }) => leaveService.submit(body, idempotencyKey),
    invalidate: () => leaveInvalidations(actorId),
  });
}

export function useWithdrawLeave(approvalRequestId: string) {
  const actorId = useActorId();
  const queryClient = useQueryClient();
  return useAppMutation({
    mutationFn: ({
      subjectVersion,
      idempotencyKey,
    }: {
      subjectVersion?: number;
      idempotencyKey: string;
    }) => approvalService.withdraw(approvalRequestId, subjectVersion, idempotencyKey),
    invalidate: () => leaveInvalidations(actorId),
    onError: (error) => {
      if (error instanceof ApiClientError && error.code.toLowerCase() === "approval_already_decided") {
        void queryClient.invalidateQueries({ queryKey: leaveKeys.all(actorId) });
      }
    },
  });
}
