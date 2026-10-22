"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ulid } from "ulid";
import { createIdempotencyKey } from "@/src/shared/api";
import { readSessionSync } from "@/src/shared/auth/session";
import { createBrowserCapabilities } from "@/src/shared/capabilities";
import type { OrderEntry, OutletSellersByBrandOut } from "./service";

const STORAGE_KEY = "humbee-sfa-order-draft";

interface ShipToDraftSelection {
  type: "self" | "dealer";
  outletId: string;
  esiId: string;
}

interface ShippingOverrideDraft {
  line1: string;
  line2: string;
  stateId: string;
  districtId: string;
  pincode: string;
}

interface AutoSkippedStepsDraft {
  esi: boolean;
  shipTo: boolean;
  po: boolean;
}

interface OrderDraftContextValue {
  activeVisitStopId: string;
  activeVisitOutletId: string;
  cartId: string;
  entry: OrderEntry | null;
  idempotencyKey: string;
  intentId: string;
  sellerBrands: OutletSellersByBrandOut[];
  selectedSourceIds: string[];
  selectedOutletEsiId: string;
  selectedSellerEsiId: string;
  shipToSelection: ShipToDraftSelection | null;
  shippingOverrideDraft: ShippingOverrideDraft | null;
  autoSkippedSteps: AutoSkippedStepsDraft;
  beginVisitOrder: (
    sourceIds: string[],
    stopId: string,
    entry?: OrderEntry,
    sellerBrands?: OutletSellersByBrandOut[],
    outletId?: string,
  ) => void;
  setSelectedEsi: (outletEsiId: string, sellerEsiId: string) => void;
  setAutoSkippedStep: (step: keyof AutoSkippedStepsDraft, skipped: boolean) => void;
  setShipToSelection: (selection: ShipToDraftSelection | null) => void;
  setShippingOverrideDraft: (value: ShippingOverrideDraft | null) => void;
  clearDraft: () => void;
  completeVisit: () => void;
  configureEntry: (entry: OrderEntry) => void;
  restartOrderEntry: (entry: OrderEntry) => void;
  setCartId: (cartId: string) => void;
}

interface StoredOrderDraft {
  version: 5;
  actorId: string;
  activeVisitStopId: string;
  activeVisitOutletId: string;
  cartId: string;
  entry: OrderEntry | null;
  idempotencyKey: string;
  intentId: string;
  sellerBrands: OutletSellersByBrandOut[];
  selectedSourceIds: string[];
  selectedOutletEsiId: string;
  selectedSellerEsiId: string;
  shipToSelection: ShipToDraftSelection | null;
  shippingOverrideDraft: ShippingOverrideDraft | null;
  autoSkippedSteps: AutoSkippedStepsDraft;
}

const OrderDraftContext = createContext<OrderDraftContextValue | null>(null);

function isOrderEntry(value: unknown): value is OrderEntry {
  if (!value || typeof value !== "object") return false;
  const entry = value as Record<string, unknown>;
  return typeof entry.visitId === "string"
    && typeof entry.outletId === "string"
    && typeof entry.manufacturerId === "string"
    && Boolean(entry.visitId && entry.outletId && entry.manufacturerId);
}

