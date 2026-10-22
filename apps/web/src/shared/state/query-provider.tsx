"use client";

import {
  QueryClient,
  QueryClientProvider,
  onlineManager,
  useQueryClient,
} from "@tanstack/react-query";
import { OfflineBanner } from "humbee-design-system";
import { useEffect, useState, type ReactNode } from "react";
import { ApiClientError } from "@/src/shared/api";
import {
  getConnectivitySnapshot,
  subscribeToConnectivity,
  subscribeToHardwareBack,
  useConnectivity,
} from "@/src/shared/capabilities";

function shouldRetry(failureCount: number, error: Error) {
  if (failureCount >= 1) {
    return false;
  }
  if (error instanceof ApiClientError) {
    return error.status === 0 || error.status >= 500;
  }
  return false;
}

let appQueryClient: QueryClient | null = null;

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        gcTime: 5 * 60 * 1000,
        networkMode: "online",
        refetchInterval: false,
        refetchOnReconnect: "always",
        refetchOnWindowFocus: false,
        retry: shouldRetry,
        staleTime: 30 * 1000,
      },
      mutations: {
        networkMode: "online",
        retry: false,
      },
    },
  });
}

function ConnectivityBanner() {
  const { isOnline } = useConnectivity();
  const queryClient = useQueryClient();

  if (isOnline) {
    return null;
  }

  return (
    <OfflineBanner
      message="You're offline. Cached information remains available, but actions are paused."
      onRetry={() =>
        queryClient.refetchQueries({ type: "active" })
      }
    />
  );
}

export function AppQueryProvider({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);

  useEffect(
    () =>
      onlineManager.setEventListener((setOnline) => {
        setOnline(getConnectivitySnapshot());
        return subscribeToConnectivity(() =>
          setOnline(getConnectivitySnapshot()),
        );
      }),
    [],
  );

  useEffect(() => subscribeToHardwareBack(), []);

  useEffect(() => {
    appQueryClient = queryClient;
    return () => {
      if (appQueryClient === queryClient) {
        appQueryClient = null;
      }
    };
  }, [queryClient]);

  return (
    <QueryClientProvider client={queryClient}>
      <ConnectivityBanner />
      {children}
    </QueryClientProvider>
  );
}

export function clearAppQueryState() {
  appQueryClient?.clear();
}
