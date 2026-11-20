"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import {
  getServerSession,
  readSessionSync,
  subscribeToSession,
} from "@/src/shared/auth/session";
import { useAppMutation } from "@/src/shared/state";
import { createActorQueryKeys } from "@/src/shared/state/query-keys";
import { resolveLeadDateWindow, type LeadFilters } from "./filters";
import { leadsService, type CaptureLeadBody } from "./service";

const LEADS_PAGE_SIZE = 20;

function useActorId() {
  return useSyncExternalStore(
    subscribeToSession,
    readSessionSync,
    getServerSession,
  )?.employeeId ?? "";
}

const baseKeys = createActorQueryKeys("leads");

export const leadKeys = {
  ...baseKeys,
  list: (actorId: string, filters: LeadFilters) =>
    [...baseKeys.all(actorId), "list", filters] as const,
  detail: (actorId: string, id: string) =>
    [...baseKeys.all(actorId), "detail", id] as const,
  counts: (actorId: string) =>
    [...baseKeys.all(actorId), "counts"] as const,
};

/** `filters.q` is expected to be debounced by the caller. */
export function useLeads(filters: LeadFilters) {
  const actorId = useActorId();
  return useInfiniteQuery({
    queryKey: leadKeys.list(actorId, filters),
    queryFn: ({ pageParam, signal }) => {
      const window = resolveLeadDateWindow(filters, new Date());
      return leadsService.list(
        {
          ...window,
          employeeId: filters.employeeId,
          q: filters.q,
          cursor: pageParam,
          limit: LEADS_PAGE_SIZE,
        },
        signal,
      );
    },
    initialPageParam: "",
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });
}

export function useLead(id: string) {
  const actorId = useActorId();
  return useQuery({
    queryKey: leadKeys.detail(actorId, id),
    queryFn: ({ signal }) => leadsService.detail(id, signal),
    enabled: Boolean(id),
  });
}

export function useLeadCountsByEmployee(enabled: boolean) {
  const actorId = useActorId();
  return useQuery({
    queryKey: leadKeys.counts(actorId),
    queryFn: ({ signal }) => leadsService.countsByEmployee(signal),
    enabled,
  });
}

export function useCaptureLead() {
  const actorId = useActorId();
  return useAppMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CaptureLeadBody;
      idempotencyKey?: string;
    }) => leadsService.captureLead(body, idempotencyKey),
    invalidate: [leadKeys.all(actorId)],
  });
}
