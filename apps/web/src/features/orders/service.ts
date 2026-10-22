import {
  createCartApiV1CartsPost,
  firmAddressOptionsApiV1OutletsOnboardingAddressOptionsGet,
  getCartApiV1CartsCartIdGet,
  getCatalogApiV1OrdersCatalogGet,
  getOrderApiV1OrdersOrderIdGet,
  getOrderContextApiV1OrdersContextGet,
  getOutletSellersApiV1OutletsOutletIdSellersGet,
  getPurchaseOrdersApiV1OrdersPurchaseOrdersGet,
  getServiceableDistrictsApiV1OrdersServiceableDistrictsGet,
  getServiceableStatesApiV1OrdersServiceableStatesGet,
  listOrdersApiV1OrdersGet,
  patchCartApiV1CartsCartIdPatch,
  retrySubmissionApiV1OrdersOrderIdRetrySubmissionPost,
  submitOrderApiV1OrdersPost,
  upsertLineApiV1CartsCartIdLinesPut,
  type CartResponse as ContractCartResponse,
  type CatalogResponse,
  type OrderContextResponse,
  type OrderDetailOut,
  type OrderListResponse,
  type OutletSellersResponse,
  type CreateCartBody,
  type FirmAddressOptionsResponse,
  type PatchCartBody as ContractPatchCartBody,
  type PurchaseOrdersResponse,
  type ServiceableDistrictsResponse,
  type ServiceableStatesResponse,
} from "@humbee/api-contract";
import {
  createIdempotencyKey,
  getBrowserApiClient,
  idempotencyHeaders,
} from "@/src/shared/api";

export type PartnerRole = "manufacturer" | "distribution_partner" | "dealer";

export interface OrderEntry {
  visitId: string;
  outletId: string;
  manufacturerId: string;
  sellerId?: string;
}

export type {
  CatalogProductOut,
  CatalogResponse,
  EsiRecordOut,
  OrderContextResponse,
  OrderDetailOut,
  OrderLineOut,
  OrderSummaryOut,
  OutletSellerOut,
  OutletSellersByBrandOut,
  OutletSellersResponse,
  PurchaseOrderOut,
  SellerOut,
  ServiceableDistrictOut,
  ServiceableStateOut,
  ShippingAddressOverride,
  ShipToOptionOut,
} from "@humbee/api-contract";

export type CartResponse = ContractCartResponse & {
  outlet_esi_id?: string | null;
  seller_esi_id?: string | null;
  ship_to_esi_id?: string | null;
};

export type PatchCartBody = ContractPatchCartBody & {
  outlet_esi_id?: string | null;
  seller_esi_id?: string | null;
};

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

