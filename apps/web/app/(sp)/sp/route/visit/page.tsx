"use client";

import { useSearchParams } from "next/navigation";
import { EmptyState } from "humbee-design-system";
import { OutletVisitScreen } from "@/src/features/routes/screens";
import { SpScreen } from "@/src/features/shell/components";

export default function Page() {
  const searchParams = useSearchParams();
  const visitId = searchParams.get("visitId");
  const outletRef = searchParams.get("outletRef");
  if (!visitId && !outletRef) {
    return <SpScreen title="Visit" back><EmptyState icon="LocationPin" title="Visit unavailable" message="Choose a stop from today's route." /></SpScreen>;
  }
  return (
    <OutletVisitScreen
      stopId={visitId}
      outletRef={outletRef}
      outletName={searchParams.get("name")}
      outletArea={searchParams.get("area")}
    />
  );
}
