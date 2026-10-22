"use client";

import { useAppMutation } from "@/src/shared/state";
import { leadsService, type CaptureLeadBody } from "./service";

export function useCaptureLead() {
  return useAppMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CaptureLeadBody;
      idempotencyKey?: string;
    }) => leadsService.captureLead(body, idempotencyKey),
  });
}