export function OrderDraftProvider({
  children,
}: {
  children: ReactNode;
}) {
  const actorId = readSessionSync()?.employeeId ?? "";
  const [activeVisitStopId, setActiveVisitStopId] = useState("");
  const [activeVisitOutletId, setActiveVisitOutletId] = useState("");
  const [cartId, setCartId] = useState("");
  const [entry, setEntry] = useState<OrderEntry | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState(createIdempotencyKey);
  const [intentId, setIntentId] = useState(ulid);
  const [sellerBrands, setSellerBrands] = useState<OutletSellersByBrandOut[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [selectedOutletEsiId, setSelectedOutletEsiId] = useState("");
  const [selectedSellerEsiId, setSelectedSellerEsiId] = useState("");
  const [shipToSelection, setShipToSelection] = useState<ShipToDraftSelection | null>(null);
  const [shippingOverrideDraft, setShippingOverrideDraft] = useState<ShippingOverrideDraft | null>(null);
  const [autoSkippedSteps, setAutoSkippedSteps] = useState<AutoSkippedStepsDraft>({
    esi: false,
    shipTo: false,
    po: false,
  });
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    let active = true;
    const storage = createBrowserCapabilities().storage;
    void storage.getItem(STORAGE_KEY).then((stored) => {
      if (!active) return;
      if (!stored) {
        setRestored(true);
        return;
      }
      try {
        const draft = JSON.parse(stored) as Partial<StoredOrderDraft>;
        if (
          draft.version !== 5
          || draft.actorId !== actorId
          || typeof draft.idempotencyKey !== "string"
          || typeof draft.intentId !== "string"
        ) {
          void storage.removeItem(STORAGE_KEY);
          setRestored(true);
          return;
        }
        setActiveVisitStopId(
          typeof draft.activeVisitStopId === "string"
            ? draft.activeVisitStopId
            : "",
        );
        setActiveVisitOutletId(
          typeof draft.activeVisitOutletId === "string"
            ? draft.activeVisitOutletId
            : "",
        );
        setCartId(typeof draft.cartId === "string" ? draft.cartId : "");
        setEntry(isOrderEntry(draft.entry) ? draft.entry : null);
        setIdempotencyKey(draft.idempotencyKey);
        setIntentId(draft.intentId);
        setSellerBrands(
          Array.isArray(draft.sellerBrands)
            ? draft.sellerBrands
            : [],
        );
        setSelectedSourceIds(
          Array.isArray(draft.selectedSourceIds)
            ? draft.selectedSourceIds.filter(
              (sourceId): sourceId is string => typeof sourceId === "string",
            )
            : [],
        );
        setSelectedOutletEsiId(
          typeof draft.selectedOutletEsiId === "string"
            ? draft.selectedOutletEsiId
            : "",
        );
        setSelectedSellerEsiId(
          typeof draft.selectedSellerEsiId === "string"
            ? draft.selectedSellerEsiId
            : "",
        );
        setShipToSelection(
          draft.shipToSelection
            && typeof draft.shipToSelection === "object"
            && (draft.shipToSelection.type === "self" || draft.shipToSelection.type === "dealer")
            && typeof draft.shipToSelection.outletId === "string"
            && typeof draft.shipToSelection.esiId === "string"
            ? draft.shipToSelection
            : null,
        );
        setShippingOverrideDraft(
          draft.shippingOverrideDraft
            && typeof draft.shippingOverrideDraft === "object"
            && typeof draft.shippingOverrideDraft.line1 === "string"
            && typeof draft.shippingOverrideDraft.line2 === "string"
            && typeof draft.shippingOverrideDraft.stateId === "string"
            && typeof draft.shippingOverrideDraft.districtId === "string"
            && typeof draft.shippingOverrideDraft.pincode === "string"
            ? draft.shippingOverrideDraft
            : draft.shippingOverrideDraft
              && typeof draft.shippingOverrideDraft === "object"
              && typeof draft.shippingOverrideDraft.line1 === "string"
              && typeof draft.shippingOverrideDraft.line2 === "string"
              && typeof draft.shippingOverrideDraft.stateId === "string"
              && typeof draft.shippingOverrideDraft.districtId === "string"
              ? {
                line1: draft.shippingOverrideDraft.line1,
                line2: draft.shippingOverrideDraft.line2,
                stateId: draft.shippingOverrideDraft.stateId,
                districtId: draft.shippingOverrideDraft.districtId,
                pincode: "",
              }
              : null,
        );
        setAutoSkippedSteps(
          draft.autoSkippedSteps
            && typeof draft.autoSkippedSteps === "object"
            && typeof draft.autoSkippedSteps.esi === "boolean"
            && typeof draft.autoSkippedSteps.shipTo === "boolean"
            ? {
              esi: draft.autoSkippedSteps.esi,
              shipTo: draft.autoSkippedSteps.shipTo,
              po: typeof draft.autoSkippedSteps.po === "boolean"
                ? draft.autoSkippedSteps.po
                : false,
            }
            : {
              esi: false,
              shipTo: false,
              po: false,
            },
        );
      } catch {
        void storage.removeItem(STORAGE_KEY);
      }
      setRestored(true);
    }).catch(() => {
      if (active) setRestored(true);
    });
    return () => {
      active = false;
    };
  }, [actorId]);

  useEffect(() => {
    if (!restored) return;
    const draft: StoredOrderDraft = {
      version: 5,
      actorId,
      activeVisitStopId,
      activeVisitOutletId,
      cartId,
      entry,
      idempotencyKey,
      intentId,
      sellerBrands,
      selectedSourceIds,
      selectedOutletEsiId,
      selectedSellerEsiId,
      shipToSelection,
      shippingOverrideDraft,
      autoSkippedSteps,
    };
    void createBrowserCapabilities().storage
      .setItem(STORAGE_KEY, JSON.stringify(draft))
      .catch(() => undefined);
  }, [
    activeVisitStopId,
    activeVisitOutletId,
    actorId,
    cartId,
    entry,
    idempotencyKey,
    intentId,
    restored,
    sellerBrands,
    selectedSourceIds,
    selectedOutletEsiId,
    selectedSellerEsiId,
    shipToSelection,
    shippingOverrideDraft,
    autoSkippedSteps,
  ]);

  const value = useMemo<OrderDraftContextValue>(() => ({
    activeVisitStopId,
    activeVisitOutletId,
    cartId,
    entry,
    idempotencyKey,
    intentId,
    sellerBrands,
    selectedSourceIds,
    selectedOutletEsiId,
    selectedSellerEsiId,
    shipToSelection,
    shippingOverrideDraft,
    autoSkippedSteps,
    beginVisitOrder: (sourceIds, stopId, nextEntry, nextSellerBrands = [], outletId = "") => {
      setActiveVisitStopId(stopId);
      setActiveVisitOutletId(outletId || nextEntry?.outletId || "");
      setSellerBrands(nextSellerBrands);
      setSelectedSourceIds(sourceIds);
      setEntry(nextEntry ?? null);
      setSelectedOutletEsiId("");
      setSelectedSellerEsiId("");
      setShipToSelection(null);
      setShippingOverrideDraft(null);
      setAutoSkippedSteps({ esi: false, shipTo: false, po: false });
      setCartId("");
      setIdempotencyKey(createIdempotencyKey());
      setIntentId(ulid());
    },
    setSelectedEsi: (outletEsiId, sellerEsiId) => {
      setSelectedOutletEsiId(outletEsiId);
      setSelectedSellerEsiId(sellerEsiId);
    },
    setAutoSkippedStep: (step, skipped) => {
      setAutoSkippedSteps((current) => (
        current[step] === skipped
          ? current
          : { ...current, [step]: skipped }
      ));
    },
    setShipToSelection,
    setShippingOverrideDraft,
    clearDraft: () => {
      setActiveVisitStopId("");
      setActiveVisitOutletId("");
      setCartId("");
      setEntry(null);
      setSellerBrands([]);
      setSelectedSourceIds([]);
      setSelectedOutletEsiId("");
      setSelectedSellerEsiId("");
      setShipToSelection(null);
      setShippingOverrideDraft(null);
      setAutoSkippedSteps({ esi: false, shipTo: false, po: false });
      setIdempotencyKey(createIdempotencyKey());
      setIntentId(ulid());
    },
    completeVisit: () => setActiveVisitStopId(""),
    configureEntry: (nextEntry) => {
      const changed = !entry
        || entry.visitId !== nextEntry.visitId
        || entry.outletId !== nextEntry.outletId
        || entry.manufacturerId !== nextEntry.manufacturerId
        || entry.sellerId !== nextEntry.sellerId;
      if (!changed) return;
      const sellerAddedOnly = Boolean(
        entry
        && !entry.sellerId
        && nextEntry.sellerId
        && cartId
        && entry.visitId === nextEntry.visitId
        && entry.outletId === nextEntry.outletId
        && entry.manufacturerId === nextEntry.manufacturerId,
      );
      setEntry(nextEntry);
      setActiveVisitOutletId(nextEntry.outletId);
      setSelectedSourceIds([nextEntry.manufacturerId]);
      if (sellerAddedOnly) return;
      setSelectedOutletEsiId("");
      setSelectedSellerEsiId("");
      setShipToSelection(null);
      setShippingOverrideDraft(null);
      setAutoSkippedSteps({ esi: false, shipTo: false, po: false });
      setCartId("");
      setIdempotencyKey(createIdempotencyKey());
      setIntentId(ulid());
    },
    restartOrderEntry: (nextEntry) => {
      setEntry(nextEntry);
      setActiveVisitOutletId(nextEntry.outletId);
      setSelectedSourceIds([nextEntry.manufacturerId]);
      setSelectedOutletEsiId("");
      setSelectedSellerEsiId("");
      setShipToSelection(null);
      setShippingOverrideDraft(null);
      setAutoSkippedSteps({ esi: false, shipTo: false, po: false });
      setCartId("");
      setIdempotencyKey(createIdempotencyKey());
      setIntentId(ulid());
    },
    setCartId,
  }), [
    activeVisitStopId,
    activeVisitOutletId,
    cartId,
    entry,
    idempotencyKey,
    intentId,
    sellerBrands,
    selectedSourceIds,
    selectedOutletEsiId,
    selectedSellerEsiId,
    shipToSelection,
    shippingOverrideDraft,
    autoSkippedSteps,
  ]);

  return (
    <OrderDraftContext.Provider value={value}>
      {children}
    </OrderDraftContext.Provider>
  );
}

export function useOrderDraft() {
  const context = useContext(OrderDraftContext);
  if (!context) {
    throw new Error("useOrderDraft must be used within OrderDraftProvider");
  }
  return context;
}
