export class RuntimeConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RuntimeConfigurationError";
  }
}

export interface PublicRuntimeConfig {
  apiBaseUrl: string;
}

let cachedConfig: PublicRuntimeConfig | null = null;

function parseApiBaseUrl(value: string | undefined): string {
  if (!value) {
    throw new RuntimeConfigurationError(
      "NEXT_PUBLIC_SFA_API_BASE_URL is required.",
    );
  }

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new RuntimeConfigurationError(
      "NEXT_PUBLIC_SFA_API_BASE_URL must be an absolute URL.",
    );
  }

  if (!["http:", "https:"].includes(url.protocol)) {
    throw new RuntimeConfigurationError(
      "NEXT_PUBLIC_SFA_API_BASE_URL must use HTTP or HTTPS.",
    );
  }
  if (url.search || url.hash) {
    throw new RuntimeConfigurationError(
      "NEXT_PUBLIC_SFA_API_BASE_URL cannot include a query or fragment.",
    );
  }

  return url.toString().replace(/\/+$/, "");
}

function resolveBrowserApiBaseUrl(value: string): string {
  if (typeof window === "undefined") return value;

  const url = new URL(value);
  const pageHost = window.location.hostname;
  const loopbackApiHost = ["localhost", "127.0.0.1", "[::1]", "::1"].includes(url.hostname);
  const loopbackPageHost = ["localhost", "127.0.0.1", "::1"].includes(pageHost);

  if (loopbackApiHost && !loopbackPageHost) {
    // A LAN-opened dev UI must call the dev machine, not the browser device's localhost.
    url.hostname = pageHost;
    return url.toString().replace(/\/+$/, "");
  }

  return value;
}

export function getPublicRuntimeConfig(): PublicRuntimeConfig {
  if (!cachedConfig) {
    cachedConfig = {
      apiBaseUrl: resolveBrowserApiBaseUrl(
        parseApiBaseUrl(process.env.NEXT_PUBLIC_SFA_API_BASE_URL),
      ),
    };
  }
  return cachedConfig;
}
