"use client";

import {
  Button,
  EmptyState,
  ErrorState,
  Icon,
  ListRow,
  Select,
  StatusChip,
  TextField,
} from "humbee-design-system";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { ApiClientError, createIdempotencyKey } from "@/src/shared/api";
import { useConnectivity } from "@/src/shared/capabilities";
import { SEARCH_API_DEBOUNCE_MS, useDebouncedSearchQuery, useInfiniteScrollTrigger } from "@/src/shared/state";
import {
  SpCard,
  SpInlineAlert,
  SpProcessProgress,
  SpScreen,
  SpSectionLabel,
  SpStatusRow,
  SpStickyFooter,
} from "@/src/features/shell/components";
import { SpPageSkeleton } from "@/src/features/shell/loading";
import {
  newMutationKey,
  orderKeys,
  useCart,
  useCatalog,
  useAutoSkip,
  useCreateCart,
  useOrder,
  useOrderContext,
  useOrders,
  useOutletSellers,
  usePatchCart,
  usePatchCartById,
  usePurchaseOrders,
  useRecoverIdlePendingQuery,
  useServiceableDistricts,
  useServiceableStates,
  useShipToAddressOptions,
  useRetryOrder,
  useSubmitOrder,
  useUpsertCartLine,
} from "./hooks";
import { useOrderDraft } from "./order-draft";
import { ordersService } from "./service";
import {
  formatFormTypeLabel,
  OrderPriceSummaryCard,
  OrderSummarySections,
  mapOrderDetailSummaryLine,
  SchemeAppliedBanner,
  sharedGstRateBp,
} from "./order-summary-ui";
import type {
  CartResponse,
  CatalogProductOut,
  EsiRecordOut,
  OrderDetailOut,
  OrderContextResponse,
  OrderEntry,
  OrderSummaryOut,
  OutletSellerOut,
  PatchCartBody,
  SellerOut,
  ShipToOptionOut,
  ShippingAddressOverride,
} from "./service";

const money = (paise: number) =>
  `₹ ${(paise / 100).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}`;

const basisPointAmount = (paise: number, basisPoints: number) =>
  Math.round((paise * basisPoints) / 10_000);
type LineFormType = "STRAIGHT" | "BEND" | "";

function normalizeLineFormType(value: string | null | undefined): LineFormType {
  if (value === "STRAIGHT" || value === "BEND") return value;
  return "";
}

function resolvedRequiredFormType(value: LineFormType | undefined): "STRAIGHT" | "BEND" {
  return value === "BEND" ? "BEND" : "STRAIGHT";
}

const FORM_TYPE_OPTIONS = [
  { value: "STRAIGHT", label: "Straight" },
  { value: "BEND", label: "Bend" },
] as const;

