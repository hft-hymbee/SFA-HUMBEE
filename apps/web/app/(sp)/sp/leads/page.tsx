"use client";

import { Suspense } from "react";
import { MyLeadsScreen } from "@/src/features/leads/screens";

export default function Page() {
  return (
    <Suspense>
      <MyLeadsScreen />
    </Suspense>
  );
}
