"use client";

import { Suspense } from "react";
import { PunchBlockedScreen } from "@/src/features/attendance/screens";
import { useSearchParams } from "next/navigation";

function PunchBlockedPage() {
  const reason = useSearchParams().get("reason");
  const blockedReason = reason === "gpsoff" ? reason : "permission";
  return <PunchBlockedScreen reason={blockedReason} />;
}

export default function Page() {
  return (
    <Suspense>
      <PunchBlockedPage />
    </Suspense>
  );
}