function FormTypeSelect({
  value,
  onChange,
}: {
  value: "STRAIGHT" | "BEND";
  onChange: (value: "STRAIGHT" | "BEND") => void;
}) {
  const [open, setOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0, width: 132, openUp: false });
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const updateMenuPosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const width = Math.max(rect.width, 132);
    const menuHeight = 88;
    const spaceBelow = window.innerHeight - rect.bottom - 8;
    const openUp = spaceBelow < menuHeight && rect.top > spaceBelow;
    setMenuPosition({
      top: openUp ? Math.max(8, rect.top - menuHeight - 4) : rect.bottom + 4,
      left: Math.min(Math.max(8, rect.left), window.innerWidth - width - 8),
      width,
      openUp,
    });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    updateMenuPosition();
    const close = (event: MouseEvent) => {
      const target = event.target as Node;
      if (rootRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, updateMenuPosition]);

  const selectedLabel = value === "BEND" ? "Bend" : "Straight";

  return (
    <div className="sp-order-form-type" data-open={open ? "true" : "false"} ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className="sp-order-form-type__trigger"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={`Form type: ${selectedLabel}`}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{selectedLabel}</span>
        <Icon name="KeyboardArrowDown" size={14} color="currentColor" />
      </button>
      {open ? createPortal(
        <div
          ref={menuRef}
          className="sp-order-form-type__menu"
          data-open-up={menuPosition.openUp ? "true" : "false"}
          role="listbox"
          aria-label="Form type"
          style={{ top: menuPosition.top, left: menuPosition.left, minWidth: menuPosition.width }}
        >
          {FORM_TYPE_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              role="option"
              aria-selected={option.value === value}
              className="sp-order-form-type__option"
              data-selected={option.value === value ? "true" : "false"}
              onClick={() => {
                onChange(option.value);
                setOpen(false);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>,
        document.body,
      ) : null}
    </div>
  );
}

function discountedUnitNetPaise(
  unitPriceNetPaise: number | null | undefined,
  discountRateBp: number,
) {
  if (unitPriceNetPaise == null) return null;
  if (discountRateBp <= 0) return unitPriceNetPaise;
  const discount = basisPointAmount(unitPriceNetPaise, discountRateBp);
  return unitPriceNetPaise - discount;
}

function unitPriceInclGstPaise(netPaise: number | null, gstRateBp: number) {
  if (netPaise == null) return null;
  return netPaise + basisPointAmount(netPaise, gstRateBp);
}

function productUnitDiscountedNetPaise(product: CatalogProductOut) {
  return discountedUnitNetPaise(product.unit_price_net_paise, product.discount_rate_bp);
}

function unitPriceWithDiscountLabel(
  unitPriceNetPaise: number | null | undefined,
  discountRateBp: number,
  gstRateBp: number,
) {
  const grossPrice = unitPriceInclGstPaise(
    discountedUnitNetPaise(unitPriceNetPaise, discountRateBp), gstRateBp,
  );
  if (grossPrice == null) return "—";
  if (discountRateBp <= 0 || unitPriceNetPaise == null) {
    return money(grossPrice);
  }
  const oldGrossPrice = unitPriceInclGstPaise(unitPriceNetPaise, gstRateBp)!;
  return (
    <>
      <s className="sp-order-product-price-old">{money(oldGrossPrice)}</s>
      {" "}
      {money(grossPrice)}
    </>
  );
}

function productNetPriceLabel(product: CatalogProductOut) {
  return unitPriceWithDiscountLabel(
    product.unit_price_net_paise, product.discount_rate_bp, product.gst_rate_bp,
  );
}

type CartPricedLine = {
  line: { product_id: string; unit_price_net_paise: number | null; qty: number };
  product?: Pick<CatalogProductOut, "discount_rate_bp" | "gst_rate_bp" | "name"> | null;
};

function lineListNetPaise(line: { unit_price_net_paise: number | null; qty: number }) {
  if (line.unit_price_net_paise == null) return 0;
  return line.unit_price_net_paise * line.qty;
}

function lineProductDiscountPaise(
  line: { unit_price_net_paise: number | null; qty: number },
  discountRateBp: number,
) {
  if (line.unit_price_net_paise == null || discountRateBp <= 0) return 0;
  return basisPointAmount(line.unit_price_net_paise, discountRateBp) * line.qty;
}

function cartProductDiscountPaise(lines: CartPricedLine[]) {
  return lines.reduce(
    (total, { line, product }) => total + lineProductDiscountPaise(line, product?.discount_rate_bp ?? 0),
    0,
  );
}

function apportionPaise(total: number, weights: number[]) {
  const weightSum = weights.reduce((sum, weight) => sum + weight, 0);
  if (total <= 0 || weightSum <= 0) return weights.map(() => 0);
  const shares = weights.map((weight) => Math.floor((total * weight) / weightSum));
  let remainder = total - shares.reduce((sum, share) => sum + share, 0);
  const order = weights
    .map((weight, index) => ({ index, remainder: (total * weight) % weightSum }))
    .sort((left, right) => right.remainder - left.remainder);
  for (const { index } of order) {
    if (remainder <= 0) break;
    const current = shares[index] ?? 0;
    shares[index] = current + 1;
    remainder -= 1;
  }
  return shares;
}

function cartDisplayPriceSummary(
  lines: CartPricedLine[],
  schemeDiscountPaise: number,
  itemCount: number,
  pricedAsOf?: string | null,
) {
  const priced = lines.filter(({ line }) => line.unit_price_net_paise != null);
  const subtotalPaise = priced.reduce((sum, { line }) => sum + lineListNetPaise(line), 0);
  const productDiscountPaise = cartProductDiscountPaise(priced);
  const discountedNets = priced.map(({ line, product }) => (
    lineListNetPaise(line) - lineProductDiscountPaise(line, product?.discount_rate_bp ?? 0)
  ));
  const discountedSubtotal = discountedNets.reduce((sum, net) => sum + net, 0);
  const scheme = Math.min(Math.max(0, schemeDiscountPaise), discountedSubtotal);
  const schemeShares = apportionPaise(scheme, discountedNets);
  let gstPaise = 0;
  const lineTotalsByProductId = new Map<string, number>();
  priced.forEach(({ line, product }, index) => {
    const taxable = (discountedNets[index] ?? 0) - (schemeShares[index] ?? 0);
    const gstRateBp = product?.gst_rate_bp ?? 0;
    const lineGst = basisPointAmount(taxable, gstRateBp);
    gstPaise += lineGst;
    lineTotalsByProductId.set(line.product_id, taxable + lineGst);
  });
  const taxableBasePaise = subtotalPaise - productDiscountPaise - scheme;
  return {
    itemCount,
    subtotalPaise,
    productDiscountPaise,
    schemeDiscountPaise: scheme,
    gstPaise,
    gstRateBp: sharedGstRateBp(priced.map(({ product }) => product?.gst_rate_bp)),
    totalPaise: taxableBasePaise + gstPaise,
    pricedAsOf,
    lineTotalsByProductId,
  };
}

function cartDiscountBanner(
  lines: CartPricedLine[],
  productDiscountPaise: number,
  schemeLabel: string | null | undefined,
  schemeDiscountPaise: number,
) {
  if (schemeDiscountPaise > 0 && schemeLabel) {
    return { label: schemeLabel, discountPaise: schemeDiscountPaise };
  }
  if (productDiscountPaise <= 0) return { label: null, discountPaise: 0 };
  const discounted = lines.filter(({ line, product }) => (
    line.unit_price_net_paise != null && (product?.discount_rate_bp ?? 0) > 0
  ));
  const discountedProduct = discounted.length === 1 ? discounted[0] : undefined;
  if (discountedProduct) {
    return {
      label: `Discount applied: ${discountedProduct.product?.name ?? "item"} — ${money(productDiscountPaise)} off`,
      discountPaise: productDiscountPaise,
    };
  }
  return {
    label: `Discount applied: ${money(productDiscountPaise)} off`,
    discountPaise: productDiscountPaise,
  };
}

function productUnitLabel(product: Pick<CatalogProductOut, "pack_size" | "uom"> | null | undefined) {
  const unit = product?.pack_size ?? product?.uom ?? "";
  const normalized = unit.trim();
  return normalized || null;
}

function reviewLineSubtitle(
  product: Pick<CatalogProductOut, "pack_size" | "uom"> | null | undefined,
  formType: "STRAIGHT" | "BEND" | null | undefined,
  qty: number,
) {
  const formTypeLabel = formatFormTypeLabel(formType);
  const subtitle = [
    `Quantity: ${qty}`,
    productUnitLabel(product) ? `Unit: ${productUnitLabel(product)}` : "",
    formTypeLabel ? `Form: ${formTypeLabel}` : "",
  ].filter(Boolean).join(" · ");
  return subtitle || undefined;
}

function CatalogProductImage({
  imageUrl,
  productName,
}: {
  imageUrl: string | null;
  productName: string;
}) {
  const [loadFailed, setLoadFailed] = useState(false);
  const normalizedUrl = imageUrl?.trim() ?? "";
  const [attemptedUrl, setAttemptedUrl] = useState(normalizedUrl);
  if (attemptedUrl !== normalizedUrl) {
    setAttemptedUrl(normalizedUrl);
    setLoadFailed(false);
  }

  if (!normalizedUrl || loadFailed) {
    return <Icon name="Image" size={22} color="var(--color-text-disabled)" />;
  }

  return (
    <img
      src={normalizedUrl}
      alt={productName}
      className="sp-product-image-thumb"
      loading="lazy"
      decoding="async"
      onError={() => setLoadFailed(true)}
    />
  );
}


function isPoBackedPath(path: string | null | undefined) {
  return path === "po_backed" || path === "distribution_partner";
}

function isAwaitingApprovalStatus(status: string) {
  return status === "pending_approval" || status === "awaiting_approval";
}

function errorMessage(error: unknown) {
  if (error instanceof ApiClientError) return error.message;
  return "Something went wrong. Try again.";
}

export function statusLabel(status: string) {
  const labels: Record<string, string> = {
    submitted: "Submitted",
    pending_approval: "Pending approval",
    awaiting_approval: "Pending approval",
    approved: "Approved",
    approved_with_edits: "Approved with edits",
    rejected: "Rejected",
    dp_creation_pending: "Registration pending",
    dp_created: "Order created",
    submission_failed: "Order failed",
    cancelled: "Cancelled",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

export function statusChip(status: string) {
  if (status === "dp_created") return "verified";
  if (status === "rejected" || status === "cancelled") return "cancelled";
  if (status === "submission_failed") return "not-verified";
  if (status === "approved_with_edits") return "partially-completed";
  if (status === "approved") return "approved";
  return "pending";
}

function approvedLineQuantity(line: OrderDetailOut["lines"][number]) {
  return line.approved_qty ?? line.requested_qty;
}

type OrderFlowStep =
  | "manufacturer"
  | "start"
  | "esi"
  | "shipTo"
  | "po"
  | "products"
  | "cart"
  | "review";

const ORDER_FLOW_STEP_LABEL: Record<OrderFlowStep, string> = {
  manufacturer: "Choose manufacturer",
  start: "Verify order context",
  esi: "Select SAP",
  shipTo: "Shipping setup",
  po: "Select purchase order",
  products: "Add products",
  cart: "Review cart",
  review: "Submit order",
};

function orderFlowSteps({
  includesManufacturer = false,
  requiresPoStep = false,
}: {
  includesManufacturer?: boolean;
  requiresPoStep?: boolean;
}) {
  const steps: OrderFlowStep[] = ["start", "esi", "shipTo", "products", "cart", "review"];
  if (requiresPoStep) steps.splice(2, 0, "po");
  if (includesManufacturer) steps.unshift("manufacturer");
  return steps;
}

function sellerRequiresPo(seller: { requires_purchase_order: boolean } | undefined) {
  return Boolean(seller?.requires_purchase_order);
}

function orderFlowProgress(
  currentStep: OrderFlowStep,
  {
    includesManufacturer = false,
    requiresPoStep = false,
  }: {
    includesManufacturer?: boolean;
    requiresPoStep?: boolean;
  },
) {
  const steps = orderFlowSteps({ includesManufacturer, requiresPoStep });
  if (!steps.includes(currentStep)) steps.push(currentStep);
  const currentIndex = Math.max(0, steps.indexOf(currentStep));
  const current = currentIndex + 1;
  const total = steps.length;
  return {
    steps,
    currentIndex,
    current,
    total,
  };
}

function OrderFlowToolbar({
  step,
  includesManufacturer,
  requiresPoStep,
}: {
  step: OrderFlowStep;
  includesManufacturer?: boolean;
  requiresPoStep?: boolean;
}) {
  const progress = orderFlowProgress(step, { includesManufacturer, requiresPoStep });
  return (
    <SpProcessProgress
      layout="toolbar"
      steps={progress.steps.map((flowStep) => ORDER_FLOW_STEP_LABEL[flowStep])}
      activeStep={progress.currentIndex}
    />
  );
}

function orderStatePane(
  content: ReactNode,
  { loading = false }: { loading?: boolean } = {},
) {
  return (
    <div className={`sp-order-state-pane${loading ? " sp-order-state-pane--loading" : ""}`}>
      {content}
    </div>
  );
}

function loadingScreen(
  title: string,
  {
    toolbar,
    back = true,
    bell = false,
  }: {
    toolbar?: ReactNode;
    back?: boolean;
    bell?: boolean;
  } = {},
) {
  return (
    <SpScreen title={title} back={back} bell={bell} toolbar={toolbar}>
      {orderStatePane(
        <SpPageSkeleton className="sp-stack" rows={2} style={{ width: "100%" }} />,
        { loading: true },
      )}
    </SpScreen>
  );
}

function stepAutoSkipTransitionScreen({
  title,
  message,
  toolbar,
}: {
  title: string;
  message: string;
  toolbar?: ReactNode;
}) {
  return (
    <SpScreen title={title} back toolbar={toolbar}>
      {orderStatePane(
        <div className="sp-stack">
          <SpInlineAlert>{message}</SpInlineAlert>
          <SpPageSkeleton className="sp-stack" rows={2} style={{ width: "100%" }} />
        </div>,
        { loading: true },
      )}
    </SpScreen>
  );
}

function BlockedEntry({ title }: { title: string }) {
  const router = useRouter();
  return (
    <SpScreen title={title} back>
      {orderStatePane(
        <EmptyState
          icon="ShoppingCartOutlined"
          title="Open this order from an active visit"
          message="The visit, outlet, and supplier context is required before a server cart can be created."
          actionLabel="Go to route"
          onAction={() => router.push("/sp/route")}
        />,
      )}
    </SpScreen>
  );
}

function sameEntry(left: OrderEntry | null, right: OrderEntry | null) {
  return Boolean(left && right
    && left.visitId === right.visitId
    && left.outletId === right.outletId
    && left.manufacturerId === right.manufacturerId
    && left.sellerId === right.sellerId);
}

function findOutletSeller(
  brands: Array<{ brand_id: string; sellers: OutletSellerOut[] }>,
  manufacturerId: string,
  sellerId?: string,
) {
  if (!sellerId) return undefined;
  return findBrandByManufacturerId(brands, manufacturerId)
    ?.sellers.find((seller) => seller.seller_id === sellerId)
    ?? brands.flatMap((brand) => brand.sellers).find((seller) => seller.seller_id === sellerId);
}

function findBrandByManufacturerId<T extends {
  brand_id: string;
  sellers: Array<{ seller_id: string; seller_type: string }>;
}>(
  brands: T[],
  manufacturerId: string,
) {
  return brands.find((brand) =>
    brand.brand_id === manufacturerId
    || brand.sellers.some((seller) => seller.seller_id === manufacturerId));
}

function manufacturerIdForBrandOrder(brand: {
  brand_id: string;
}) {
  return brand.brand_id;
}

function sellerIdForBrandOrder(brand: {
  sellers: Array<{ seller_id: string }>;
}) {
  return brand.sellers.length === 1
    ? brand.sellers[0]?.seller_id ?? undefined
    : undefined;
}

function manufacturerIdForSelectedSeller(
  currentManufacturerId: string,
  _seller: { seller_id: string; seller_type: string } | undefined,
  brand: {
    brand_id: string;
    sellers: Array<{ seller_id: string; seller_type: string }>;
  } | undefined,
) {
  if (brand) return brand.brand_id;
  return currentManufacturerId;
}

function resolveOrderEntry(
  entry: OrderEntry | null,
  cachedSellers: Array<{ seller_id: string; seller_type: string }>,
  brand: {
    brand_id: string;
    sellers: Array<{ seller_id: string; seller_type: string }>;
  } | undefined,
  contextSellerId = "",
): OrderEntry | null {
  if (!entry) return null;
  if (entry.sellerId) return entry;
  const resolvedSellerId = cachedSellers.length === 1
    ? cachedSellers[0]?.seller_id
    : contextSellerId || undefined;
  if (!resolvedSellerId) return entry;
  const seller = cachedSellers.find((item) => item.seller_id === resolvedSellerId);
  return {
    ...entry,
    manufacturerId: manufacturerIdForSelectedSeller(
      entry.manufacturerId,
      seller,
      brand,
    ),
    sellerId: resolvedSellerId,
  };
}

function orderPathFromContext(
  cart: CartResponse | undefined,
  context: OrderContextResponse | undefined,
  selectedSeller: { requires_purchase_order: boolean } | undefined,
) {
  return cart?.order_path
    ?? context?.order_path
    ?? (selectedSeller?.requires_purchase_order ? "po_backed" : selectedSeller ? "direct" : null);
}

interface SubmitErrorDetails {
  gross_total_paise?: unknown;
}

interface SubmitErrorMeta {
  message: string;
  actionLabel: string | null;
  actionPath: string | null;
}

function submitErrorMeta(error: unknown): SubmitErrorMeta {
  if (!(error instanceof ApiClientError)) {
    return {
      message: errorMessage(error),
      actionLabel: null,
      actionPath: null,
    };
  }
  const details = (
    typeof error.details === "object" && error.details !== null
      ? error.details as SubmitErrorDetails
      : null
  );
  if (error.code === "classification_changed") {
    return {
      message: "Order routing changed before submit. Review the order context again.",
      actionLabel: "Review start order",
      actionPath: "/sp/orders/new",
    };
  }
  if (error.code === "price_changed") {
    const nextTotal = typeof details?.gross_total_paise === "number"
      ? ` Updated total: ${money(details.gross_total_paise)}.`
      : "";
    return {
      message: `Product pricing changed before submit.${nextTotal}`,
      actionLabel: "Review cart",
      actionPath: "/sp/orders/new/cart",
    };
  }
  if (error.code === "po_no_longer_open") {
    return {
      message: "The selected purchase order is no longer open.",
      actionLabel: "Select another PO",
      actionPath: "/sp/orders/new/po",
    };
  }
  if (error.code === "cart_changed" || error.code === "cart_not_open") {
    return {
      message: "Cart changed during review. Refresh and submit again.",
      actionLabel: "Review cart",
      actionPath: "/sp/orders/new/cart",
    };
  }
  return {
    message: error.message,
    actionLabel: null,
    actionPath: null,
  };
}

function esiLabel(record: EsiRecordOut) {
  return record.esi_code
    ? `${record.esi_code}`
    : record.esi_id;
}

function shipToOptionValue(option: ShipToOptionOut) {
  return `${option.party_id}:${option.esi_id}`;
}

function shipToValueFromCart(
  cart: CartResponse | undefined,
  shipToOptions: ShipToOptionOut[],
) {
  if (cart?.ship_to_type === "dealer" && cart.ship_to_outlet_id && cart.ship_to_esi_id) {
    const option = shipToOptions.find(
      (item) => item.party_id === cart.ship_to_outlet_id && item.esi_id === cart.ship_to_esi_id,
    );
    if (option) return shipToOptionValue(option);
    return `${cart.ship_to_outlet_id}:${cart.ship_to_esi_id}`;
  }
  if (cart?.ship_to_type === "dealer" && cart.ship_to_outlet_id) {
    const option = shipToOptions.find((item) => item.party_id === cart.ship_to_outlet_id);
    if (option) return shipToOptionValue(option);
  }
  return "self";
}

function normalizeShippingOverride(
  override: ShippingAddressOverride | null | undefined,
) {
  if (!override) return null;
  return {
    line1: override.line1,
    line2: override.line2 ?? "",
    stateId: override.state_id,
    districtId: override.district_id,
    pincode: override.pincode,
  };
}

function useResolvedEntry(routeEntry?: OrderEntry | null) {
  const draft = useOrderDraft();
  useEffect(() => {
    if (routeEntry && !sameEntry(draft.entry, routeEntry)) {
      draft.configureEntry(routeEntry);
    }
  }, [draft, routeEntry]);
  return {
    ...draft,
    entry: routeEntry ?? draft.entry,
    cartId: routeEntry && !sameEntry(draft.entry, routeEntry)
      ? ""
      : draft.cartId,
  };
}

type StartOrderBootstrapState =
  | { phase: "loading" }
  | { phase: "pick-seller"; sellers: SellerOut[]; brandName: string }
  | { phase: "blocked"; title: string; message: string }
  | { phase: "error"; message: string };

function DraftCartLineControl({
  product,
  quantity,
  disabled,
  canIncrement = true,
  onChange,
}: {
  product: CatalogProductOut;
  quantity: number;
  disabled: boolean;
  canIncrement?: boolean;
  onChange: (quantity: number) => void;
}) {
  const step = 1;
  const [draftText, setDraftText] = useState<string | null>(null);
  const commitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (commitTimerRef.current) clearTimeout(commitTimerRef.current);
  }, []);
  const change = (nextQuantity: number) => {
    if (disabled) return;
    onChange(Math.max(0, nextQuantity));
  };
  const commitDraft = (digits: string) => {
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
      commitTimerRef.current = null;
    }
    change(digits === "" ? 0 : Number(digits));
  };
  const changeFromInput = (raw: string) => {
    const digits = raw.replace(/\D/g, "").slice(0, 3);
    setDraftText(digits);
    if (commitTimerRef.current) clearTimeout(commitTimerRef.current);
    commitTimerRef.current = setTimeout(() => commitDraft(digits), SEARCH_API_DEBOUNCE_MS);
  };
  const handleBlur = () => {
    if (draftText !== null) commitDraft(draftText);
    setDraftText(null);
  };
  if (!quantity && draftText === null) {
    return (
      <Button
        variant="outlined"
        color="primary"
        size="small"
        disabled={disabled || !canIncrement}
        label="Add"
        onClick={() => change(step)}
      />
    );
  }
  return (
    <div className="sp-mini-stepper" aria-label={`${product.name} quantity`}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => change(quantity - step)}
      >
        <Icon name="Minus" size={18} color="currentColor" />
      </button>
      <input
        className="sp-mini-stepper-input"
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={3}
        value={draftText ?? String(quantity)}
        disabled={disabled}
        aria-label={`${product.name} quantity`}
        onFocus={() => setDraftText(String(quantity))}
        onChange={(event) => changeFromInput(event.target.value)}
        onBlur={handleBlur}
      />
      <button
        type="button"
        disabled={disabled || !canIncrement}
        onClick={() => change(quantity + step)}
      >
        <Icon name="Add" size={18} color="currentColor" />
      </button>
    </div>
  );
}

function CartLineControl({
  cartId,
  product,
  formType,
  canIncrement,
}: {
  cartId: string;
  product: CatalogProductOut;
  formType?: "STRAIGHT" | "BEND" | null;
  canIncrement?: boolean;
}) {
  const update = useUpsertCartLine(cartId);
  const change = (quantity: number) => {
    if (update.isPending) return;
    const nextQuantity = Math.max(0, quantity);
    update.mutate({
      lines: [{
        productId: product.product_id,
        quantity: nextQuantity,
        formType: nextQuantity > 0 ? (formType ?? null) : null,
      }],
      idempotencyKey: newMutationKey(),
    });
  };
  return (
    <DraftCartLineControl
      product={product}
      quantity={product.qty_in_cart}
      disabled={update.isPending}
      canIncrement={canIncrement}
      onChange={change}
    />
  );
}

export function ManufacturerScreen() {
  const router = useRouter();
  const draft = useResolvedEntry();
  const brandChoices = useMemo(
    () => draft.sellerBrands.map((brand) => ({
      ...brand,
      sellers: brand.sellers.filter((seller) => seller.is_active),
    })),
    [draft.sellerBrands],
  );
  const hasOrderableBrand = brandChoices.some((brand) => brand.sellers.length > 0);
  const flowToolbar = (
    <OrderFlowToolbar
      step="manufacturer"
      includesManufacturer
      requiresPoStep={brandChoices.some((brand) => brand.sellers.some((seller) => seller.requires_purchase_order))}
    />
  );
  if (!draft.activeVisitStopId || !draft.activeVisitOutletId || !brandChoices.length) {
    return <BlockedEntry title="Choose manufacturer" />;
  }
  return (
    <SpScreen title="Choose manufacturer" back toolbar={flowToolbar}>
      <div className="sp-content sp-order-flow-content sp-order-motion-stack">
        <SpInlineAlert>
          Choose a manufacturer to continue. Seller routing and PO checks are applied on the next step.
        </SpInlineAlert>
        <SpCard>
          <div className="sp-po-list">
            {brandChoices.map((brand) => {
              const disabled = !brand.sellers.length;
              return (
                <button
                  className="sp-po-option"
                  key={brand.brand_id}
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    if (disabled) return;
                    draft.restartOrderEntry({
                      visitId: draft.activeVisitStopId,
                      outletId: draft.activeVisitOutletId,
                      manufacturerId: manufacturerIdForBrandOrder(brand),
                      sellerId: sellerIdForBrandOrder(brand),
                    });
                    router.push("/sp/orders/new");
                  }}
                >
                  <Icon name="InventoryOutlined" size={22} color="currentColor" />
                  <span className="sp-po-copy">
                    <strong>{brand.brand_name}</strong>
                    <span>
                      {[
                        brand.sellers.length
                          ? `${brand.sellers.length} active seller${brand.sellers.length === 1 ? "" : "s"}`
                          : "No active sellers linked",
                        brand.sellers.some((seller) => seller.requires_purchase_order)
                          ? "PO path available"
                          : "Direct path",
                      ].join(" · ")}
                    </span>
                  </span>
                  <span className="sp-po-value">
                    <small>{brand.sellers.some((seller) => seller.manager_approval_required) ? "Approval path" : "Direct path"}</small>
                  </span>
                </button>
              );
            })}
          </div>
        </SpCard>
        {!hasOrderableBrand ? (
          <SpInlineAlert tone="warning">
            No brands are currently orderable because no active sellers are linked.
          </SpInlineAlert>
        ) : null}
      </div>
    </SpScreen>
  );
}

