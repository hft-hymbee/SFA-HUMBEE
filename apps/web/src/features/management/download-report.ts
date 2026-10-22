import { readSessionSync } from "@/src/shared/auth/session";
import { getPublicRuntimeConfig } from "@/src/shared/api/runtime-config";

function filenameFromDisposition(disposition: string | null): string | null {
  const match = disposition ? /filename="?([^"]+)"?/.exec(disposition) : null;
  return match?.[1] ?? null;
}

export async function downloadAdminReport(path: string, fallbackFilename: string): Promise<void> {
  const accessToken = readSessionSync()?.accessToken;
  const response = await fetch(`${getPublicRuntimeConfig().apiBaseUrl}${path}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  });
  if (!response.ok) {
    throw new Error(`Report download failed (${response.status})`);
  }
  const filename = filenameFromDisposition(response.headers.get("Content-Disposition")) ?? fallbackFilename;
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
