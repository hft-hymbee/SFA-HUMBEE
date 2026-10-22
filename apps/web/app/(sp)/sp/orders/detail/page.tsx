"use client";

import { useSearchParams } from "next/navigation";
import { EmptyState } from "humbee-design-system";
import { OrderDetailScreen } from "@/src/features/orders/screens";
import { SpScreen } from "@/src/features/shell/components";

export default function Page() {
  const orderId = useSearchParams().get("orderId");
  if (!orderId) {
    return (
      <SpScreen title="Order" back>
        <EmptyState
          icon="InventoryOutlined"
          title="Order unavailable"
          message="Choose an order from My orders."
        />
      </SpScreen>
    );
  }
  return <OrderDetailScreen orderId={orderId} />;
}
