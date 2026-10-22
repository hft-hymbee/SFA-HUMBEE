"use client";

import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
  type QueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { readSessionSync } from "@/src/shared/auth/session";
import { createIdempotencyKey } from "@/src/shared/api";
import { useAppMutation } from "@/src/shared/state";
import {
  ordersService,
  type CartResponse,
  type CatalogResponse,
  type OrderEntry,
} from "./service";

function actorId() {
  return readSessionSync()?.employeeId ?? "anonymous";
}

export const orderKeys = {
  all: (actor = actorId()) => ["orders", { actorId: actor }] as const,
  lists: (actor = actorId()) => [...orderKeys.all(actor), "list"] as const,
  list: (status: string, actor = actorId()) =>
    [...orderKeys.lists(actor), { status }] as const,
  detail: (orderId: string, actor = actorId()) =>
    [...orderKeys.all(actor), "detail", orderId] as const,
  context: (entry: OrderEntry, outletEsiId = "", actor = actorId()) =>
    [
      ...orderKeys.all(actor),
      "context",
      entry.visitId,
      entry.outletId,
      entry.manufacturerId,
      entry.sellerId ?? "",
      outletEsiId,
    ] as const,
  outletSellers: (outletId: string, actor = actorId()) =>
    [...orderKeys.all(actor), "outlet-sellers", outletId] as const,
  cart: (cartId: string, actor = actorId()) =>
    [...orderKeys.all(actor), "cart", cartId] as const,
  catalog: (
    cartId: string,
    query: string,
    category: string,
    actor = actorId(),
  ) => [...orderKeys.cart(cartId, actor), "catalog", { query, category }] as const,
  purchaseOrders: (
    outletId: string,
    manufacturerId: string,
    sellerId: string,
    outletEsiId: string | undefined,
    actor = actorId(),
  ) => [
    ...orderKeys.all(actor),
    "purchase-orders",
    {
      outletId,
      manufacturerId,
      sellerId,
      outletEsiId,
    },
  ] as const,
  serviceableStates: (manufacturerId: string, actor = actorId()) =>
    [...orderKeys.all(actor), "serviceable-states", manufacturerId] as const,
  serviceableDistricts: (
    manufacturerId: string,
    stateId: string,
    actor = actorId(),
  ) => [...orderKeys.all(actor), "serviceable-districts", { manufacturerId, stateId }] as const,
  shipToAddressOptions: (districtId: string, actor = actorId()) =>
    [...orderKeys.all(actor), "ship-to-address-options", districtId] as const,
};

export function useOrders(status = "") {
  return useInfiniteQuery({
    queryKey: orderKeys.list(status),
    queryFn: ({ pageParam, signal }) =>
      ordersService.list({ status, cursor: pageParam, limit: 20 }, signal),
    initialPageParam: "",
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });
}

export function useOrder(orderId: string) {
  return useQuery({
    queryKey: orderKeys.detail(orderId),
    queryFn: ({ signal }) => ordersService.detail(orderId, signal),
    enabled: Boolean(orderId),
  });
}

type AutoSkipStatus = "idle" | "running" | "failed" | "done";

export function useAutoSkip(scopeKey: string) {
  const [attempt, setAttempt] = useState<{ scopeKey: string; status: AutoSkipStatus }>({ scopeKey, status: "idle" });
  const claimedScopeKey = useRef<string | null>(null);
  const begin = useCallback(() => {
    if (claimedScopeKey.current === scopeKey) return false;
    claimedScopeKey.current = scopeKey;
    setAttempt({ scopeKey, status: "running" });
    return true;
  }, [scopeKey]);
  const fail = useCallback(() => setAttempt({ scopeKey, status: "failed" }), [scopeKey]);
  const succeed = useCallback(() => setAttempt({ scopeKey, status: "done" }), [scopeKey]);
  const running = attempt.scopeKey === scopeKey && attempt.status === "running";
  return useMemo(() => ({ running, begin, fail, succeed }), [running, begin, fail, succeed]);
}

