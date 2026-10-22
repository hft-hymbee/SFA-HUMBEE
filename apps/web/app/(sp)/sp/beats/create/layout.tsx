import type { ReactNode } from "react";
import { BeatDraftProvider } from "@/src/features/beats/beat-draft";

export default function CreateBeatLayout({ children }: { children: ReactNode }) {
  return <BeatDraftProvider>{children}</BeatDraftProvider>;
}
