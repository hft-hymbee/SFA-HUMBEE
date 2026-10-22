import {
  captureLeadApiV1LeadsPost,
  type CaptureLeadBody,
  type LeadOut,
} from "@humbee/api-contract";
import {
  createIdempotencyKey,
  getBrowserApiClient,
  idempotencyHeaders,
} from "@/src/shared/api";

export type { CaptureLeadBody, LeadOut } from "@humbee/api-contract";

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function client() {
  return getBrowserApiClient();
}

export const leadsService = {
  async captureLead(body: CaptureLeadBody, idempotencyKey = createIdempotencyKey()): Promise<LeadOut> {
    return unwrap(await captureLeadApiV1LeadsPost({
      client: client(),
      body,
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
  },
};
