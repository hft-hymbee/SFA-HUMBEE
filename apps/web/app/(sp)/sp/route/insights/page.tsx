"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { EmptyState } from "humbee-design-system";
import { OutletInsightsScreen } from "@/src/features/outlets/insights-screen";
import { SpScreen } from "@/src/features/shell/components";

export default function Page() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const outletId = searchParams.get("outletId") ?? "";
  const name = searchParams.get("name") ?? "";
  if (!outletId) {
    return (
      <SpScreen title="Outlet insights" back>
        <EmptyState
          icon="LocationPin"
          title="Outlet unavailable"
          message="Choose an outlet from today's route."
          actionLabel="Back to route"
          onAction={() => router.push("/sp/route")}
        />
      </SpScreen>
    );
  }
  return <OutletInsightsScreen outletId={outletId} outletName={name} />;
}