export const ordersService = {
  async list(
    input: { status?: string; cursor?: string; limit?: number } = {},
    signal?: AbortSignal,
  ): Promise<OrderListResponse> {
    const status = input.status === "awaiting_approval" ? "pending_approval" : input.status;
    return unwrap(await listOrdersApiV1OrdersGet({
      client: getBrowserApiClient(),
      query: {
        status: status || undefined,
        cursor: input.cursor || undefined,
        limit: input.limit ?? 20,
      },
      signal,
      throwOnError: true,
    }));
  },

  async detail(orderId: string, signal?: AbortSignal): Promise<OrderDetailOut> {
    return unwrap(await getOrderApiV1OrdersOrderIdGet({
      client: getBrowserApiClient(),
      path: { order_id: orderId },
      signal,
      throwOnError: true,
    }));
  },

  async outletSellers(outletId: string, signal?: AbortSignal): Promise<OutletSellersResponse> {
    return unwrap(await getOutletSellersApiV1OutletsOutletIdSellersGet({
      client: getBrowserApiClient(),
      path: { outlet_id: outletId },
      signal,
      throwOnError: true,
    }));
  },

  async context(
    entry: OrderEntry,
    signal?: AbortSignal,
    outletEsiId?: string,
  ): Promise<OrderContextResponse> {
    return unwrap(await getOrderContextApiV1OrdersContextGet({
      client: getBrowserApiClient(),
      query: {
        visit_id: entry.visitId,
        outlet_id: entry.outletId,
        manufacturer_id: entry.manufacturerId,
        seller_id: entry.sellerId,
        outlet_esi_id: outletEsiId || undefined,
      },
      signal,
      throwOnError: true,
    }));
  },

  async createCart(entry: OrderEntry, idempotencyKey = createIdempotencyKey()): Promise<CartResponse> {
    return unwrap(await createCartApiV1CartsPost({
      client: getBrowserApiClient(),
      body: {
        visit_id: entry.visitId,
        outlet_id: entry.outletId,
        manufacturer_id: entry.manufacturerId,
        seller_id: entry.sellerId,
      },
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },

  async cart(cartId: string, signal?: AbortSignal): Promise<CartResponse> {
    return unwrap(await getCartApiV1CartsCartIdGet({
      client: getBrowserApiClient(),
      path: { cart_id: cartId },
      signal,
      throwOnError: true,
    }));
  },

  async patchCart(
    cartId: string,
    body: PatchCartBody,
    idempotencyKey: string,
  ): Promise<CartResponse> {
    return unwrap(await patchCartApiV1CartsCartIdPatch({
      client: getBrowserApiClient(),
      path: { cart_id: cartId },
      body,
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },

  async catalog(
    cartId: string,
    input: { query?: string; category?: string } = {},
    signal?: AbortSignal,
  ): Promise<CatalogResponse> {
    return unwrap(await getCatalogApiV1OrdersCatalogGet({
      client: getBrowserApiClient(),
      query: {
        cart_id: cartId,
        q: input.query || undefined,
        category: input.category && input.category !== "All"
          ? input.category
          : undefined,
      },
      signal,
      throwOnError: true,
    }));
  },

  async purchaseOrders(
    outletId: string,
    manufacturerId: string,
    _sellerId: string,
    outletEsiId: string,
    signal?: AbortSignal,
  ): Promise<PurchaseOrdersResponse> {
    return unwrap(await getPurchaseOrdersApiV1OrdersPurchaseOrdersGet({
      client: getBrowserApiClient(),
      query: {
        outlet_id: outletId,
        manufacturer_id: manufacturerId,
        outlet_esi_id: outletEsiId,
      },
      signal,
      throwOnError: true,
    }));
  },

  async serviceableStates(
    manufacturerId: string,
    signal?: AbortSignal,
  ): Promise<ServiceableStatesResponse> {
    return unwrap(await getServiceableStatesApiV1OrdersServiceableStatesGet({
      client: getBrowserApiClient(),
      query: { manufacturer_id: manufacturerId },
      signal,
      throwOnError: true,
    }));
  },

  async serviceableDistricts(
    manufacturerId: string,
    stateId: string,
    signal?: AbortSignal,
  ): Promise<ServiceableDistrictsResponse> {
    return unwrap(await getServiceableDistrictsApiV1OrdersServiceableDistrictsGet({
      client: getBrowserApiClient(),
      query: {
        manufacturer_id: manufacturerId,
        state_id: stateId,
      },
      signal,
      throwOnError: true,
    }));
  },

  async shipToAddressOptions(
    districtId: string,
    signal?: AbortSignal,
  ): Promise<FirmAddressOptionsResponse> {
    return unwrap(await firmAddressOptionsApiV1OutletsOnboardingAddressOptionsGet({
      client: getBrowserApiClient(),
      query: { district_id: districtId },
      signal,
      throwOnError: true,
    }));
  },

  async upsertLines(
    cartId: string,
    lines: Array<{
      productId: string;
      quantity: number;
      formType?: "STRAIGHT" | "BEND" | null;
    }>,
    idempotencyKey: string,
  ): Promise<CartResponse> {
    return unwrap(await upsertLineApiV1CartsCartIdLinesPut({
      client: getBrowserApiClient(),
      path: { cart_id: cartId },
      body: {
        lines: lines.map((line) => ({
          product_id: line.productId,
          qty: line.quantity,
          form_type: line.formType ?? null,
        })),
      },
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },

  async submit(cartId: string, idempotencyKey: string): Promise<OrderDetailOut> {
    return unwrap(await submitOrderApiV1OrdersPost({
      client: getBrowserApiClient(),
      body: { cart_id: cartId, occurred_at: new Date().toISOString() },
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },

  async retry(orderId: string, idempotencyKey: string): Promise<OrderDetailOut> {
    return unwrap(await retrySubmissionApiV1OrdersOrderIdRetrySubmissionPost({
      client: getBrowserApiClient(),
      path: { order_id: orderId },
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },
};

export function partnerIcon(role: PartnerRole) {
  if (role === "dealer") return "HomeOutlined";
  if (role === "distribution_partner") return "DispatchPlanOutlined";
  return "InventoryOutlined";
}