function SellerSelectionScreen({
  sellers,
  onSelect,
  toolbar,
}: {
  sellers: SellerOut[];
  onSelect: (sellerId: string) => void;
  toolbar?: ReactNode;
}) {
  const [search, setSearch] = useState("");
  const searchTerm = search.trim().toLowerCase();
  const filteredSellers = useMemo(
    () => sellers.filter((seller) => {
      if (!searchTerm) return true;
      const sellerType = seller.seller_type.replaceAll("_", " ").toLowerCase();
      return seller.name.toLowerCase().includes(searchTerm) || sellerType.includes(searchTerm);
    }),
    [searchTerm, sellers],
  );

  return (
    <SpScreen title="Choose seller" back toolbar={toolbar}>
      <div className="sp-content sp-order-flow-content sp-order-motion-stack">
        <SpInlineAlert>Select the seller for this order context before the cart is created.</SpInlineAlert>
        <TextField
          placeholder="Search sellers"
          startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
          value={search}
          onChange={(event) => setSearch((event.target as HTMLInputElement).value)}
        />
        <p className="sp-meta">{filteredSellers.length} seller{filteredSellers.length === 1 ? "" : "s"} available</p>
        <SpCard padded={false}>
          <div className="sp-list">
            {filteredSellers.map((seller) => (
              <ListRow
                key={seller.seller_id}
                leading={<Icon name="InventoryOutlined" size={22} color="var(--color-primary)" />}
                title={seller.name}
                subtitle={[seller.seller_type.replaceAll("_", " "), seller.requires_purchase_order ? "PO required" : "Direct", seller.manager_approval_required ? "Manager approval" : "No approval"].join(" · ")}
                showChevron
                onClick={() => onSelect(seller.seller_id)}
              />
            ))}
          </div>
        </SpCard>
        {!filteredSellers.length ? (
          <SpInlineAlert tone="warning">No sellers match your search. Try another seller name.</SpInlineAlert>
        ) : null}
      </div>
    </SpScreen>
  );
}

