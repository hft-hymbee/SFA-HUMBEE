/**
 * Business profiler (BP): an outlet is "filled" when its current BP % is at or above the threshold.
 * The backend owns the threshold (`business_profiler_filled_threshold_pct`) but does not expose it
 * yet, so this mirrors its default for per-outlet colouring. Filled counts always come from the API.
 */
export const BP_FILLED_THRESHOLD_PCT = 80;

export function isBpFilled(pct: number) {
  return pct >= BP_FILLED_THRESHOLD_PCT;
}

export function formatBpPct(pct: number) {
  return `${Math.round(pct)}%`;
}
