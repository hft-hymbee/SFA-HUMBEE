"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import {
  getServerSession,
  readSessionSync,
  subscribeToSession,
} from "@/src/shared/auth/session";
import { useAppMutation } from "@/src/shared/state";
import {
  organizationService,
  type EmployeeFilters,
} from "./organization-service";

function useActorId() {
  return useSyncExternalStore(
    subscribeToSession,
    readSessionSync,
    getServerSession,
  )?.employeeId ?? "";
}

export const organizationKeys = {
  all: (actorId: string) => ["organization", { actorId }] as const,
  employees: (actorId: string, filters: EmployeeFilters) =>
    [...organizationKeys.all(actorId), "employees", filters] as const,
  employee: (actorId: string, employeeId: string) =>
    [...organizationKeys.all(actorId), "employee", employeeId] as const,
  tree: (actorId: string) =>
    [...organizationKeys.all(actorId), "tree"] as const,
  moveCandidates: (actorId: string, employeeId: string) =>
    [...organizationKeys.all(actorId), "move-candidates", employeeId] as const,
  geographyMaster: (actorId: string) =>
    [...organizationKeys.all(actorId), "geography-master"] as const,
  geographyScope: (actorId: string, employeeId: string) =>
    [...organizationKeys.all(actorId), "geography-scope", employeeId] as const,
};

export function useEmployees(filters: EmployeeFilters = {}) {
  const actorId = useActorId();
  return useQuery({
    queryKey: organizationKeys.employees(actorId, filters),
    queryFn: ({ signal }) => organizationService.listEmployees(filters, signal),
    enabled: Boolean(actorId),
  });
}

export function useEmployee(employeeId: string | null | undefined) {
  const actorId = useActorId();
  return useQuery({
    queryKey: organizationKeys.employee(actorId, employeeId ?? ""),
    queryFn: ({ signal }) => organizationService.getEmployee(employeeId!, signal),
    enabled: Boolean(actorId && employeeId),
  });
}

export function useOrganizationTree() {
  const actorId = useActorId();
  return useQuery({
    queryKey: organizationKeys.tree(actorId),
    queryFn: ({ signal }) => organizationService.getTree(signal),
    enabled: Boolean(actorId),
  });
}

export function useMoveCandidates(employeeId: string | null | undefined) {
  const actorId = useActorId();
  return useQuery({
    queryKey: organizationKeys.moveCandidates(actorId, employeeId ?? ""),
    queryFn: ({ signal }) => organizationService.getMoveCandidates(employeeId!, signal),
    enabled: Boolean(actorId && employeeId),
  });
}

export function useGeographyMaster(enabled = true) {
  const actorId = useActorId();
  return useQuery({
    queryKey: organizationKeys.geographyMaster(actorId),
    queryFn: ({ signal }) => organizationService.getGeographyMaster(signal),
    enabled: Boolean(actorId && enabled),
    staleTime: 5 * 60 * 1000,
  });
}

export function useGeographyScope(employeeId: string | null | undefined) {
  const actorId = useActorId();
  return useQuery({
    queryKey: organizationKeys.geographyScope(actorId, employeeId ?? ""),
    queryFn: ({ signal }) => organizationService.getGeographyScope(employeeId!, signal),
    enabled: Boolean(actorId && employeeId),
  });
}

export function useOrganizationMutations() {
  const actorId = useActorId();
  const queryClient = useQueryClient();
  const invalidate = () => [
    organizationKeys.all(actorId),
    ["profile"] as const,
  ];

  return {
    createEmployee: useAppMutation({
      mutationFn: organizationService.createEmployee,
      invalidate,
    }),
    updateEmployee: useAppMutation({
      mutationFn: ({
        employeeId,
        body,
      }: {
        employeeId: string;
        body: Parameters<typeof organizationService.updateEmployee>[1];
      }) => organizationService.updateEmployee(employeeId, body),
      invalidate,
    }),
    deactivateEmployee: useAppMutation({
      mutationFn: ({
        employeeId,
        reason,
      }: {
        employeeId: string;
        reason?: string;
      }) => organizationService.deactivateEmployee(employeeId, reason),
      invalidate,
    }),
    moveEmployee: useAppMutation({
      mutationFn: ({
        employeeId,
        managerId,
      }: {
        employeeId: string;
        managerId: string | null;
      }) => organizationService.moveEmployee(employeeId, managerId),
      invalidate,
    }),
    assignGeography: useAppMutation({
      mutationFn: ({
        employeeId,
        body,
      }: {
        employeeId: string;
        body: Parameters<typeof organizationService.assignGeographyScope>[1];
      }) => organizationService.assignGeographyScope(employeeId, body),
      invalidate,
    }),
    removeEmployeeCache(employeeId: string) {
      queryClient.removeQueries({
        queryKey: organizationKeys.employee(actorId, employeeId),
      });
    },
  };
}