export function StartOrderScreen({ entry: routeEntry }: { entry?: OrderEntry | null }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const draft = useResolvedEntry(routeEntry);
  const [bootstrapState, setBootstrapState] = useState<StartOrderBootstrapState>({ phase: "loading" });
  const [retryCount, setRetryCount] = useState(0);
  const [sellerBrands, setSellerBrands] = useState(draft.sellerBrands);
  const includesManufacturer = sellerBrands.length > 1;
  const flowToolbar = (
    <OrderFlowToolbar
      step="start"
      includesManufacturer={includesManufacturer}
      requiresPoStep={sellerBrands.some((brand) =>
        brand.sellers.some((seller) => seller.is_active && seller.requires_purchase_order),
      )}
    />
  );

  const entry = draft.entry;
  const [bootstrapEntry, setBootstrapEntry] = useState(entry);
  if (bootstrapEntry !== entry) {
    setBootstrapEntry(entry);
    if (entry) setBootstrapState({ phase: "loading" });
  }
  const entryKey = entry
    ? [
      entry.visitId,
      entry.outletId,
      entry.manufacturerId,
      entry.sellerId ?? "",
    ].join(":")
    : "";

  useEffect(() => {
    if (!entry) return;

    let cancelled = false;
    const controller = new AbortController();

    void (async () => {
      try {
        if (draft.cartId && entry.sellerId) {
          router.replace("/sp/orders/new/esi");
          return;
        }

        const outletSellers = await ordersService.outletSellers(entry.outletId, controller.signal);
        if (cancelled) return;

        const brands = outletSellers.sellers_by_brand;
        setSellerBrands(brands);
        const selectedBrand = findBrandByManufacturerId(brands, entry.manufacturerId);
        const activeSellers = (selectedBrand?.sellers ?? []).filter((seller) => seller.is_active);
        const brandName = selectedBrand?.brand_name ?? entry.manufacturerId;

        let resolvedEntry = resolveOrderEntry(entry, activeSellers, selectedBrand, "") ?? entry;

        if (!resolvedEntry.sellerId && activeSellers.length > 1) {
          setBootstrapState({ phase: "pick-seller", sellers: activeSellers, brandName });
          return;
        }

        const context = await ordersService.context(resolvedEntry, controller.signal);
        if (cancelled) return;

        if (context.no_sellers_linked) {
          setBootstrapState({
            phase: "blocked",
            title: "No seller linked",
            message: "This outlet has no active seller linked for the selected manufacturer.",
          });
          return;
        }

        if (context.seller_selection_required && !resolvedEntry.sellerId && context.sellers.length > 1) {
          setBootstrapState({
            phase: "pick-seller",
            sellers: context.sellers,
            brandName: context.manufacturer_name ?? brandName,
          });
          return;
        }

        if (!resolvedEntry.sellerId) {
          const sellerId = context.selected_seller_id
            ?? context.sellers[0]?.seller_id
            ?? activeSellers[0]?.seller_id;
          if (!sellerId) {
            setBootstrapState({
              phase: "blocked",
              title: "No seller linked",
              message: "This outlet has no active seller linked for the selected manufacturer.",
            });
            return;
          }
          const seller = context.sellers.find((item) => item.seller_id === sellerId)
            ?? activeSellers.find((item) => item.seller_id === sellerId);
          resolvedEntry = {
            ...resolvedEntry,
            sellerId,
            manufacturerId: manufacturerIdForSelectedSeller(
              resolvedEntry.manufacturerId,
              seller,
              selectedBrand,
            ),
          };
        }

        const selectedSeller = context.sellers.find((seller) => seller.seller_id === resolvedEntry.sellerId)
          ?? activeSellers.find((seller) => seller.seller_id === resolvedEntry.sellerId);

        if (selectedSeller && context.delivery_available === false) {
          setBootstrapState({
            phase: "blocked",
            title: "Delivery unavailable",
            message: context.delivery_block_reason ?? "Delivery availability could not be confirmed for this outlet.",
          });
          return;
        }

        const cart = await ordersService.createCart(resolvedEntry);
        if (cancelled) return;

        queryClient.setQueryData(orderKeys.cart(cart.id), cart);
        draft.setCartId(cart.id);
        if (!sameEntry(entry, resolvedEntry)) {
          draft.configureEntry(resolvedEntry);
        }
        router.replace("/sp/orders/new/esi");
      } catch (error) {
        if (cancelled || (error instanceof DOMException && error.name === "AbortError")) return;
        setBootstrapState({
          phase: "error",
          message: errorMessage(error),
        });
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [entry, entryKey, retryCount, router, queryClient]);

  if (!draft.entry) return <BlockedEntry title="Start order" />;

  if (bootstrapState.phase === "pick-seller") {
    const selectedBrand = findBrandByManufacturerId(sellerBrands, draft.entry.manufacturerId);
    return (
      <SellerSelectionScreen
        sellers={bootstrapState.sellers}
        toolbar={flowToolbar}
        onSelect={(sellerId) => {
          const selectedSeller = bootstrapState.sellers.find((seller) => seller.seller_id === sellerId);
          draft.configureEntry({
            ...draft.entry!,
            manufacturerId: manufacturerIdForSelectedSeller(
              draft.entry!.manufacturerId,
              selectedSeller,
              selectedBrand,
            ),
            sellerId,
          });
        }}
      />
    );
  }

  if (bootstrapState.phase === "blocked") {
    return (
      <SpScreen title="Start order" back toolbar={flowToolbar}>
        {orderStatePane(
          <EmptyState
            icon="Lock"
            title={bootstrapState.title}
            message={bootstrapState.message}
            actionLabel="Back to visit"
            onAction={() => router.push("/sp/route")}
          />,
        )}
      </SpScreen>
    );
  }

  if (bootstrapState.phase === "error") {
    return (
      <SpScreen title="Start order" back toolbar={flowToolbar}>
        {orderStatePane(
          <ErrorState
            title="Order context unavailable"
            message={bootstrapState.message}
            onRetry={() => {
              setBootstrapState({ phase: "loading" });
              setRetryCount((count) => count + 1);
            }}
          />,
        )}
      </SpScreen>
    );
  }

  return stepAutoSkipTransitionScreen({
    title: "Start order",
    message: "Verifying order context and continuing.",
    toolbar: flowToolbar,
  });
}

export function EsiSelectionScreen() {
  const router = useRouter();
  const draft = useResolvedEntry();
  const entry = draft.entry;
  const createCart = useCreateCart();
  const patch = usePatchCartById();
  const activeCartId = draft.cartId || createCart.data?.id || "";
  const outletSellerLinks = useOutletSellers(entry?.outletId ?? "");
  const cart = useCart(activeCartId);
  useRecoverIdlePendingQuery(cart, Boolean(activeCartId));
  useRecoverIdlePendingQuery(outletSellerLinks, Boolean(entry?.outletId));
  const [outletEsiIdInput, setOutletEsiIdInput] = useState("");
  const [sellerEsiIdInput, setSellerEsiIdInput] = useState("");
  const sellerBrandGroups = outletSellerLinks.data?.sellers_by_brand ?? draft.sellerBrands;
  const selectedBrand = entry
    ? findBrandByManufacturerId(sellerBrandGroups, entry.manufacturerId)
    : undefined;
  const selectedSeller = useMemo(() => (entry
    ? findOutletSeller(
      sellerBrandGroups,
      entry.manufacturerId,
      entry.sellerId,
    )
    : undefined), [entry, sellerBrandGroups]);
  const poRequired = sellerRequiresPo(selectedSeller);
  const outletOptions = selectedSeller?.outlet_esi_records ?? [];
  const sellerOptions = selectedSeller?.seller_esi_records ?? [];
  const sellerNeedsDeliveryEsi = selectedSeller
    ? selectedSeller.seller_type !== "MANUFACTURER"
    : false;
  const flowToolbar = (
    <OrderFlowToolbar
      step="esi"
      includesManufacturer={sellerBrandGroups.length > 1}
      requiresPoStep={poRequired}
    />
  );
  const outletEsiId = outletOptions.some((record) => record.esi_id === outletEsiIdInput)
    ? outletEsiIdInput
    : outletOptions.some((record) => record.esi_id === draft.selectedOutletEsiId)
      ? draft.selectedOutletEsiId
      : outletOptions[0]?.esi_id ?? "";
  const sellerEsiId = !sellerNeedsDeliveryEsi
    ? ""
    : sellerOptions.some((record) => record.esi_id === sellerEsiIdInput)
      ? sellerEsiIdInput
      : sellerOptions.some((record) => record.esi_id === draft.selectedSellerEsiId)
        ? draft.selectedSellerEsiId
        : sellerOptions[0]?.esi_id ?? "";
  const singleOutletChoice = outletOptions.length === 1;
  const singleSellerChoice = !sellerNeedsDeliveryEsi || sellerOptions.length === 1;
  const autoSkipEligible = singleOutletChoice && singleSellerChoice;
  const {
    running: autoSkipRunning,
    begin: beginAutoSkip,
    fail: failAutoSkip,
    succeed: succeedAutoSkip,
  } = useAutoSkip(`${outletEsiId}:${sellerNeedsDeliveryEsi ? sellerEsiId : ""}`);
  const nextStepPath = poRequired ? "/sp/orders/new/po" : "/sp/orders/new/ship-to";

  const continueDisabled = !outletEsiId
    || (sellerNeedsDeliveryEsi && !sellerEsiId)
    || createCart.isPending
    || patch.isPending;
  const esiSelectionHint = sellerNeedsDeliveryEsi
    ? "Select seller delivery SAP and outlet shipping SAP."
    : "Manufacturer seller selected. Delivery SAP is not required.";
  const esiNextStepHint = esiSelectionHint;

  const finishEsiAutoSkip = useCallback((
    cartId: string,
    { autoSkipped = false }: { autoSkipped?: boolean } = {},
  ) => {
    draft.setCartId(cartId);
    draft.setSelectedEsi(outletEsiId, sellerNeedsDeliveryEsi ? sellerEsiId : "");
    draft.setAutoSkippedStep("esi", autoSkipped);
    succeedAutoSkip();
    router.push(nextStepPath);
  }, [
    draft,
    nextStepPath,
    outletEsiId,
    router,
    sellerEsiId,
    sellerNeedsDeliveryEsi,
    succeedAutoSkip,
  ]);

  const applyEsiToCart = useCallback((
    cartId: string,
    { autoSkipped = false }: { autoSkipped?: boolean } = {},
  ) => {
    const body: PatchCartBody = {
      outlet_esi_id: outletEsiId,
    };
    if (sellerNeedsDeliveryEsi) {
      body.seller_esi_id = sellerEsiId;
    }
    patch.mutate({
      cartId,
      body,
      idempotencyKey: newMutationKey(),
    }, {
      onSuccess: () => {
        finishEsiAutoSkip(cartId, { autoSkipped });
      },
      onError: failAutoSkip,
    });
  }, [
    failAutoSkip,
    finishEsiAutoSkip,
    outletEsiId,
    patch,
    sellerEsiId,
    sellerNeedsDeliveryEsi,
  ]);

  const cartEsiMatchesSelection = Boolean(
    cart.data
    && cart.data.outlet_esi_id === outletEsiId
    && (
      !sellerNeedsDeliveryEsi
      || cart.data.seller_esi_id === sellerEsiId
    ),
  );

  const sellerDataReady = Boolean(selectedSeller)
    && (!outletSellerLinks.isPending || draft.sellerBrands.length > 0);

  useEffect(() => {
    patch.reset();
    createCart.reset();
  }, []);

  useEffect(() => {
    if (!activeCartId) return;
    void cart.refetch();
  }, [activeCartId, cart.refetch]);

  useEffect(() => {
    if (
      !entry?.sellerId
      || !sellerDataReady
      || !autoSkipEligible
      || draft.autoSkippedSteps.esi
      || createCart.isPending
      || patch.isPending
      || (activeCartId && (cart.isLoading || cart.isError))
    ) {
      return;
    }

    if (activeCartId && cartEsiMatchesSelection) {
      finishEsiAutoSkip(activeCartId, { autoSkipped: true });
      return;
    }

    if (!beginAutoSkip()) return;
    if (activeCartId) {
      applyEsiToCart(activeCartId, { autoSkipped: true });
      return;
    }
    createCart.mutate(entry, {
      onSuccess: (createdCart) => {
        draft.setCartId(createdCart.id);
        applyEsiToCart(createdCart.id, { autoSkipped: true });
      },
      onError: failAutoSkip,
    });
  }, [
    activeCartId,
    applyEsiToCart,
    autoSkipEligible,
    beginAutoSkip,
    cart.isError,
    cart.isLoading,
    cartEsiMatchesSelection,
    createCart.isPending,
    createCart.mutate,
    draft.autoSkippedSteps.esi,
    entry,
    failAutoSkip,
    finishEsiAutoSkip,
    patch.isPending,
    sellerDataReady,
  ]);

  if (autoSkipRunning) {
    return stepAutoSkipTransitionScreen({
      title: "Select SAP",
      message: "Only one SAP option was available. Applying it and continuing.",
      toolbar: flowToolbar,
    });
  }

  if (!entry || !entry.sellerId) {
    return <BlockedEntry title="Select SAP" />;
  }

  if (!selectedSeller) {
    return (
      <SpScreen title="Select SAP" back toolbar={flowToolbar}>
        {orderStatePane(
          <EmptyState
            icon="Lock"
            title="Seller mapping unavailable"
            message="Seller SAP details are unavailable for this brand and outlet."
            actionLabel="Back to start order"
            onAction={() => router.push("/sp/orders/new")}
          />,
        )}
      </SpScreen>
    );
  }

  if (!outletOptions.length) {
    return (
      <SpScreen title="Select SAP" back toolbar={flowToolbar}>
        {orderStatePane(
          <EmptyState
            icon="Lock"
            title="No outlet SAP records"
            message="This seller has no shipping-address SAP linked for the outlet."
            actionLabel="Back to start order"
            onAction={() => router.push("/sp/orders/new")}
          />,
        )}
      </SpScreen>
    );
  }

  if (sellerNeedsDeliveryEsi && !sellerOptions.length) {
    return (
      <SpScreen title="Select SAP" back toolbar={flowToolbar}>
        {orderStatePane(
          <EmptyState
            icon="Lock"
            title="No seller SAP records"
            message="This seller requires a delivery-location SAP, but none were returned."
            actionLabel="Back to start order"
            onAction={() => router.push("/sp/orders/new")}
          />,
        )}
      </SpScreen>
    );
  }

  return (
    <SpScreen title="Select SAP" back toolbar={flowToolbar}>
      <div className="sp-content sp-order-flow-content sp-order-motion-stack">
        <SpSectionLabel>Seller and brand</SpSectionLabel>
        <SpCard style={{ borderRadius: "var(--radius-lg)" }}>
          <div className="sp-order-setup-row">
            <span className="sp-order-icon-avatar">
              <Icon name="InventoryOutlined" size={20} color="currentColor" />
            </span>
            <div className="sp-order-setup-copy" style={{ flex: 1 }}>
              <strong>{selectedSeller.name}</strong>
              <span>{selectedBrand?.brand_name ?? entry.manufacturerId} · {selectedSeller.seller_type.replaceAll("_", " ")}</span>
            </div>
          </div>
        </SpCard>
        <SpInlineAlert tone="info">
          {esiNextStepHint}
        </SpInlineAlert>
        <SpCard style={{ borderRadius: "var(--radius-lg)" }}>
          <div className="sp-stack">
            {sellerNeedsDeliveryEsi ? (
              <Select
                label="Seller delivery-location SAP"
                fullWidth
                value={sellerEsiId}
                onChange={(value) => setSellerEsiIdInput(String(value))}
                options={sellerOptions.map((record) => ({
                  value: record.esi_id,
                  label: esiLabel(record),
                }))}
              />
            ) : (
              ""
            )}
            <Select
              label="Outlet shipping SAP"
              fullWidth
              value={outletEsiId}
              onChange={(value) => setOutletEsiIdInput(String(value))}
              options={outletOptions.map((record) => ({
                value: record.esi_id,
                label: esiLabel(record),
              }))}
            />
          </div>
        </SpCard>
        {patch.isError ? (
          <SpInlineAlert tone="error">{errorMessage(patch.error)}</SpInlineAlert>
        ) : null}
        {createCart.isError ? (
          <SpInlineAlert tone="error">{errorMessage(createCart.error)}</SpInlineAlert>
        ) : null}
      </div>
      <SpStickyFooter>
        <Button
          variant="filled"
          color="primary"
          loading={createCart.isPending || patch.isPending}
          disabled={continueDisabled}
          label={poRequired ? "Continue to select PO" : "Continue to ship-to"}
          onClick={() => {
            if (activeCartId) {
              applyEsiToCart(activeCartId);
              return;
            }
            createCart.mutate(entry, {
              onSuccess: (createdCart) => {
                draft.setCartId(createdCart.id);
                applyEsiToCart(createdCart.id);
              },
            });
          }}
          style={{ width: "100%" }}
        />
      </SpStickyFooter>
    </SpScreen>
  );
}

interface ShippingOverrideDraftState {
  line1: string;
  line2: string;
  stateId: string;
  districtId: string;
  pincode: string;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function firstText(record: Record<string, unknown> | null, keys: string[]) {
  if (!record) return "";
  for (const key of keys) {
    const value = record[key];
    if (value == null) continue;
    const text = String(value).trim();
    if (text) return text;
  }
  return "";
}

function shippingOverrideFromEsiGeography(record?: EsiRecordOut | null): ShippingOverrideDraftState | null {
  const geography = asRecord(record?.geographic_info);
  if (!geography) return null;

  const addressInfo = asRecord(geography.address_info);
  const stateInfo = asRecord(geography.state_info);
  const districtInfo = asRecord(geography.district_info);
  const pincodeInfo = asRecord(geography.pincode_info);

  return {
    line1: firstText(addressInfo, ["address_line_1", "address_line1", "line1"]),
    line2: firstText(addressInfo, ["address_line_2", "address_line2", "line2"]),
    stateId: firstText(stateInfo, ["state_id"]) || firstText(geography, ["state_id"]),
    districtId: firstText(districtInfo, ["district_id"]) || firstText(geography, ["district_id"]),
    pincode: firstText(pincodeInfo, ["pincode_id", "pincode_name", "pincode"]),
  };
}

function shippingOverrideFromShipToOption(option?: ShipToOptionOut | null): ShippingOverrideDraftState | null {
  if (!option) return null;
  const optionRecord = asRecord(option as unknown);
  const geographic = asRecord(optionRecord?.geographic_info);
  const addressInfo = asRecord(geographic?.address_info);
  const stateInfo = asRecord(geographic?.state_info);
  const districtInfo = asRecord(geographic?.district_info);
  const pincodeInfo = asRecord(geographic?.pincode_info);

  const flatLine2 = [option.address_line2 ?? "", option.address_line3 ?? ""]
    .map((value) => value.trim())
    .filter((value) => value.length > 0)
    .join(", ");
  const nestedLine2 = [
    firstText(addressInfo, ["address_line_2", "address_line2", "line2"]),
    firstText(addressInfo, ["address_line_3", "address_line3", "line3"]),
  ]
    .map((value) => value.trim())
    .filter((value) => value.length > 0)
    .join(", ");

  return {
    line1: option.address_line1.trim()
      || firstText(addressInfo, ["address_line_1", "address_line1", "line1"]),
    line2: flatLine2 || nestedLine2,
    stateId: firstText(optionRecord, ["state_id"])
      || firstText(stateInfo, ["state_id"])
      || firstText(geographic, ["state_id"]),
    districtId: firstText(optionRecord, ["district_id"])
      || firstText(districtInfo, ["district_id"])
      || firstText(geographic, ["district_id"]),
    pincode: firstText(optionRecord, ["pincode"])
      || firstText(pincodeInfo, ["pincode_id", "pincode_name", "pincode"])
      || firstText(geographic, ["pincode"]),
  };
}

export function ShipToPartnerScreen() {
  const router = useRouter();
  const draft = useResolvedEntry();
  const cart = useCart(draft.cartId);
  const outletSellerLinks = useOutletSellers(draft.entry?.outletId ?? "");
  const sellerBrandGroups = outletSellerLinks.data?.sellers_by_brand ?? draft.sellerBrands;
  const outletEsiId = cart.data?.outlet_esi_id ?? draft.selectedOutletEsiId;
  const context = useOrderContext(draft.entry, outletEsiId);
  const patch = usePatchCart(draft.cartId);
  const serviceabilityManufacturerId = draft.entry?.manufacturerId ?? "";
  const states = useServiceableStates(serviceabilityManufacturerId);
  const [shipToInput, setShipToInput] = useState<string | null>(null);
  const [shipToMenuOpen, setShipToMenuOpen] = useState(false);
  const [shipToSearch, setShipToSearch] = useState("");
  const [addressInput, setAddressInput] = useState<ShippingOverrideDraftState | null>(null);
  const draftShipToValue = draft.shipToSelection
    ? (draft.shipToSelection.type === "self"
      ? "self"
      : `${draft.shipToSelection.outletId}:${draft.shipToSelection.esiId}`)
    : null;
  const shipToOptions = context.data?.ship_to_options ?? [];
  const shipToValue = shipToInput ?? draftShipToValue ?? shipToValueFromCart(cart.data, shipToOptions);
  const selectedOutletSeller = draft.entry
    ? findOutletSeller(sellerBrandGroups, draft.entry.manufacturerId, draft.entry.sellerId)
    : undefined;
  const selectedOutletEsiRecord = selectedOutletSeller?.outlet_esi_records.find(
    (esiRecord) => esiRecord.esi_id === outletEsiId,
  ) ?? selectedOutletSeller?.outlet_esi_records.find(
    (esiRecord) => esiRecord.esi_id === draft.selectedOutletEsiId,
  ) ?? selectedOutletSeller?.outlet_esi_records[0];
  const esiDerivedAddress = shippingOverrideFromEsiGeography(selectedOutletEsiRecord);
  const ownGodownPrefillAddress = esiDerivedAddress
    ?? normalizeShippingOverride(cart.data?.shipping_address_override)
    ?? {
      line1: "",
      line2: "",
      stateId: "",
      districtId: "",
      pincode: "",
    };
  const baseAddress = draft.shippingOverrideDraft ?? ownGodownPrefillAddress;
  const address = addressInput ?? baseAddress;
  const districts = useServiceableDistricts(
    serviceabilityManufacturerId,
    address.stateId,
    Boolean(address.stateId),
  );
  const pincodeOptions = useShipToAddressOptions(
    address.districtId,
    Boolean(address.districtId),
  );
  const searchablePincodeOptions = useMemo(() => {
    const fetched = (pincodeOptions.data?.pincodes ?? []).map((pincode) => ({
      value: pincode,
      label: pincode,
    }));
    if (!address.pincode || fetched.some((option) => option.value === address.pincode)) return fetched;
    return [{ value: address.pincode, label: address.pincode }, ...fetched];
  }, [pincodeOptions.data?.pincodes, address.pincode]);
  const selectedSeller = context.data?.sellers.find(
    (seller) => seller.seller_id === (draft.entry?.sellerId ?? context.data?.selected_seller_id),
  );
  const orderPath = orderPathFromContext(cart.data, context.data, selectedSeller);
  const poRequired = isPoBackedPath(orderPath);
  const selectedShipToOption = shipToOptions.find(
    (option) => shipToOptionValue(option) === shipToValue,
  );
  const flowToolbar = (
    <OrderFlowToolbar
      step="shipTo"
      includesManufacturer={sellerBrandGroups.length > 1}
      requiresPoStep={poRequired}
    />
  );
  const partnerShipToOptions = useMemo(
    () => shipToOptions.filter((option) => {
      if (outletEsiId) return option.esi_id !== outletEsiId;
      return !option.is_self;
    }),
    [shipToOptions, outletEsiId],
  );
  const shipToSearchTerm = shipToSearch.trim().toLowerCase();
  const filteredPartnerShipToOptions = useMemo(
    () => partnerShipToOptions.filter((option) => {
      if (!shipToSearchTerm) return true;
      const name = option.name.toLowerCase();
      const esiCode = (option.esi_code ?? "").toLowerCase();
      const esiId = option.esi_id.toLowerCase();
      return name.includes(shipToSearchTerm)
        || esiCode.includes(shipToSearchTerm)
        || esiId.includes(shipToSearchTerm);
    }),
    [partnerShipToOptions, shipToSearchTerm],
  );
  const noPartnerOptions = partnerShipToOptions.length === 0;
  const selectedShipToEsiId = selectedShipToOption?.esi_id ?? (
    shipToValue === "self"
      ? ""
      : shipToValue.split(":")[1] ?? ""
  );
  const isPartnerShipTo = shipToValue !== "self" && (
    !outletEsiId || selectedShipToEsiId !== outletEsiId
  );
  const shipToSummaryTitle = shipToValue === "self"
    ? "Own godown"
    : (selectedShipToOption?.name ?? "Select ship-to partner");
  const shipToSummarySubtitle = shipToValue === "self"
    ? `SAP ${outletEsiId}`
    : selectedShipToOption
      ? `SAP ${selectedShipToOption.esi_code ?? selectedShipToOption.esi_id}`
      : "Choose the delivery partner ship-to address";
  const esiAddressReady = Boolean(
    esiDerivedAddress
    && esiDerivedAddress.line1.trim()
    && esiDerivedAddress.stateId
    && esiDerivedAddress.districtId
    && /^\d{6}$/.test(esiDerivedAddress.pincode.trim()),
  );
  const partnerAddressReady = Boolean(
    address.line1.trim()
    && address.stateId
    && address.districtId
    && /^\d{6}$/.test(address.pincode.trim()),
  );
  const shipToReady = shipToValue === "self" || Boolean(selectedShipToOption);
  const addressReady = partnerAddressReady;

  const onSelectShipTo = (value: string) => {
    setShipToMenuOpen(false);
    setShipToSearch("");
    setShipToInput(value);
    if (value === "self") {
      const nextSelfAddress = { ...ownGodownPrefillAddress };
      setAddressInput(nextSelfAddress);
      draft.setShipToSelection({ type: "self", outletId: "", esiId: "" });
      draft.setShippingOverrideDraft(nextSelfAddress);
      return;
    }
    const option = partnerShipToOptions.find((item) => shipToOptionValue(item) === value);
    if (!option) return;
    const nextPartnerAddress = shippingOverrideFromShipToOption(option);
    if (nextPartnerAddress) {
      setAddressInput(nextPartnerAddress);
      draft.setShippingOverrideDraft(nextPartnerAddress);
    }
    draft.setShipToSelection({
      type: "dealer",
      outletId: option.party_id,
      esiId: option.esi_id,
    });
  };

  const {
    running: autoSkipRunning,
    begin: beginAutoSkip,
    fail: failAutoSkip,
  } = useAutoSkip(shipToValue);
  const applyShipToSelection = useCallback((
    { autoSkipped = false }: { autoSkipped?: boolean } = {},
  ) => {
    const payload: PatchCartBody = {};
    if (shipToValue === "self") {
      payload.ship_to_type = "self";
      payload.ship_to_outlet_id = null;
      payload.ship_to_esi_id = null;
      payload.shipping_address_override = {
        line1: address.line1.trim(),
        line2: address.line2.trim() || null,
        state_id: address.stateId,
        district_id: address.districtId,
        pincode: address.pincode.trim(),
      };
    } else if (selectedShipToOption) {
      payload.ship_to_type = "dealer";
      payload.ship_to_outlet_id = selectedShipToOption.party_id;
      payload.ship_to_esi_id = selectedShipToOption.esi_id;
      payload.shipping_address_override = {
        line1: address.line1.trim(),
        line2: address.line2.trim() || null,
        state_id: address.stateId,
        district_id: address.districtId,
        pincode: address.pincode.trim(),
      };
    }
    patch.mutate({
      body: payload,
      idempotencyKey: newMutationKey(),
    }, {
      onSuccess: () => {
        if (shipToValue === "self") {
          draft.setShipToSelection({ type: "self", outletId: "", esiId: "" });
          draft.setShippingOverrideDraft(address);
        } else if (selectedShipToOption) {
          draft.setShipToSelection({
            type: "dealer",
            outletId: selectedShipToOption.party_id,
            esiId: selectedShipToOption.esi_id,
          });
          draft.setShippingOverrideDraft(address);
        }
        draft.setAutoSkippedStep("shipTo", autoSkipped);
        router.push("/sp/orders/new/products");
      },
      onError: failAutoSkip,
    });
  }, [
    address,
    draft,
    failAutoSkip,
    patch,
    router,
    selectedShipToOption,
    shipToValue,
  ]);

  const autoSkipEligible = noPartnerOptions && shipToValue === "self" && addressReady;
  useEffect(() => {
    if (
      !cart.data
      || !context.data
      || !autoSkipEligible
      || draft.autoSkippedSteps.shipTo
      || patch.isPending
    ) {
      return;
    }
    if (!beginAutoSkip()) return;
    applyShipToSelection({ autoSkipped: true });
  }, [
    applyShipToSelection,
    autoSkipEligible,
    beginAutoSkip,
    cart.data,
    context.data,
    draft.autoSkippedSteps.shipTo,
    patch.isPending,
  ]);

  if (autoSkipRunning) {
    return stepAutoSkipTransitionScreen({
      title: "Ship to and address",
      message: "No partner ship-to options were available. Applying own godown and continuing.",
      toolbar: flowToolbar,
    });
  }

  if (!draft.entry || !draft.cartId || !draft.entry.sellerId) {
    return <BlockedEntry title="Ship to" />;
  }
  if (cart.isPending || context.isPending) return loadingScreen("Ship to", { toolbar: flowToolbar });
  if (cart.isError || context.isError) {
    return (
      <SpScreen title="Ship to" back toolbar={flowToolbar}>
        {orderStatePane(
          <ErrorState
            title="Ship-to setup unavailable"
            message={errorMessage(cart.error ?? context.error)}
            onRetry={() => {
              void cart.refetch();
              void context.refetch();
            }}
          />,
        )}
      </SpScreen>
    );
  }
  if (!cart.data || !context.data) return loadingScreen("Ship to", { toolbar: flowToolbar });

  return (
    <SpScreen title="Ship to and address" back toolbar={flowToolbar}>
      <div className="sp-content sp-order-flow-content sp-order-motion-stack">
        <div>
          <SpSectionLabel>Ship to partner</SpSectionLabel>
          <div className="sp-order-select-panel">
            <button
              type="button"
              className="sp-order-select-row"
              data-open={shipToMenuOpen}
              onClick={() => setShipToMenuOpen((open) => !open)}
              aria-expanded={shipToMenuOpen}
            >
              <span className="sp-order-icon-avatar" style={{ height: 38, width: 38 }}>
                <Icon name="DispatchPlanOutlined" size={20} color="currentColor" />
              </span>
              <span className="sp-order-setup-copy" style={{ flex: 1 }}>
                <strong style={{ fontSize: 15 }}>{shipToSummaryTitle}</strong>
                <span style={{ fontSize: 14, lineHeight: "var(--text-body-sm-line)" }}>{shipToSummarySubtitle}</span>
              </span>
              <Icon
                name="KeyboardArrowDown"
                size={20}
                color="var(--color-text-secondary)"
                style={{
                  flexShrink: 0,
                  transform: shipToMenuOpen ? "rotate(180deg)" : "none",
                  transition: "transform var(--motion-duration-fast, 140ms) var(--motion-ease-standard, ease)",
                }}
              />
            </button>
            {shipToMenuOpen ? (
              <SpCard padded={false} style={{ borderRadius: "var(--radius-md)" }}>
                <div style={{ paddingTop: 12, paddingInline: 14, paddingBottom: 0 }}>
                  <TextField
                    placeholder="Search ship-to partners"
                    startAdornment={<Icon name="SearchOutlined" size={18} color="var(--color-text-placeholder)" />}
                    value={shipToSearch}
                    onChange={(event) => setShipToSearch((event.target as HTMLInputElement).value)}
                  />
                </div>
                <div className="sp-list">
                  <ListRow
                    title="Own godown"
                    subtitle={`SAP ${outletEsiId}`}
                    trailing={shipToValue === "self" ? <Icon name="Check" size={18} color="var(--color-primary)" /> : null}
                    onClick={() => onSelectShipTo("self")}
                    style={{ borderRadius: 0, boxShadow: "none", minHeight: 60 }}
                  />
                  {filteredPartnerShipToOptions.map((option) => {
                    const value = shipToOptionValue(option);
                    return (
                      <ListRow
                        key={value}
                        title={option.name}
                        subtitle={`SAP ${option.esi_code ?? option.esi_id}`}
                        trailing={shipToValue === value ? <Icon name="Check" size={18} color="var(--color-primary)" /> : null}
                        onClick={() => onSelectShipTo(value)}
                        style={{ borderRadius: 0, boxShadow: "none", minHeight: 60 }}
                      />
                    );
                  })}
                  {!filteredPartnerShipToOptions.length ? (
                    <div style={{ paddingTop: "var(--space-xs)", paddingInline: 14, paddingBottom: 14 }}>
                      <SpInlineAlert tone="warning">No ship-to partners match your search.</SpInlineAlert>
                    </div>
                  ) : null}
                </div>
              </SpCard>
            ) : null}
          </div>
        </div>
        <div>
          <SpSectionLabel>Delivery address</SpSectionLabel>
          <SpCard style={{ overflow: "visible" }}>
            <div className="sp-stack">
              <TextField
                label="Address line 1"
                value={address.line1}
                onChange={(event) => setAddressInput({
                  ...address,
                  line1: (event.target as HTMLInputElement).value,
                })}
                required
              />
              <TextField
                label="Address line 2"
                value={address.line2}
                onChange={(event) => setAddressInput({
                  ...address,
                  line2: (event.target as HTMLInputElement).value,
                })}
              />
              <Select
                label="Serviceable state"
                fullWidth
                searchable
                searchPlaceholder="Search state"
                value={address.stateId}
                onChange={(value) => {
                  const nextStateId = String(value);
                  setAddressInput({
                    ...address,
                    stateId: nextStateId,
                    districtId: address.stateId === nextStateId ? address.districtId : "",
                    pincode: address.stateId === nextStateId ? address.pincode : "",
                  });
                }}
                options={(states.data?.states ?? []).map((state) => ({
                  value: state.state_id,
                  label: state.state_name,
                }))}
              />
              <Select
                label="Serviceable district"
                fullWidth
                searchable
                searchPlaceholder="Search district"
                value={address.districtId}
                onChange={(value) => {
                  const nextDistrictId = String(value);
                  setAddressInput({
                    ...address,
                    districtId: nextDistrictId,
                    pincode: address.districtId === nextDistrictId ? address.pincode : "",
                  });
                }}
                options={(districts.data?.districts ?? []).map((district) => ({
                  value: district.district_id,
                  label: district.district_name,
                }))}
              />
              <Select
                label="Pincode"
                fullWidth
                searchable
                searchPlaceholder="Search pincode"
                placeholder="Select serviceable pincode"
                value={address.pincode}
                onChange={(value) => setAddressInput({
                  ...address,
                  pincode: String(value),
                })}
                options={searchablePincodeOptions}
                emptyLabel={address.districtId ? "No pincodes found for this district" : "Select district first"}
              />
            </div>
          </SpCard>
        </div>
        <SpInlineAlert tone={poRequired ? "warning" : "info"}>
          Choose your own godown or a ship-to partner, then confirm or edit the delivery address before continuing.
        </SpInlineAlert>
        {states.isPending || districts.isPending || pincodeOptions.isPending ? (
          <SpInlineAlert>Refreshing serviceability data…</SpInlineAlert>
        ) : null}
        {states.isError || districts.isError || pincodeOptions.isError ? (
          <SpInlineAlert tone="warning">
            Serviceability data could not be refreshed. Verify state, district, and pincode before continuing.
          </SpInlineAlert>
        ) : null}
        {!isPartnerShipTo && !esiAddressReady ? (
          <SpInlineAlert tone="warning">
            Selected outlet SAP is missing required address details. Update the fields manually before continuing.
          </SpInlineAlert>
        ) : null}
        {patch.isError ? (
          <SpInlineAlert tone="error">{errorMessage(patch.error)}</SpInlineAlert>
        ) : null}
      </div>
      <SpStickyFooter>
        <Button
          variant="filled"
          color="primary"
          loading={patch.isPending}
          disabled={patch.isPending || !shipToReady || !addressReady}
          label="Add products"
          onClick={() => applyShipToSelection()}
          style={{ width: "100%" }}
        />
      </SpStickyFooter>
    </SpScreen>
  );
}

export function PoSelectorScreen() {
  const router = useRouter();
  const draft = useResolvedEntry();
  const { entry, cartId } = draft;
  const cart = useCart(cartId);
  const outletEsiId = cart.data?.outlet_esi_id ?? draft.selectedOutletEsiId;
  const purchaseOrders = usePurchaseOrders(
    entry,
    Boolean(entry?.sellerId && cartId && outletEsiId),
    outletEsiId,
  );
  const patch = usePatchCart(cartId);
  const [selectedPoId, setSelectedPoId] = useState("");
  const flowToolbar = (
    <OrderFlowToolbar
      step="po"
      includesManufacturer={draft.sellerBrands.length > 1}
      requiresPoStep
    />
  );
  const options = purchaseOrders.data?.purchase_orders ?? [];
  const effectiveSelectedPoId = selectedPoId
    || cart.data?.source_po_id
    || (options.length === 1 ? options[0]!.po_id : "");
  const autoSkipEligible = options.length === 1 && Boolean(effectiveSelectedPoId);
  const {
    running: autoSkipRunning,
    begin: beginAutoSkip,
    fail: failAutoSkip,
    succeed: succeedAutoSkip,
  } = useAutoSkip(effectiveSelectedPoId);

  const applyPoSelection = useCallback((
    poId: string,
    { autoSkipped = false }: { autoSkipped?: boolean } = {},
  ) => {
    patch.mutate({
      body: { source_po_id: poId },
      idempotencyKey: newMutationKey(),
    }, {
      onSuccess: () => {
        draft.setAutoSkippedStep("po", autoSkipped);
        succeedAutoSkip();
        router.push("/sp/orders/new/ship-to");
      },
      onError: failAutoSkip,
    });
  }, [draft, failAutoSkip, patch, router, succeedAutoSkip]);

  useEffect(() => {
    if (!entry?.sellerId || outletEsiId) return;
    router.replace("/sp/orders/new/esi");
  }, [entry?.sellerId, outletEsiId, router]);

  useEffect(() => {
    if (
      !cart.data
      || purchaseOrders.isPending
      || !purchaseOrders.data
      || !autoSkipEligible
      || draft.autoSkippedSteps.po
      || patch.isPending
    ) {
      return;
    }

    if (cart.data.source_po_id === effectiveSelectedPoId) {
      draft.setAutoSkippedStep("po", true);
      router.push("/sp/orders/new/ship-to");
      return;
    }

    if (!beginAutoSkip()) return;
    applyPoSelection(effectiveSelectedPoId, { autoSkipped: true });
  }, [
    applyPoSelection,
    autoSkipEligible,
    beginAutoSkip,
    cart.data,
    draft,
    draft.autoSkippedSteps.po,
    effectiveSelectedPoId,
    patch.isPending,
    purchaseOrders.data,
    purchaseOrders.isPending,
    router,
  ]);

  if (autoSkipRunning) {
    return stepAutoSkipTransitionScreen({
      title: "Select PO",
      message: "Only one open purchase order was available. Applying it and continuing.",
      toolbar: flowToolbar,
    });
  }

  if (!entry || !entry.sellerId) return <BlockedEntry title="Select PO" />;
  if (!outletEsiId) return loadingScreen("Select PO", { toolbar: flowToolbar });
  if (!cartId || cart.isPending || purchaseOrders.isPending) {
    return loadingScreen("Select PO", { toolbar: flowToolbar });
  }
  if (cart.isError || purchaseOrders.isError) {
    return (
      <SpScreen title="Select PO" back toolbar={flowToolbar}>
        {orderStatePane(
          <ErrorState
            title="Purchase orders unavailable"
            message={errorMessage(cart.error ?? purchaseOrders.error)}
            onRetry={() => {
              void cart.refetch();
              void purchaseOrders.refetch();
            }}
          />,
        )}
      </SpScreen>
    );
  }
  if (!options.length) {
    return (
      <SpScreen title="Select PO" back toolbar={flowToolbar}>
        {orderStatePane(
          <EmptyState
            icon="InvoiceOutlined"
            title="No open purchase orders"
            message="A valid open PO is required for this order."
            actionLabel="Back to SAP"
            onAction={() => router.push("/sp/orders/new/esi")}
          />,
        )}
      </SpScreen>
    );
  }
  return (
    <SpScreen title="Select PO" back toolbar={flowToolbar}>
      <div className="sp-content sp-order-flow-content sp-order-motion-stack">
        <SpInlineAlert>Choose one open PO to continue.</SpInlineAlert>
        <p className="sp-meta">
          Live purchase orders as of {new Date(purchaseOrders.data!.as_of).toLocaleString("en-IN")}
        </p>
        <SpCard>
          <div className="sp-po-list">
            {options.map((purchaseOrder) => (
              <button
                className="sp-po-option"
                data-active={effectiveSelectedPoId === purchaseOrder.po_id}
                key={purchaseOrder.po_id}
                onClick={() => setSelectedPoId(purchaseOrder.po_id)}
                type="button"
              >
                <Icon name="Calendar" size={22} color="currentColor" />
                <span className="sp-po-copy">
                  <strong>{purchaseOrder.po_number}</strong>
                  <span>{purchaseOrder.manufacturer_name} · {purchaseOrder.po_date}</span>
                </span>
                <span className="sp-po-value">
                  {money(purchaseOrder.balance_value_paise)}
                  <small>open</small>
                </span>
              </button>
            ))}
          </div>
        </SpCard>
        {patch.isError ? (
          <SpInlineAlert tone="error">{errorMessage(patch.error)}</SpInlineAlert>
        ) : null}
      </div>
      <SpStickyFooter>
        <Button
          variant="filled"
          color="primary"
          loading={patch.isPending}
          disabled={!effectiveSelectedPoId || patch.isPending}
          label="Continue with this PO"
          onClick={() => applyPoSelection(effectiveSelectedPoId)}
          style={{ width: "100%" }}
        />
      </SpStickyFooter>
    </SpScreen>
  );
}

export function ProductPickerScreen() {
  const router = useRouter();
  const draft = useResolvedEntry();
  const { cartId } = draft;
  const [query, setQuery] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [filtersExpanded, setFiltersExpanded] = useState(false);
  const [draftQuantities, setDraftQuantities] = useState<Record<string, number>>({});
  const [serverQuantities, setServerQuantities] = useState<Record<string, number>>({});
  const [draftFormTypes, setDraftFormTypes] = useState<Record<string, LineFormType>>({});
  const [serverFormTypes, setServerFormTypes] = useState<Record<string, LineFormType>>({});
  const [saveError, setSaveError] = useState<string | null>(null);
  const cart = useCart(cartId);
  const debouncedQuery = useDebouncedSearchQuery(query);
  const catalog = useCatalog(cartId, debouncedQuery, "All");
  const update = useUpsertCartLine(cartId);
  const allProducts = catalog.data?.products ?? [];
  const totalDraftQty = Object.values(draftQuantities).reduce((sum, value) => sum + value, 0);
  const poCapQty = cart.data?.po_cap_qty ?? null;
  const poLineBalances = cart.data?.po_line_balances;
  const categoryOptions = useMemo(() => {
    const counts = new Map<string, number>();
    for (const product of allProducts) {
      const value = product.category?.trim() || "Uncategorized";
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
    return [
      { value: "All", label: "All", count: allProducts.length },
      ...Array.from(counts.entries())
        .sort(([left], [right]) => left.localeCompare(right, "en-IN"))
        .map(([value, count]) => ({ value, label: value, count })),
    ];
  }, [allProducts]);
  const flowToolbar = (
    <OrderFlowToolbar
      step="products"
      includesManufacturer={draft.sellerBrands.length > 1}
      requiresPoStep={isPoBackedPath(cart.data?.order_path)}
    />
  );

  const [linesCartId, setLinesCartId] = useState(cartId);
  if (linesCartId !== cartId) {
    setLinesCartId(cartId);
    setDraftQuantities({});
    setServerQuantities({});
    setDraftFormTypes({});
    setServerFormTypes({});
    setSaveError(null);
  }

  const catalogProducts = catalog.data?.products;
  const cartLines = cart.data?.lines;
  const [syncedLineSources, setSyncedLineSources] = useState<{
    products: typeof catalogProducts;
    lines: typeof cartLines;
  }>({ products: undefined, lines: undefined });
  if (syncedLineSources.products !== catalogProducts || syncedLineSources.lines !== cartLines) {
    setSyncedLineSources({ products: catalogProducts, lines: cartLines });
    if (catalogProducts?.length) {
      const cartFormTypeByProduct = new Map(
        (cartLines ?? []).map((line) => [
          line.product_id,
          normalizeLineFormType(line.form_type),
        ]),
      );
      setServerQuantities((current) => {
        const next = { ...current };
        for (const product of catalogProducts) {
          next[product.product_id] = Math.max(0, product.qty_in_cart ?? 0);
        }
        return next;
      });
      setServerFormTypes((current) => {
        const next = { ...current };
        for (const product of catalogProducts) {
          next[product.product_id] = cartFormTypeByProduct.get(product.product_id) ?? "";
        }
        return next;
      });
      setDraftQuantities((current) => {
        const next = { ...current };
        for (const product of catalogProducts) {
          if (next[product.product_id] == null) {
            next[product.product_id] = Math.max(0, product.qty_in_cart ?? 0);
          }
        }
        return next;
      });
      setDraftFormTypes((current) => {
        const next = { ...current };
        for (const product of catalogProducts) {
          if (next[product.product_id] != null) continue;
          const cartFormType = cartFormTypeByProduct.get(product.product_id) ?? "";
          next[product.product_id] = product.form_type_req
            ? resolvedRequiredFormType(cartFormType)
            : cartFormType;
        }
        return next;
      });
    }
  }

  const updateDraftQuantity = (productId: string, quantity: number) => {
    const nextQuantity = Math.max(0, quantity);
    setSaveError(null);
    setDraftQuantities((current) => ({ ...current, [productId]: nextQuantity }));
    const product = allProducts.find((item) => item.product_id === productId);
    if (!product?.form_type_req) return;
    setDraftFormTypes((current) => (
      current[productId] === "BEND" || current[productId] === "STRAIGHT"
        ? current
        : { ...current, [productId]: "STRAIGHT" }
    ));
  };
  const updateDraftFormType = (productId: string, formType: "STRAIGHT" | "BEND") => {
    setSaveError(null);
    setDraftFormTypes((current) => ({ ...current, [productId]: formType }));
  };

  const changedLines = useMemo(
    () => allProducts
      .map((product) => {
        const quantity = draftQuantities[product.product_id] ?? Math.max(0, product.qty_in_cart ?? 0);
        const formType: "STRAIGHT" | "BEND" | null = quantity > 0 && product.form_type_req
          ? resolvedRequiredFormType(draftFormTypes[product.product_id])
          : null;
        const serverQuantity = serverQuantities[product.product_id] ?? 0;
        const serverFormType = serverFormTypes[product.product_id] ?? "";
        const persistedFormType = serverQuantity > 0 ? (serverFormType || null) : null;
        return {
          productId: product.product_id,
          quantity,
          formType,
          changed: quantity !== serverQuantity || formType !== persistedFormType,
        };
      })
      .filter((line) => line.changed),
    [allProducts, draftFormTypes, draftQuantities, serverFormTypes, serverQuantities],
  );
  const missingFormTypeCount = useMemo(
    () => allProducts.filter((product) => {
      if (!product.form_type_req) return false;
      const quantity = draftQuantities[product.product_id] ?? Math.max(0, product.qty_in_cart ?? 0);
      if (quantity <= 0) return false;
      const formType = resolvedRequiredFormType(draftFormTypes[product.product_id]);
      return !formType;
    }).length,
    [allProducts, draftFormTypes, draftQuantities],
  );
  const itemCount = useMemo(
    () => Object.values(draftQuantities).reduce((total, quantity) => total + quantity, 0),
    [draftQuantities],
  );
  const activeFilterCount = selectedCategories.length;
  const changedLineCount = changedLines.length;
  const products = useMemo(
    () => {
      if (!selectedCategories.length) return allProducts;
      const selected = new Set(selectedCategories);
      return allProducts.filter((product) => selected.has(product.category?.trim() || "Uncategorized"));
    },
    [allProducts, selectedCategories],
  );
  const availableCategories = new Set(
    categoryOptions
      .filter((option) => option.value !== "All")
      .map((option) => option.value),
  );
  if (selectedCategories.some((value) => !availableCategories.has(value))) {
    setSelectedCategories(selectedCategories.filter((value) => availableCategories.has(value)));
  }

  const toggleCategoryFilter = (value: string) => {
    if (value === "All") {
      setSelectedCategories([]);
      return;
    }
    setSelectedCategories((current) => current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value]);
  };

  const syncCartAndOpen = async () => {
    if (update.isPending) return;
    if (missingFormTypeCount > 0) {
      setSaveError("Select form type (STRAIGHT or BEND) for all required products.");
      return;
    }
    setSaveError(null);
    try {
      if (changedLines.length > 0) {
        await update.mutateAsync({
          lines: changedLines.map((line) => ({
            productId: line.productId,
            quantity: line.quantity,
            formType: line.formType,
          })),
          idempotencyKey: newMutationKey(),
        });
      }
      router.push("/sp/orders/new/cart");
    } catch (error) {
      setSaveError(errorMessage(error));
    }
  };

  if (!cartId) return <BlockedEntry title="Add products" />;
  if (!catalog.data && catalog.isPending) return loadingScreen("Add products", { toolbar: flowToolbar });
  if (catalog.isError) {
    return (
      <SpScreen title="Add products" back toolbar={flowToolbar}>
        {orderStatePane(
          <ErrorState
            title="Catalogue unavailable"
            message={errorMessage(catalog.error)}
            onRetry={() => void catalog.refetch()}
          />,
        )}
      </SpScreen>
    );
  }
  return (
    <SpScreen title="Add products" back toolbar={flowToolbar}>
      <div className="sp-order-products-screen">
        <div className="sp-product-toolbar sp-order-product-toolbar">
          <div className="sp-order-product-search-row">
            <TextField
              placeholder="Search products"
              startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
              value={query}
              onChange={(event) => setQuery((event.target as HTMLInputElement).value)}
            />
            <button
              type="button"
              className="sp-order-product-filter-toggle"
              data-active={activeFilterCount ? "true" : "false"}
              aria-expanded={filtersExpanded}
              aria-controls="sp-product-category-filter-panel"
              onClick={() => setFiltersExpanded((current) => !current)}
            >
              <Icon name="FilterList" size={16} color="currentColor" />
              <span>Filters</span>
              {activeFilterCount ? <small>{activeFilterCount}</small> : null}
              <Icon
                name="KeyboardArrowDown"
                size={16}
                color="currentColor"
                style={{
                  transform: filtersExpanded ? "rotate(180deg)" : "rotate(0deg)",
                  transition: "transform var(--motion-duration-fast, 140ms) var(--motion-ease-standard, ease)",
                }}
              />
            </button>
          </div>
          <div
            id="sp-product-category-filter-panel"
            className="sp-filter-bar sp-order-product-filter-bar"
            role="group"
            aria-label="Product categories"
            data-open={filtersExpanded ? "true" : "false"}
          >
            {categoryOptions.map((option) => {
              const isActive = option.value === "All"
                ? selectedCategories.length === 0
                : selectedCategories.includes(option.value);
              return (
              <button
                className="sp-filter-chip sp-order-product-filter-chip"
                data-active={isActive ? "true" : "false"}
                key={option.value}
                onClick={() => toggleCategoryFilter(option.value)}
                type="button"
                aria-pressed={isActive}
              >
                <span>{option.label}</span>
                <small>{option.count}</small>
              </button>
              );
            })}
          </div>
        </div>
        {products.length ? (
          <div className="sp-product-list sp-order-product-list">
            {products.map((product) => {
              const quantity = draftQuantities[product.product_id] ?? product.qty_in_cart ?? 0;
              const lineBalance = poLineBalances?.[product.product_id];
              const canIncrement = (poCapQty == null || totalDraftQty < poCapQty)
                && (lineBalance == null || quantity < lineBalance);
              const formType = resolvedRequiredFormType(draftFormTypes[product.product_id]);
              const pricePending = product.unit_price_net_paise == null;
              const subtitle = product.category;
              const productLabel = product.name;
              return (
                <div
                  className="sp-product-row sp-order-product-row sp-order-line-card"
                  data-priced={pricePending ? "false" : "true"}
                  key={product.product_id}
                >
                  <span className="sp-product-image sp-order-product-image">
                    <CatalogProductImage imageUrl={product.image_url} productName={productLabel} />
                  </span>
                  <span className="sp-product-copy sp-order-product-copy">
                    <strong>{productLabel}</strong>
                    <span className="sp-order-product-subtitle">
                      {subtitle ? <span className="sp-order-product-category-label">{subtitle}</span> : null}
                      {subtitle && product.form_type_req ? (
                        <span className="sp-order-product-subtitle-sep" aria-hidden="true">·</span>
                      ) : null}
                      {product.form_type_req ? (
                        <FormTypeSelect
                          value={formType}
                          onChange={(nextFormType) => updateDraftFormType(product.product_id, nextFormType)}
                        />
                      ) : null}
                    </span>
                    {!pricePending ? (
                      <span className="sp-order-product-price">{productNetPriceLabel(product)} / {product.uom}</span>
                    ) : (
                      <span className="sp-order-product-price">{product.uom}</span>
                    )}
                  </span>
                  <span className="sp-product-control sp-order-product-control">
                    <DraftCartLineControl
                      product={product}
                      quantity={quantity}
                      disabled={update.isPending}
                      canIncrement={canIncrement}
                      onChange={(nextQuantity) => updateDraftQuantity(product.product_id, nextQuantity)}
                    />
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          orderStatePane(
            <EmptyState
              icon={query ? "SearchOutlined" : "InventoryOutlined"}
              title={query
                ? "No products found"
                : selectedCategories.length === 0
                  ? "No products available"
                  : "No products in selected filters"}
              message={query
                ? "Try another product name or switch category."
                : selectedCategories.length === 0
                  ? "The selected supplier has no catalogue products for this outlet."
                  : "Try removing one or more filters to find matching products."}
              actionLabel={query
                ? "Clear search"
                : selectedCategories.length === 0
                  ? "Back to order"
                  : "Clear filters"}
              onAction={() => {
                if (query) {
                  setQuery("");
                  return;
                }
                if (selectedCategories.length > 0) {
                  setSelectedCategories([]);
                  return;
                }
                router.push("/sp/orders/new");
              }}
            />,
          )
        )}
        {saveError ? (
          <div className="sp-content sp-order-flow-content">
            <SpInlineAlert tone="error">{saveError}</SpInlineAlert>
          </div>
        ) : null}
        {!saveError && missingFormTypeCount > 0 ? (
          <div className="sp-content sp-order-flow-content">
            <SpInlineAlert tone="warning">
              Select form type for {missingFormTypeCount} required product{missingFormTypeCount === 1 ? "" : "s"}.
            </SpInlineAlert>
          </div>
        ) : null}
      </div>
      <SpStickyFooter>
        <button
          className="sp-cart-cta"
          type="button"
          disabled={!itemCount || update.isPending}
          onClick={() => {
            void syncCartAndOpen();
          }}
        >
          <span>
            <Icon name="ShoppingCartOutlined" size={20} color="currentColor" />
            {itemCount} items
          </span>
          <span>
            {changedLineCount ? `Save ${changedLineCount} update${changedLineCount === 1 ? "" : "s"}` : "View cart"}
            <Icon name="KeyboardArrowRight" size={20} color="currentColor" />
          </span>
        </button>
      </SpStickyFooter>
    </SpScreen>
  );
}

function useCartProducts(cart: CartResponse | undefined, catalog: CatalogProductOut[]) {
  return useMemo(() => {
    if (!cart) return [];
    const catalogById = new Map(catalog.map((item) => [item.product_id, item]));
    return cart.lines.map((line) => ({
      line,
      product: catalogById.get(line.product_id),
    }));
  }, [cart, catalog]);
}

function cartQuantity(cart: CartResponse | undefined) {
  return cart?.lines.reduce((total, line) => total + line.qty, 0) ?? 0;
}

export function CartScreen() {
  const router = useRouter();
  const draft = useResolvedEntry();
  const { cartId } = draft;
  const cart = useCart(cartId);
  const catalog = useCatalog(cartId);
  const lines = useCartProducts(cart.data, catalog.data?.products ?? []);
  const flowToolbar = (
    <OrderFlowToolbar
      step="cart"
      includesManufacturer={draft.sellerBrands.length > 1}
      requiresPoStep={isPoBackedPath(cart.data?.order_path)}
    />
  );

  if (!cartId) return <BlockedEntry title="Cart" />;
  if (cart.isPending || catalog.isPending) return loadingScreen("Cart", { toolbar: flowToolbar });
  if (cart.isError || catalog.isError) {
    return (
      <SpScreen title="Cart" back toolbar={flowToolbar}>
        {orderStatePane(
          <ErrorState
            title="Cart unavailable"
            message={errorMessage(cart.error ?? catalog.error)}
            onRetry={() => {
              void cart.refetch();
              void catalog.refetch();
            }}
          />,
        )}
      </SpScreen>
    );
  }
  if (!cart.data?.lines.length) {
    return (
      <SpScreen title="Cart" back toolbar={flowToolbar}>
        {orderStatePane(
          <EmptyState
            icon="ShoppingCartOutlined"
            title="Your cart is empty"
            message="Add products to continue."
            actionLabel="Add products"
            onAction={() => router.push("/sp/orders/new/products")}
          />,
        )}
      </SpScreen>
    );
  }
  const totalItemCount = cartQuantity(cart.data);
  const pricedLines = lines.filter(({ line }) => line.unit_price_net_paise != null);
  const priceSummary = cartDisplayPriceSummary(
    lines,
    cart.data.scheme_discount_paise,
    totalItemCount,
    cart.data.as_of,
  );
  const discountBanner = cartDiscountBanner(
    lines,
    priceSummary.productDiscountPaise,
    cart.data.scheme_label,
    cart.data.scheme_discount_paise,
  );
  return (
    <SpScreen title="Cart" back toolbar={flowToolbar}>
      <div className="sp-content sp-order-flow-content sp-order-motion-stack">
        <div className="sp-order-cart-shell">
          <div className="sp-order-cart-header">
            <h2>My shopping cart</h2>
            <span>Total items {totalItemCount}</span>
          </div>
          <div className="sp-order-cart-product-list">
            {lines.map(({ line, product }) => {
              const subtitle = product?.category;
              const productName = product?.name ?? line.product_id;
              const discountRateBp = product?.discount_rate_bp ?? 0;
              const gstRateBp = product?.gst_rate_bp ?? 0;
              const unitPriceLabel = line.unit_price_net_paise != null
                ? unitPriceWithDiscountLabel(line.unit_price_net_paise, discountRateBp, gstRateBp)
                : null;
              const lineBalance = cart.data?.po_line_balances?.[line.product_id];
              const canIncrementLine = (cart.data?.po_cap_qty == null || totalItemCount < cart.data.po_cap_qty)
                && (lineBalance == null || line.qty < lineBalance);
              return (
                <SpCard
                  key={line.product_id}
                  padded={false}
                  style={{
                    borderRadius: "var(--radius-lg)",
                    borderStyle: line.unit_price_net_paise == null ? "dashed" : "solid",
                    background: line.unit_price_net_paise == null ? "var(--surface-muted)" : undefined,
                  }}
                >
                  <div className="sp-order-cart-product-row">
                    <span className="sp-product-image sp-order-product-image sp-order-cart-product-image">
                      <CatalogProductImage imageUrl={product?.image_url ?? null} productName={productName} />
                    </span>
                    <span className="sp-product-copy sp-order-product-copy sp-order-cart-product-copy">
                      <strong>{productName}</strong>
                      <span className="sp-order-product-subtitle">{subtitle}</span>
                      {unitPriceLabel ? (
                        <span className="sp-order-product-price">{unitPriceLabel} / {product?.uom}</span>
                      ) : (
                        <span className="sp-order-cart-price-pending">{product?.uom}</span>
                      )}
                      {line.unit_price_net_paise != null ? (
                        <span className="sp-order-cart-line-total">
                          Line total {money(priceSummary.lineTotalsByProductId.get(line.product_id) ?? 0)}
                        </span>
                      ) : null}
                      {line.price_changed ? <span className="sp-order-cart-price-update">Price updated</span> : null}
                    </span>
                    <span className="sp-order-cart-counter sp-order-cart-counter--item">
                      {product
                        ? (
                          <CartLineControl
                            cartId={cartId}
                            product={{ ...product, qty_in_cart: line.qty }}
                            formType={line.form_type}
                            canIncrement={canIncrementLine}
                          />
                        )
                        : <span className="sp-body-strong--sm">{line.qty}</span>}
                    </span>
                  </div>
                </SpCard>
              );
            })}
          </div>
        </div>
        <SchemeAppliedBanner
          label={discountBanner.label}
          discountPaise={discountBanner.discountPaise}
        />
        {pricedLines.length ? (
          <OrderPriceSummaryCard {...priceSummary} />
        ) : null}
      </div>
      <SpStickyFooter>
        <Button
          variant="filled"
          color="primary"
          label="Review order"
          onClick={() => router.push("/sp/orders/new/review")}
          style={{ width: "100%" }}
        />
      </SpStickyFooter>
    </SpScreen>
  );
}

export function OrderReviewScreen() {
  const router = useRouter();
  const draft = useResolvedEntry();
  const { cartId, clearDraft, idempotencyKey, entry } = draft;
  const cart = useCart(cartId);
  const catalog = useCatalog(cartId);
  const outletEsiId = cart.data?.outlet_esi_id ?? draft.selectedOutletEsiId;
  const context = useOrderContext(entry, outletEsiId);
  const selectedSeller = context.data?.sellers.find(
    (seller) => seller.seller_id === (entry?.sellerId ?? context.data?.selected_seller_id),
  );
  const currentPath = orderPathFromContext(cart.data, context.data, selectedSeller);
  const poRequired = isPoBackedPath(currentPath);
  const requiresManagerApproval = context.data?.requires_approval ?? selectedSeller?.manager_approval_required ?? false;
  const purchaseOrders = usePurchaseOrders(entry, false, outletEsiId);
  const submit = useSubmitOrder();
  const lines = useCartProducts(cart.data, catalog.data?.products ?? []);
  const { writesEnabled } = useConnectivity();
  const [preSubmitMessage, setPreSubmitMessage] = useState("");
  const [preSubmitActionPath, setPreSubmitActionPath] = useState<string | null>(null);
  const [preSubmitActionLabel, setPreSubmitActionLabel] = useState<string | null>(null);
  const [preSubmitChecking, setPreSubmitChecking] = useState(false);
  const flowToolbar = (
    <OrderFlowToolbar
      step="review"
      includesManufacturer={draft.sellerBrands.length > 1}
      requiresPoStep={poRequired}
    />
  );

  const setPreSubmitIssue = (
    message: string,
    actionPath: string | null,
    actionLabel: string | null,
  ) => {
    setPreSubmitMessage(message);
    setPreSubmitActionPath(actionPath);
    setPreSubmitActionLabel(actionLabel);
  };

  const runPreSubmitChecks = async () => {
    const [nextCart, nextContext] = await Promise.all([
      cart.refetch(),
      context.refetch(),
    ]);
    if (nextCart.error || !nextCart.data) {
      setPreSubmitIssue(
        "Could not refresh cart totals. Retry before submitting.",
        null,
        null,
      );
      return false;
    }
    if (nextContext.error || !nextContext.data) {
      setPreSubmitIssue(
        "Order context could not be refreshed. Review and try again.",
        "/sp/orders/new",
        "Review start order",
      );
      return false;
    }
    if (!nextCart.data.lines.length) {
      setPreSubmitIssue(
        "No products left in cart. Add products before submitting.",
        "/sp/orders/new/products",
        "Add products",
      );
      return false;
    }

    const contextSeller = nextContext.data.sellers.find(
      (seller) => seller.seller_id === (entry?.sellerId ?? nextContext.data.selected_seller_id),
    );
    const needsPo = isPoBackedPath(
      orderPathFromContext(nextCart.data, nextContext.data, contextSeller),
    );
    if (!needsPo) return true;

    if (!entry?.sellerId || !outletEsiId) {
      setPreSubmitIssue(
        "Purchase-order context is incomplete. Re-open order setup.",
        "/sp/orders/new",
        "Review start order",
      );
      return false;
    }

    const poResult = await purchaseOrders.refetch();
    if (poResult.error || !poResult.data) {
      setPreSubmitIssue(
        "Could not refresh open purchase orders. Try again.",
        "/sp/orders/new/po",
        "Select purchase order",
      );
      return false;
    }
    const sourcePoId = nextCart.data.source_po_id;
    if (!sourcePoId) {
      setPreSubmitIssue(
        "Select a purchase order before submitting this order.",
        "/sp/orders/new/po",
        "Select purchase order",
      );
      return false;
    }
    const selectedStillOpen = poResult.data.purchase_orders.some(
      (purchaseOrder) => purchaseOrder.po_id === sourcePoId,
    );
    if (!selectedStillOpen) {
      setPreSubmitIssue(
        "Selected purchase order is no longer open. Choose another one.",
        "/sp/orders/new/po",
        "Select another PO",
      );
      return false;
    }
    return true;
  };

  const onSubmit = async () => {
    if (submit.isPending || preSubmitChecking) return;
    setPreSubmitMessage("");
    setPreSubmitActionPath(null);
    setPreSubmitActionLabel(null);
    setPreSubmitChecking(true);
    try {
      const canSubmit = await runPreSubmitChecks();
      if (!canSubmit) return;
      submit.mutate({
        cartId,
        idempotencyKey,
      }, {
        onSuccess: (order) => {
          const visitReturnPath = entry?.visitId
            ? `/sp/route/visit?visitId=${encodeURIComponent(entry.visitId)}&outletRef=${encodeURIComponent(entry.outletId)}`
            : "/sp/route";
          clearDraft();
          router.replace(
            `/sp/orders/new/success?orderId=${encodeURIComponent(order.id)}&next=${encodeURIComponent(visitReturnPath)}`,
          );
        },
      });
    } finally {
      setPreSubmitChecking(false);
    }
  };

  if (!cartId) return <BlockedEntry title="Review order" />;
  if (cart.isPending || catalog.isPending || context.isPending) {
    return loadingScreen("Review order", { toolbar: flowToolbar });
  }
  if (cart.isError || catalog.isError || context.isError) {
    return (
      <SpScreen title="Review order" back toolbar={flowToolbar}>
        {orderStatePane(
          <ErrorState
            title="Review unavailable"
            message={errorMessage(cart.error ?? catalog.error ?? context.error)}
            onRetry={() => {
              void cart.refetch();
              void catalog.refetch();
              void context.refetch();
            }}
          />,
        )}
      </SpScreen>
    );
  }
  if (!cart.data?.lines.length) {
    return (
      <SpScreen title="Review order" back toolbar={flowToolbar}>
        {orderStatePane(
          <EmptyState
            icon="ShoppingCartOutlined"
            title="No products to review"
            message="Add products before submitting."
            actionLabel="Add products"
            onAction={() => router.push("/sp/orders/new/products")}
          />,
        )}
      </SpScreen>
    );
  }
  const submitError = submit.isError ? submitErrorMeta(submit.error) : null;
  const reviewIssue = submitError
    ? {
      tone: "error" as const,
      message: submitError.message,
      actionPath: submitError.actionPath,
      actionLabel: submitError.actionLabel,
    }
    : preSubmitMessage
      ? {
        tone: "warning" as const,
        message: preSubmitMessage,
        actionPath: preSubmitActionPath,
        actionLabel: preSubmitActionLabel,
      }
      : null;
  const pricedLines = lines.filter(({ line }) => line.unit_price_net_paise != null);
  const quantityOnlyLines = lines.filter(({ line }) => line.unit_price_net_paise == null);
  const priceSummary = cartDisplayPriceSummary(
    lines,
    cart.data.scheme_discount_paise,
    cartQuantity(cart.data),
    cart.data.as_of,
  );
  const discountBanner = cartDiscountBanner(
    lines,
    priceSummary.productDiscountPaise,
    cart.data.scheme_label,
    cart.data.scheme_discount_paise,
  );
  return (
    <SpScreen title="Review order" back toolbar={flowToolbar}>
      <div className="sp-content sp-order-flow-content sp-order-motion-stack">
        {!requiresManagerApproval ? (
          <SpInlineAlert tone={poRequired ? "warning" : "info"}>
            {poRequired
              ? "This PO-backed order will be sent directly for registration."
              : "This dealer order will be sent directly for registration."}
          </SpInlineAlert>
        ) : null}
        {pricedLines.length ? (
          <>
            <SpSectionLabel>
              {quantityOnlyLines.length
                ? `Priced items · ${pricedLines.length}`
                : `Order items · ${pricedLines.length}`}
            </SpSectionLabel>
            <SpCard padded={false}>
              <div className="sp-list">
                {pricedLines.map(({ line, product }) => (
                  <ListRow
                    key={line.product_id}
                    title={product?.name ?? line.product_id}
                    subtitle={reviewLineSubtitle(product, line.form_type, line.qty)}
                    meta={money(priceSummary.lineTotalsByProductId.get(line.product_id) ?? 0)}
                  />
                ))}
              </div>
            </SpCard>
            <SchemeAppliedBanner
              label={discountBanner.label}
              discountPaise={discountBanner.discountPaise}
            />
            <OrderPriceSummaryCard {...priceSummary} />
          </>
        ) : null}
        {quantityOnlyLines.length ? (
          <>
            <SpSectionLabel>
              {pricedLines.length
                ? `Quantity-only items · ${quantityOnlyLines.length}`
                : `Order items · ${quantityOnlyLines.length}`}
            </SpSectionLabel>
            <SpCard padded={false}>
              <div className="sp-list">
                {quantityOnlyLines.map(({ line, product }) => (
                  <ListRow
                    key={line.product_id}
                    title={product?.name ?? line.product_id}
                    subtitle={reviewLineSubtitle(product, line.form_type, line.qty)}
                  />
                ))}
              </div>
            </SpCard>
          </>
        ) : null}
        {reviewIssue ? (
          <SpInlineAlert tone={reviewIssue.tone}>{reviewIssue.message}</SpInlineAlert>
        ) : null}
        {reviewIssue?.actionPath && reviewIssue.actionLabel ? (
          <Button
            variant="outlined"
            color="primary"
            label={reviewIssue.actionLabel}
            onClick={() => {
              if (reviewIssue.actionPath) router.push(reviewIssue.actionPath);
            }}
            style={{ width: "100%" }}
          />
        ) : null}
      </div>
      <SpStickyFooter>
        <Button
          variant="filled"
          color="primary"
          loading={submit.isPending || preSubmitChecking}
          disabled={submit.isPending || preSubmitChecking || !writesEnabled}
          label={!writesEnabled
            ? "Connect to submit"
            : isPoBackedPath(cart.data.order_path)
              ? "Submit for approval"
              : "Submit DP order"}
          onClick={() => {
            void onSubmit();
          }}
          style={{ width: "100%" }}
        />
      </SpStickyFooter>
    </SpScreen>
  );
}

export function OrderSuccessScreen({ orderId, next }: { orderId: string; next: string }) {
  const router = useRouter();
  const order = useOrder(orderId);
  const message = order.data
    ? `${order.data.order_number} · ${order.data.outlet_name}`
    : "Your order has been submitted.";
  return (
    <SpScreen title="Order placed" back={false}>
      {orderStatePane(
        <EmptyState
          icon="CheckCircle"
          title="Order placed successfully"
          message={message}
          actionLabel="Done"
          onAction={() => router.replace(next)}
        />,
      )}
    </SpScreen>
  );
}

function OrderListItem({ order }: { order: OrderSummaryOut }) {
  const router = useRouter();
  return (
    <ListRow
      leading={<Icon name="ShoppingCartOutlined" size={22} color="var(--color-primary)" />}
      title={order.outlet_name}
      subtitle={`${order.counterparty_name} · ${order.business_date}`}
      meta={money(order.gross_total_paise)}
      trailing={(
        <StatusChip
          status={statusChip(order.status)}
          label={statusLabel(order.status)}
          type="outlined"
        />
      )}
      showChevron
      onClick={() => router.push(`/sp/orders/detail?orderId=${encodeURIComponent(order.id)}`)}
    />
  );
}

export function MyOrdersScreen() {
  const router = useRouter();
  const [filter, setFilter] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("status") ?? "";
  });
  const orders = useOrders(filter);
  const items = orders.data?.pages.flatMap((page) => page.items) ?? [];
  const listRef = useInfiniteScrollTrigger<HTMLDivElement>({
    hasNextPage: orders.hasNextPage,
    isFetchingNextPage: orders.isFetchingNextPage,
    fetchNextPage: orders.fetchNextPage,
  });
  const filterOptions = [
    ["", "All"],
    ["pending_approval", "Pending approval"],
    ["dp_created", "Registered"],
    ["submission_failed", "Failed"],
    ["rejected", "Rejected"],
  ] as const;

  if (orders.isPending) return loadingScreen("Orders", { bell: true, back: false });
  if (orders.isError) {
    return (
      <SpScreen title="Orders" bell>
        {orderStatePane(
          <ErrorState
            title="Orders unavailable"
            message={errorMessage(orders.error)}
            onRetry={() => void orders.refetch()}
          />,
        )}
      </SpScreen>
    );
  }
  return (
    <SpScreen title="Orders" bell>
      <div className="sp-filter-bar">
        {filterOptions.map(([value, label]) => (
          <button
            className="sp-filter-chip"
            data-active={filter === value}
            key={value}
            onClick={() => setFilter(value)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>
      <div className="sp-content">
        <SpSectionLabel>My orders</SpSectionLabel>
        <p className="sp-meta">{items.length} order{items.length === 1 ? "" : "s"} shown</p>
      </div>
      <div className="sp-list" ref={listRef}>
        {items.length
          ? items.map((order) => <OrderListItem key={order.id} order={order} />)
          : (
            orderStatePane(
              <EmptyState
                icon="ShoppingCartOutlined"
                title={filter ? "No matching orders" : "No orders yet"}
                message={filter
                  ? "Try another status filter."
                  : "Start an order from an active outlet visit."}
                actionLabel={filter ? "Show all" : "Go to route"}
                onAction={() => filter
                  ? setFilter("")
                  : router.push("/sp/route")}
              />,
            )
          )}
        {orders.hasNextPage ? (
          <Button
            variant="outlined"
            color="primary"
            loading={orders.isFetchingNextPage}
            label="Load more"
            onClick={() => void orders.fetchNextPage()}
            style={{ width: "100%" }}
          />
        ) : null}
      </div>
    </SpScreen>
  );
}

export function OrderDetailScreen({ orderId }: { orderId: string }) {
  const order = useOrder(orderId);
  const retry = useRetryOrder(orderId);
  const [retryKey, setRetryKey] = useState(createIdempotencyKey);

  if (order.isPending) return loadingScreen("Order");
  if (order.isError) {
    return (
      <SpScreen title="Order" back>
        {orderStatePane(
          <ErrorState
            title="Order unavailable"
            message={errorMessage(order.error)}
            onRetry={() => void order.refetch()}
          />,
        )}
      </SpScreen>
    );
  }
  if (!order.data) return loadingScreen("Order");
  const detail = order.data;
  const edited = detail.lines.some(
    (line) => line.approved_qty != null
      && line.approved_qty !== line.requested_qty,
  );
  const primaryStatusNote = detail.status === "submission_failed"
    ? {
      tone: "error" as const,
      message: detail.sub_status_reason
        ?? "Submission failed while creating the downstream order. Retry when ready.",
    }
    : detail.sub_status_reason
      ? {
        tone: detail.status === "submission_failed" ? "error" as const : "warning" as const,
        message: detail.sub_status_reason,
      }
      : detail.status === "dp_creation_pending"
        ? {
          tone: "warning" as const,
          message: "Registration is pending. No fulfilment status is available in SFA.",
        }
        : isAwaitingApprovalStatus(detail.status)
          ? {
            tone: "info" as const,
            message: "This order is waiting for manager approval.",
          }
          : detail.status === "dp_created"
            ? {
              tone: "info" as const,
              message: "Order is registered with Humbee Successfully",
            }
            : null;
  const pricedLines = detail.lines.filter((line) => line.unit_price_net_paise != null);
  const quantityOnlyLines = detail.lines.filter((line) => line.unit_price_net_paise == null);
  const totalItemCount = detail.lines.reduce(
    (total, line) => total + approvedLineQuantity(line),
    0,
  );
  const detailSummaryColumns = "minmax(0, 1fr) auto";
  const pricedSummaryLines = pricedLines.map(mapOrderDetailSummaryLine);
  const quantityOnlySummaryLines = quantityOnlyLines.map(mapOrderDetailSummaryLine);

  return (
    <SpScreen title={detail.order_number} back>
      <div className="sp-content sp-order-detail-content sp-order-motion-stack">
        <SpCard>
          <div className="sp-row">
            <div>
              <h2 className="sp-title">{detail.outlet_name}</h2>
              <p className="sp-meta">
                {detail.counterparty_name} · {detail.business_date}
              </p>
            </div>
            <StatusChip
              status={statusChip(detail.status)}
              label={statusLabel(detail.status)}
              type="filled"
            />
          </div>
        </SpCard>
        {primaryStatusNote ? (
          <SpInlineAlert tone={primaryStatusNote.tone}>{primaryStatusNote.message}</SpInlineAlert>
        ) : null}
        <OrderSummarySections
          pricedLines={pricedSummaryLines}
          quantityOnlyLines={quantityOnlySummaryLines}
          schemeLabel={detail.scheme_label}
          priceSummary={pricedLines.length ? {
            itemCount: totalItemCount,
            subtotalPaise: detail.subtotal_net_paise,
            productDiscountPaise: detail.product_discount_paise,
            schemeDiscountPaise: detail.scheme_discount_paise,
            gstPaise: detail.gst_amount_paise,
            totalPaise: detail.gross_total_paise,
          } : null}
        />
        {edited ? (
          <SpInlineAlert>
            Approved quantities differ from the submitted snapshot. The totals shown use the approved server values.
          </SpInlineAlert>
        ) : null}
        <SpCard>
          <div className="sp-stack">
            <SpStatusRow
              label="Items"
              value={detail.lines.length}
              valueAlign="right"
              columns={detailSummaryColumns}
            />
            {!pricedLines.length ? (
              <SpStatusRow
                label="Order total"
                value={money(detail.gross_total_paise)}
                tone="var(--color-primary)"
                valueAlign="right"
                columns={detailSummaryColumns}
              />
            ) : null}
            <SpStatusRow
              label="Submitted"
              value={new Date(detail.submitted_at).toLocaleString("en-IN")}
              valueAlign="right"
              columns={detailSummaryColumns}
            />
            {detail.approver_name ? (
              <SpStatusRow
                label="Approver"
                value={detail.approver_name}
                valueAlign="right"
                columns={detailSummaryColumns}
              />
            ) : null}
            {detail.downstream_dp_order_ref ? (
              <SpStatusRow
                label="Registration reference"
                value={detail.downstream_dp_order_ref}
                valueAlign="right"
                columns={detailSummaryColumns}
              />
            ) : null}
          </div>
        </SpCard>
        {retry.isError ? (
          <SpInlineAlert tone="error">{errorMessage(retry.error)}</SpInlineAlert>
        ) : null}
      </div>
      <SpStickyFooter>
        {detail.status === "submission_failed" ? (
          <Button
            variant="filled"
            color="primary"
            loading={retry.isPending}
            disabled={retry.isPending}
            label="Retry submission"
            leftIcon={<Icon name="Autorenew" size={20} color="currentColor" />}
            onClick={() => retry.mutate(retryKey, {
              onSuccess: () => setRetryKey(createIdempotencyKey()),
            })}
            style={{ width: "100%" }}
          />
        ) : (
          <Button
            variant="outlined"
            color="neutral"
            label="Back to orders"
            onClick={() => window.history.back()}
            style={{ width: "100%" }}
          />
        )}
      </SpStickyFooter>
    </SpScreen>
  );
}