export function useRecoverIdlePendingQuery<TData>(
  query: Pick<UseQueryResult<TData>, "isPending" | "isFetching" | "fetchStatus" | "refetch">,
  enabled: boolean,
) {
  useEffect(() => {
    if (!enabled) return;
    if (query.isPending && !query.isFetching && query.fetchStatus === "idle") {
      void query.refetch();
    }
  }, [enabled, query.fetchStatus, query.isFetching, query.isPending, query.refetch]);
}

export function useOutletSellers(outletId: string) {
  return useQuery({
    queryKey: outletId
      ? orderKeys.outletSellers(outletId)
      : [...orderKeys.all(), "outlet-sellers", "unconfigured"],
    queryFn: ({ signal }) => ordersService.outletSellers(outletId, signal),
    enabled: Boolean(outletId),
    refetchOnWindowFocus: true,
    staleTime: 30_000,
  });
}

export function useOrderContext(entry: OrderEntry | null, outletEsiId = "") {
  return useQuery({
    queryKey: entry
      ? orderKeys.context(entry, outletEsiId)
      : [...orderKeys.all(), "context", "unconfigured"],
    queryFn: ({ signal }) =>
      ordersService.context(entry as OrderEntry, signal, outletEsiId || undefined),
    enabled: Boolean(entry),
    refetchOnWindowFocus: true,
  });
}

export function useCart(cartId: string) {
  return useQuery({
    queryKey: orderKeys.cart(cartId),
    queryFn: ({ signal }) => ordersService.cart(cartId, signal),
    enabled: Boolean(cartId),
    refetchOnWindowFocus: true,
    staleTime: 60_000,
    retry: false,
  });
}

export function useCatalog(cartId: string, query = "", category = "All") {
  return useQuery({
    queryKey: orderKeys.catalog(cartId, query, category),
    queryFn: ({ signal }) =>
      ordersService.catalog(cartId, { query, category }, signal),
    enabled: Boolean(cartId),
    staleTime: 30_000,
  });
}

export function usePurchaseOrders(entry: OrderEntry | null, enabled = true, outletEsiId?: string) {
  return useQuery({
    queryKey: entry
      ? orderKeys.purchaseOrders(
        entry.outletId,
        entry.manufacturerId,
        entry.sellerId!,
        outletEsiId,
      )
      : [...orderKeys.all(), "purchase-orders", "unconfigured"],
    queryFn: ({ signal }) =>
      ordersService.purchaseOrders(
        (entry as OrderEntry).outletId,
        (entry as OrderEntry).manufacturerId,
        (entry as OrderEntry).sellerId!,
        outletEsiId!,
        signal,
      ),
    enabled: Boolean(enabled && entry?.sellerId && outletEsiId),
    staleTime: 60_000,
  });
}

export function useServiceableStates(manufacturerId: string) {
  return useQuery({
    queryKey: manufacturerId
      ? orderKeys.serviceableStates(manufacturerId)
      : [...orderKeys.all(), "serviceable-states", "unconfigured"],
    queryFn: ({ signal }) => ordersService.serviceableStates(manufacturerId, signal),
    enabled: Boolean(manufacturerId),
    staleTime: 300_000,
  });
}

export function useServiceableDistricts(
  manufacturerId: string,
  stateId: string,
  enabled = true,
) {
  return useQuery({
    queryKey: manufacturerId && stateId
      ? orderKeys.serviceableDistricts(manufacturerId, stateId)
      : [...orderKeys.all(), "serviceable-districts", "unconfigured"],
    queryFn: ({ signal }) =>
      ordersService.serviceableDistricts(manufacturerId, stateId, signal),
    enabled: Boolean(enabled && manufacturerId && stateId),
    staleTime: 300_000,
  });
}

export function useShipToAddressOptions(districtId: string, enabled = true) {
  return useQuery({
    queryKey: districtId
      ? orderKeys.shipToAddressOptions(districtId)
      : [...orderKeys.all(), "ship-to-address-options", "unconfigured"],
    queryFn: ({ signal }) => ordersService.shipToAddressOptions(districtId, signal),
    enabled: Boolean(enabled && districtId),
    staleTime: 300_000,
  });
}

