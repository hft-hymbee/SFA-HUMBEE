import { createBrowserCapabilities } from "@/src/shared/capabilities";
import {
  SESSION_KEY,
  SessionStore,
  type AuthSession,
  type OtpChallenge,
  type UserRole,
} from "./index";

export const SESSION_STORAGE_KEY = SESSION_KEY;
export const SESSION_CHANGE_EVENT = "humbee-sfa-session-change";
export const PENDING_LOGIN_KEY = "humbee.sfa.pending-login";
export const PENDING_CHANGE_EVENT = "humbee-sfa-pending-login-change";
export const RETURN_PATH_KEY = "humbee.sfa.return-path";
export const DEACTIVATED_CHALLENGE_KEY = "humbee.sfa.deactivated-challenge";
const DEVICE_ID_KEY = "humbee.sfa.device-id";
const ORDER_DRAFT_KEY = "humbee-sfa-order-draft";

export interface PendingLogin {
  challenge: OtpChallenge;
  phone?: string;
  purpose: "login" | "reauth";
}

let browserStore: SessionStore | null = null;
let sessionSnapshotRaw: string | null = null;
let sessionSnapshot: AuthSession | null = null;
let pendingSnapshotRaw: string | null = null;
let pendingSnapshot: PendingLogin | null = null;

export function getBrowserSessionStore(): SessionStore {
  if (!browserStore) {
    browserStore = new SessionStore(createBrowserCapabilities().storage);
  }
  return browserStore;
}

export function readSessionSync(): AuthSession | null {
  if (typeof window === "undefined") return null;
  const rawValue = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (rawValue === sessionSnapshotRaw) return sessionSnapshot;
  sessionSnapshotRaw = rawValue;
  if (!rawValue) {
    sessionSnapshot = null;
    return null;
  }
  try {
    sessionSnapshot = JSON.parse(rawValue) as AuthSession;
    return sessionSnapshot;
  } catch {
    sessionSnapshot = null;
    return null;
  }
}

export function subscribeToSession(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(SESSION_CHANGE_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(SESSION_CHANGE_EVENT, onChange);
  };
}

export async function writeSession(session: AuthSession) {
  await getBrowserSessionStore().write(session);
  sessionSnapshotRaw = JSON.stringify(session);
  sessionSnapshot = session;
  clearDeactivatedChallenge();
  window.dispatchEvent(new Event(SESSION_CHANGE_EVENT));
}

export async function clearSession() {
  await getBrowserSessionStore().clear();
  sessionSnapshotRaw = null;
  sessionSnapshot = null;
  window.dispatchEvent(new Event(SESSION_CHANGE_EVENT));
}

export async function markSessionForReauth() {
  const session = readSessionSync();
  if (!session || session.status === "reauth_required") {
    return;
  }
  await writeSession({ ...session, status: "reauth_required" });
}

export function getServerSession(): AuthSession | null {
  return null;
}

export function readPendingLogin(): PendingLogin | null {
  if (typeof window === "undefined") return null;
  const rawValue = window.sessionStorage.getItem(PENDING_LOGIN_KEY);
  if (rawValue === pendingSnapshotRaw) return pendingSnapshot;
  pendingSnapshotRaw = rawValue;
  if (!rawValue) {
    pendingSnapshot = null;
    return null;
  }
  try {
    pendingSnapshot = JSON.parse(rawValue) as PendingLogin;
    return pendingSnapshot;
  } catch {
    window.sessionStorage.removeItem(PENDING_LOGIN_KEY);
    pendingSnapshotRaw = null;
    pendingSnapshot = null;
    return null;
  }
}

export function writePendingLogin(pending: PendingLogin) {
  clearDeactivatedChallenge();
  const rawValue = JSON.stringify(pending);
  window.sessionStorage.setItem(PENDING_LOGIN_KEY, rawValue);
  pendingSnapshotRaw = rawValue;
  pendingSnapshot = pending;
  window.dispatchEvent(new Event(PENDING_CHANGE_EVENT));
}

export function clearPendingLogin() {
  window.sessionStorage.removeItem(PENDING_LOGIN_KEY);
  pendingSnapshotRaw = null;
  pendingSnapshot = null;
  window.dispatchEvent(new Event(PENDING_CHANGE_EVENT));
}

export function getServerPendingLogin(): PendingLogin | null {
  return null;
}

// In-memory only: sessionStorage would let a later visitor on this browser
// reopen /auth/deactivated and fetch the prior user's manager phone.
let deactivatedChallengeId: string | null = null;

function dropStoredDeactivatedChallenge() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(DEACTIVATED_CHALLENGE_KEY);
}

export function rememberDeactivatedChallenge(challengeId: string) {
  deactivatedChallengeId = challengeId;
  dropStoredDeactivatedChallenge();
}

export function readDeactivatedChallenge() {
  dropStoredDeactivatedChallenge();
  return deactivatedChallengeId;
}

export function subscribeToDeactivatedChallenge() {
  return () => {};
}

export function getServerDeactivatedChallenge(): string | null {
  return null;
}

export function clearDeactivatedChallenge() {
  deactivatedChallengeId = null;
  dropStoredDeactivatedChallenge();
}

export function subscribeToPendingLogin(onChange: () => void) {
  window.addEventListener(PENDING_CHANGE_EVENT, onChange);
  return () => window.removeEventListener(PENDING_CHANGE_EVENT, onChange);
}

export function storeReturnPath(path: string) {
  window.sessionStorage.setItem(RETURN_PATH_KEY, path);
}

export function takeReturnPath() {
  const path = window.sessionStorage.getItem(RETURN_PATH_KEY);
  window.sessionStorage.removeItem(RETURN_PATH_KEY);
  return path;
}

export async function getClientDeviceId() {
  const storage = createBrowserCapabilities().storage;
  const existing = await storage.getItem(DEVICE_ID_KEY);
  if (existing) {
    return existing;
  }
  if (typeof crypto === "undefined" || typeof crypto.randomUUID !== "function") {
    throw new Error("Secure device identifier generation is unavailable.");
  }
  const deviceId = crypto.randomUUID();
  await storage.setItem(DEVICE_ID_KEY, deviceId);
  return deviceId;
}

export async function clearSensitiveClientState() {
  const storage = createBrowserCapabilities().storage;
  await Promise.all([
    clearSession(),
    storage.removeItem(ORDER_DRAFT_KEY),
  ]);
  clearPendingLogin();
  clearDeactivatedChallenge();
  window.sessionStorage.removeItem(RETURN_PATH_KEY);
}

export function homeForRole(role: UserRole) {
  if (role === "manager") return "/manager";
  if (role === "admin") return "/admin";
  return "/sp";
}
