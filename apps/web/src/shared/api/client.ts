import {
  createContractClient,
  type ContractClient,
} from "@humbee/api-contract/client";
import { readSessionSync } from "@/src/shared/auth/session";
import { getPublicRuntimeConfig } from "./runtime-config";

interface ApiErrorBody {
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
    request_id?: unknown;
  };
}

export class ApiClientError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: unknown;
  readonly requestId: string | null;

  constructor({
    code,
    status,
    message,
    details,
    requestId,
  }: {
    code: string;
    status: number;
    message: string;
    details: unknown;
    requestId: string | null;
  }) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.details = details;
    this.requestId = requestId;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function readErrorPayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return response.text();
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}

function mapError(response: Response, payload: unknown): ApiClientError {
  const body = isRecord(payload) ? (payload as ApiErrorBody) : undefined;
  const error = body?.error;
  const code = typeof error?.code === "string" ? error.code : "invalid_error_response";
  const message =
    typeof error?.message === "string"
      ? error.message
      : `API request failed with status ${response.status}.`;
  const bodyRequestId =
    typeof error?.request_id === "string" ? error.request_id : null;

  return new ApiClientError({
    code,
    status: response.status,
    message,
    details: error?.details ?? payload,
    requestId: bodyRequestId ?? response.headers.get("x-request-id"),
  });
}

function createAuthenticatedFetch(
  getAccessToken: () => string | null | Promise<string | null>,
  fetchFn: typeof fetch = fetch,
  retryUnauthorized = true,
): typeof fetch {
  return async (input, init) => {
    const request = new Request(input, init);
    const headers = new Headers(request.headers);
    headers.set("Accept", "application/json");

    if (
      request.method !== "GET"
      && request.method !== "HEAD"
      && typeof navigator !== "undefined"
      && !navigator.onLine
    ) {
      throw new ApiClientError({
        code: "offline_write_blocked",
        status: 0,
        message: "Connect to the internet before trying this action.",
        details: null,
        requestId: null,
      });
    }

    const accessToken = await getAccessToken();
    if (accessToken) {
      headers.set("Authorization", `Bearer ${accessToken}`);
    }

    const retrySource = retryUnauthorized ? request.clone() : request;
    const send = async (outgoing: Request) => {
      try {
        return await fetchFn(outgoing);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          throw error;
        }
        throw new ApiClientError({
          code: "network_unavailable",
          status: 0,
          message: "The API is unavailable. Check your connection and try again.",
          details: error,
          requestId: null,
        });
      }
    };

    let response = await send(new Request(request, { headers }));

    let responseError: ApiClientError | null = null;
    if (!response.ok) {
      responseError = mapError(
        response,
        await readErrorPayload(response.clone()),
      );
    }
    if (
      retryUnauthorized
      && unauthorizedHandler
      && (response.status === 401 || responseError?.code === "account_deactivated")
    ) {
      unauthorizedFlight ??= unauthorizedHandler(responseError!).finally(() => {
        unauthorizedFlight = null;
      });
      const refreshed = await unauthorizedFlight;
      if (refreshed) {
        const retryHeaders = new Headers(request.headers);
        retryHeaders.set("Accept", "application/json");
        const retryToken = await getAccessToken();
        if (retryToken) {
          retryHeaders.set("Authorization", `Bearer ${retryToken}`);
        }
        response = await send(new Request(retrySource, { headers: retryHeaders }));
        responseError = response.ok
          ? null
          : mapError(response, await readErrorPayload(response.clone()));
      }
    }

    if (!response.ok) {
      throw responseError ?? mapError(
        response,
        await readErrorPayload(response.clone()),
      );
    }

    return response;
  };
}

let browserClient: ContractClient | null = null;
let unauthorizedHandler: ((error: ApiClientError) => Promise<boolean>) | null = null;
let unauthorizedFlight: Promise<boolean> | null = null;

export function registerUnauthorizedHandler(
  handler: (error: ApiClientError) => Promise<boolean>,
) {
  unauthorizedHandler = handler;
}

export function createSessionApiClient(accessToken?: string): ContractClient {
  return createContractClient({
    baseUrl: getPublicRuntimeConfig().apiBaseUrl,
    fetch: createAuthenticatedFetch(() => accessToken ?? null, fetch, false),
    throwOnError: true,
  });
}

export function getBrowserApiClient(): ContractClient {
  if (typeof window === "undefined") {
    throw new Error("The browser API client cannot be created on the server.");
  }
  if (!browserClient) {
    browserClient = createContractClient({
      baseUrl: getPublicRuntimeConfig().apiBaseUrl,
      fetch: createAuthenticatedFetch(() => readSessionSync()?.accessToken ?? null),
      throwOnError: true,
    });
  }
  return browserClient;
}

export function createIdempotencyKey(): string {
  if (typeof crypto === "undefined" || typeof crypto.randomUUID !== "function") {
    throw new Error("Secure idempotency key generation is unavailable.");
  }
  return crypto.randomUUID();
}

export function idempotencyHeaders(idempotencyKey: string) {
  if (!idempotencyKey.trim()) {
    throw new Error("An idempotency key is required.");
  }
  return { "Idempotency-Key": idempotencyKey } as const;
}