function updateCatalogCartSnapshot(queryClient: QueryClient, cart: CartResponse) {
  const quantityByProduct = new Map(cart.lines.map((line) => [line.product_id, line.qty]));
  queryClient.setQueriesData<CatalogResponse>(
    { queryKey: [...orderKeys.cart(cart.id), "catalog"] },
    (current) => current ? {
      ...current,
      cart_item_count: cart.lines.reduce((total, line) => total + line.qty, 0),
      cart_subtotal_net_paise: cart.subtotal_net_paise,
      products: current.products.map((product) => ({
        ...product,
        qty_in_cart: quantityByProduct.get(product.product_id) ?? 0,
      })),
    } : current,
  );
}

export function useCreateCart() {
  const queryClient = useQueryClient();
  return useAppMutation({
    mutationFn: (entry: OrderEntry) => ordersService.createCart(entry),
    onSuccess: (cart) => {
      queryClient.setQueryData(orderKeys.cart(cart.id), cart);
      updateCatalogCartSnapshot(queryClient, cart);
    },
  });
}

export function usePatchCart(cartId: string) {
  const queryClient = useQueryClient();
  return useAppMutation({
    mutationFn: (
      input: {
        body: Parameters<typeof ordersService.patchCart>[1];
        idempotencyKey: string;
      },
    ) => ordersService.patchCart(cartId, input.body, input.idempotencyKey),
    onSuccess: (cart) => {
      queryClient.setQueryData(orderKeys.cart(cart.id), cart);
    },
  });
}

export function usePatchCartById() {
  const queryClient = useQueryClient();
  return useAppMutation({
    mutationFn: (
      input: {
        cartId: string;
        body: Parameters<typeof ordersService.patchCart>[1];
        idempotencyKey: string;
      },
    ) => ordersService.patchCart(input.cartId, input.body, input.idempotencyKey),
    onSuccess: (cart) => {
      queryClient.setQueryData(orderKeys.cart(cart.id), cart);
    },
  });
}

export function useUpsertCartLine(cartId: string) {
  const queryClient = useQueryClient();
  return useAppMutation({
    mutationFn: (
      input: {
        lines: Array<{
          productId: string;
          quantity: number;
          formType?: "STRAIGHT" | "BEND" | null;
        }>;
        idempotencyKey: string;
      },
    ) => ordersService.upsertLines(
      cartId,
      input.lines,
      input.idempotencyKey,
    ),
    onSuccess: (cart: CartResponse) => {
      queryClient.setQueryData(orderKeys.cart(cart.id), cart);
      updateCatalogCartSnapshot(queryClient, cart);
    },
  });
}

export function useSubmitOrder() {
  const queryClient = useQueryClient();
  return useAppMutation({
    mutationFn: (
      input: { cartId: string; idempotencyKey: string },
    ) => ordersService.submit(input.cartId, input.idempotencyKey),
    onSuccess: (order) => {
      const actor = actorId();
      queryClient.setQueryData(orderKeys.detail(order.id), order);
      const queryKeys = [
        orderKeys.lists(actor),
        ["today", { actorId: actor }],
      ] as const;
      for (const queryKey of queryKeys) {
        void queryClient.invalidateQueries({ queryKey });
      }
      if (order.requires_approval || order.status === "pending_approval" || order.status === "awaiting_approval") {
        void queryClient.invalidateQueries({ queryKey: ["approvals", { actorId: actor }] });
        void queryClient.invalidateQueries({ queryKey: ["notifications", { actorId: actor }] });
      }
    },
  });
}

export function useRetryOrder(orderId: string) {
  const queryClient = useQueryClient();
  return useAppMutation({
    mutationFn: (idempotencyKey: string) =>
      ordersService.retry(orderId, idempotencyKey),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKeys.detail(order.id), order);
      void queryClient.invalidateQueries({ queryKey: orderKeys.lists() });
    },
  });
}

export function newMutationKey() {
  return createIdempotencyKey();
}
