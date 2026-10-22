import type { QueryFunctionContext } from "@tanstack/react-query";

export function cancellableQuery<TData>(
  request: (signal: AbortSignal) => Promise<TData>,
) {
  return ({ signal }: QueryFunctionContext) => request(signal);
}
