"use client";

import { useSearchParams } from "next/navigation";
import { StartOrderScreen } from "@/src/features/orders/screens";
import type { OrderEntry } from "@/src/features/orders/service";

export default function Page() {
  const query = useSearchParams();
  const visitId = query.get("visitId") ?? "";
  const outletId = query.get("outletId") ?? "";
  const manufacturerId = query.get("manufacturerId") ?? "";
  const sellerId = query.get("sellerId") ?? undefined;
  const entry: OrderEntry | null = visitId && outletId && manufacturerId
    ? { visitId, outletId, manufacturerId, sellerId }
    : null;
  return <StartOrderScreen entry={entry} />;
}
