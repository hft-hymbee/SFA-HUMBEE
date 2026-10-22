import type { ReactNode } from "react";
import { OrderDraftProvider } from "@/src/features/orders/order-draft";
import { RouteTransition, SalesPersonShell } from "@/src/shared/navigation";

export default function SalesPersonLayout({ children }: { children: ReactNode }) {
  return (
    <OrderDraftProvider>
      <SalesPersonShell>
        <RouteTransition>{children}</RouteTransition>
      </SalesPersonShell>
    </OrderDraftProvider>
  );
}
