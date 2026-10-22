"use client";

import {
  useMutation,
  useQueryClient,
  type QueryClient,
  type QueryKey,
  type UseMutationOptions,
} from "@tanstack/react-query";
import { ApiClientError } from "@/src/shared/api";
import { useConnectivity } from "@/src/shared/capabilities";

interface AppMutationOptions<TData, TVariables, TSnapshot>
  extends Omit<
    UseMutationOptions<TData, Error, TVariables, TSnapshot>,
    "onMutate" | "onError" | "onSuccess"
  > {
  invalidate?: QueryKey[] | ((data: TData, variables: TVariables) => QueryKey[]);
  optimistic?: (
    queryClient: QueryClient,
    variables: TVariables,
  ) => Promise<TSnapshot> | TSnapshot;
  rollback?: (
    queryClient: QueryClient,
    snapshot: TSnapshot,
    variables: TVariables,
  ) => void;
  onError?: (error: Error, variables: TVariables) => void;
  onSuccess?: (data: TData, variables: TVariables) => void;
}

export function useAppMutation<TData, TVariables, TSnapshot = never>(
  options: AppMutationOptions<TData, TVariables, TSnapshot>,
) {
  const queryClient = useQueryClient();
  const { isOnline } = useConnectivity();
  const {
    invalidate,
    mutationFn,
    onError,
    onSuccess,
    optimistic,
    rollback,
    ...mutationOptions
  } = options;

  return useMutation({
    ...mutationOptions,
    mutationFn,
    onMutate: async (variables) => {
      if (!isOnline) {
        throw new ApiClientError({
          code: "offline_write_blocked",
          status: 0,
          message: "Connect to the internet before trying this action.",
          details: null,
          requestId: null,
        });
      }
      return optimistic
        ? await optimistic(queryClient, variables)
        : undefined as TSnapshot;
    },
    onError: (error, variables, snapshot) => {
      if (snapshot !== undefined) {
        rollback?.(queryClient, snapshot, variables);
      }
      onError?.(error, variables);
    },
    onSuccess: async (data, variables) => {
      const keys = typeof invalidate === "function"
        ? invalidate(data, variables)
        : invalidate ?? [];
      await Promise.all(
        keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })),
      );
      onSuccess?.(data, variables);
    },
  });
}

export function mutationErrorMessage(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Something went wrong. Try again.";
}
