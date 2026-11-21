import { ApiClientError } from "@/src/shared/api";

const LEAD_ID_PATTERN = /^[0-9A-HJKMNP-TV-Z]{26}$/;

/** Lead ids are ULIDs; anything else (e.g. `counts-by-employee` in `?id=`) must never reach the API. */
export function isLeadId(value: string) {
  return LEAD_ID_PATTERN.test(value);
}

export function isNotFound(error: unknown) {
  return error instanceof ApiClientError && error.status === 404;
}
