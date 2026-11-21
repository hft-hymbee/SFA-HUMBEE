"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { LeadDetailScreen } from "@/src/features/leads/screens";

function LeadDetailPage() {
  const leadId = useSearchParams().get("id") ?? "";
  return <LeadDetailScreen key={leadId} leadId={leadId} />;
}

export default function Page() {
  return (
    <Suspense>
      <LeadDetailPage />
    </Suspense>
  );
}
