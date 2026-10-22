"use client";

import { useSearchParams } from "next/navigation";
import { EmptyState } from "humbee-design-system";
import { OrderSuccessScreen } from "@/src/features/orders/screens";
import { SpScreen } from "@/src/features/shell/components";

export default function Page() {
  const searchParams = useSearchParams();
  const orderId = searchParams.get("orderId");
  const next = searchParams.get("next") ?? "/sp/route";
  if (!orderId) {
    return (
      <SpScreen title="Order placed" back={false}>
        <EmptyState
          icon="CheckCircle"
          title="Order placed successfully"
          message="Your order has been submitted."
          actionLabel="Done"
          onAction={() => {
            window.location.href = next;
          }}
        />
      </SpScreen>
    );
  }
  return <OrderSuccessScreen orderId={orderId} next={next} />;
}
