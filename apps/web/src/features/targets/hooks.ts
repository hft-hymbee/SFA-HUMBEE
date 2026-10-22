"use client";

import { useQuery } from "@tanstack/react-query";
import type { QueryKey } from "@tanstack/react-query";
import { useActorId } from "@/src/features/approvals/hooks";
import { useAppMutation } from "@/src/shared/state";
import {
  targetsService,
  type CreateTargetBody,
  type TargetListInput,
  type TargetType,
  type UpdateTargetInput,
  type RemoveTargetInput,
} from "./service";

export const targetsKeys = {
  all: (actorId: string) => ["targets", { actorId }] as const,
  manufacturers: (actorId: string) =>
    [...targetsKeys.all(actorId), "manufacturers"] as const,
  roster: (actorId: string, periodMonth: string) =>
    [...targetsKeys.all(actorId), "roster", periodMonth] as const,
  employeeMonth: (
    actorId: string,
    employeeId: string,
    periodMonth: string,
    targetType?: TargetType | null,
  ) =>
    [
      ...targetsKeys.all(actorId),
      "employee-month",
      { employeeId, periodMonth, targetType: targetType ?? "all" },
    ] as const,
  detail: (actorId: string, targetId: string) =>
    [...targetsKeys.all(actorId), "detail", targetId] as const,
};

export function useTargetManufacturers() {
  const actorId = useActorId();
  return useQuery({
    queryKey: targetsKeys.manufacturers(actorId),
    queryFn: ({ signal }) => targetsService.listManufacturers(signal),
    enabled: Boolean(actorId),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTargetRoster(periodMonth: string | null | undefined) {
  const actorId = useActorId();
  return useQuery({
    queryKey: targetsKeys.roster(actorId, periodMonth ?? ""),
    queryFn: ({ signal }) => targetsService.listRoster(periodMonth!, signal),
    enabled: Boolean(actorId && periodMonth),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useEmployeeTargets(input: TargetListInput | null | undefined) {
  const actorId = useActorId();
  return useQuery({
    queryKey: input
      ? targetsKeys.employeeMonth(
        actorId,
        input.employeeId,
        input.periodMonth,
        input.targetType,
      )
      : targetsKeys.employeeMonth(actorId, "", "", null),
    queryFn: ({ signal }) => targetsService.listTargets(input!, signal),
    enabled: Boolean(actorId && input?.employeeId && input?.periodMonth),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useTarget(targetId: string | null | undefined) {
  const actorId = useActorId();
  return useQuery({
    queryKey: targetsKeys.detail(actorId, targetId ?? ""),
    queryFn: ({ signal }) => targetsService.getTarget(targetId!, signal),
    enabled: Boolean(actorId && targetId),
    staleTime: 60_000,
  });
}

function targetInvalidations(
  actorId: string,
  input: {
    employeeId?: string;
    periodMonth?: string;
    targetType?: TargetType | null;
    targetId?: string;
  },
) {
  const keys: QueryKey[] = [
    targetsKeys.all(actorId),
    ["management", { actorId }, "targets"] as const,
  ];
  if (input.employeeId && input.periodMonth) {
    keys.push(
      targetsKeys.employeeMonth(
        actorId,
        input.employeeId,
        input.periodMonth,
        input.targetType,
      ),
    );
  }
  if (input.targetId) {
    keys.push(targetsKeys.detail(actorId, input.targetId));
  }
  return keys;
}

export function useCreateTarget() {
  const actorId = useActorId();
  return useAppMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateTargetBody;
      idempotencyKey?: string;
    }) => targetsService.createTarget(body, idempotencyKey),
    invalidate: (target) =>
      targetInvalidations(actorId, {
        employeeId: target.employee_id,
        periodMonth: target.period_month,
        targetId: target.id,
        targetType: target.target_type,
      }),
  });
}

export function useUpdateTarget() {
  const actorId = useActorId();
  return useAppMutation({
    mutationFn: (input: UpdateTargetInput) => targetsService.updateTarget(input),
    invalidate: (target) =>
      targetInvalidations(actorId, {
        employeeId: target.employee_id,
        periodMonth: target.period_month,
        targetId: target.id,
        targetType: target.target_type,
      }),
  });
}

export function useRemoveTarget() {
  const actorId = useActorId();
  return useAppMutation({
    mutationFn: (input: RemoveTargetInput) => targetsService.removeTarget(input),
    invalidate: (removed, input) =>
      targetInvalidations(actorId, { targetId: input.targetId }).concat([
        ["target-removed", removed.target_id] as const,
      ]),
  });
}
