"use client";

import { useSearchParams } from "next/navigation";
import { OutletOnboardingDetailScreen } from "@/src/features/outlets/screens";

export default function Page() {
  const candidateId = useSearchParams().get("candidateId") ?? "";
  return <OutletOnboardingDetailScreen candidateId={candidateId} />;
}
