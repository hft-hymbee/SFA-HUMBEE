"use client";

import { useSearchParams } from "next/navigation";
import { EmptyState } from "humbee-design-system";
import { VisitOutcomeScreen } from "@/src/features/routes/screens";
import { SpScreen } from "@/src/features/shell/components";

export default function Page() {
  const searchParams = useSearchParams();
  const visitId = searchParams.get("visitId");
  const forceOrderCompleted = searchParams.get("withOrder") === "1";
  if (!visitId) {
    return <SpScreen title="Log visit outcome" back><EmptyState icon="LocationPin" title="Visit unavailable" message="Choose an active visit first." /></SpScreen>;
  }
  return <VisitOutcomeScreen stopId={visitId} forceOrderCompleted={forceOrderCompleted} />;
}
