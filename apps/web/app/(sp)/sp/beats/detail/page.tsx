"use client";

import { useSearchParams } from "next/navigation";
import { EmptyState } from "humbee-design-system";
import { BeatDetailScreen } from "@/src/features/beats/screens";
import { SpScreen } from "@/src/features/shell/components";

export default function Page() {
  const searchParams = useSearchParams();
  const beatId = searchParams.get("beatId");
  const status = searchParams.get("status");
  if (!beatId) {
    return <SpScreen title="Beat" back><EmptyState icon="Calendar" title="Beat unavailable" message="Choose a beat from My beats." /></SpScreen>;
  }
  return <BeatDetailScreen beatId={beatId} knownStatus={status} />;
}
