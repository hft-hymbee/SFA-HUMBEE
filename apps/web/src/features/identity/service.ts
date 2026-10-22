import { Capacitor } from "@capacitor/core";
import {
  getAuthConfigApiV1AuthConfigGet,
  getManagerContactApiV1AuthManagerContactGet,
  getMeApiV1MeGet,
  logoutApiV1AuthLogoutPost,
  refreshTokenApiV1AuthTokenRefreshPost,
  requestOtpApiV1AuthOtpRequestPost,
  verifyOtpApiV1AuthOtpVerifyPost,
  type AuthConfigResponse,
  type ManagerContactResponse,
  type MeResponse,
  type TokenResponse,
} from "@humbee/api-contract";
import type {
  AuthSession,
  OtpChallenge,
  OtpVerificationResult,
  PhoneOtpAuthService,
  UserRole,
} from "@/src/shared/auth";
import {
  ApiClientError,
  createIdempotencyKey,
  createSessionApiClient,
  idempotencyHeaders,
  registerUnauthorizedHandler,
} from "@/src/shared/api";
import {
  clearSensitiveClientState,
  getClientDeviceId,
  markSessionForReauth,
  readSessionSync,
  rememberDeactivatedChallenge,
  writePendingLogin,
  writeSession,
} from "@/src/shared/auth/session";
import { clearAppQueryState } from "@/src/shared/state";

const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "1.0.0";

function unwrap<T>(result: { data: T }): T {
  return result.data;
}

function roleFromApi(role: string): UserRole {
  if (role === "sales_person") return "sp";
  if (role === "manager" || role === "admin") return role;
  throw new Error(`Unsupported server role: ${role}`);
}

function phoneE164(phone: string) {
  const digits = phone.replace(/\D/g, "");
  const national = digits.startsWith("91") && digits.length === 12
    ? digits.slice(2)
    : digits;
  return `+91${national}`;
}

function secondsUntil(iso: string) {
  return Math.max(0, Math.ceil((Date.parse(iso) - Date.now()) / 1000));
}

function platform(): "web_pwa" | "android" | "ios" {
  const current = Capacitor.getPlatform();
  if (current === "android" || current === "ios") {
    return current;
  }
  return "web_pwa";
}

function sessionFrom(
  tokens: TokenResponse,
  profile: MeResponse,
  deviceId: string,
): AuthSession {
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    deviceId,
    employeeId: profile.id,
    displayName: profile.full_name,
    role: roleFromApi(profile.role),
    expiresAtIso: new Date(Date.now() + tokens.expires_in * 1000).toISOString(),
    status: "active",
    refreshIdempotencyKey: createIdempotencyKey(),
    logoutIdempotencyKey: createIdempotencyKey(),
  };
}

async function resolveProfile(accessToken: string) {
  return unwrap(await getMeApiV1MeGet({
    client: createSessionApiClient(accessToken),
    throwOnError: true,
  }));
}

async function refreshStoredSession() {
  const current = readSessionSync();
  if (!current) {
    return null;
  }
  const tokens = unwrap(await refreshTokenApiV1AuthTokenRefreshPost({
    client: createSessionApiClient(),
    body: {
      client_device_id: current.deviceId,
      refresh_token: current.refreshToken,
    },
    headers: idempotencyHeaders(current.refreshIdempotencyKey),
    throwOnError: true,
  }));
  const profile = await resolveProfile(tokens.access_token);
  const session = sessionFrom(tokens, profile, current.deviceId);
  await writeSession(session);
  return session;
}

async function forceLocalLogout() {
  clearAppQueryState();
  await clearSensitiveClientState();
}

let bootstrapFlight: Promise<AuthSession | null> | null = null;

export const identityService: PhoneOtpAuthService & {
  bootstrapSession(): Promise<AuthSession | null>;
  getAuthConfig(): Promise<AuthConfigResponse>;
  getManagerContact(challengeId: string): Promise<ManagerContactResponse>;
  logout(): Promise<void>;
} = {
  async requestLoginOtp(phone, idempotencyKey) {
    const deviceId = await getClientDeviceId();
    const response = unwrap(await requestOtpApiV1AuthOtpRequestPost({
      client: createSessionApiClient(),
      body: {
        client_device_id: deviceId,
        phone_e164: phoneE164(phone),
        purpose: "login",
      },
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
    return {
      challengeId: response.challenge_id,
      phone: response.phone_e164,
      resendAfterSeconds: secondsUntil(response.resend_available_at),
      expiresAtIso: response.expires_at,
      requestIdempotencyKey: idempotencyKey,
      verifyIdempotencyKey: createIdempotencyKey(),
    };
  },

  async requestReauthOtp(idempotencyKey) {
    const deviceId = await getClientDeviceId();
    const response = unwrap(await requestOtpApiV1AuthOtpRequestPost({
      client: createSessionApiClient(),
      body: {
        client_device_id: deviceId,
        purpose: "reauth",
      },
      headers: idempotencyHeaders(idempotencyKey),
      throwOnError: true,
    }));
    return {
      challengeId: response.challenge_id,
      phone: response.phone_e164,
      resendAfterSeconds: secondsUntil(response.resend_available_at),
      expiresAtIso: response.expires_at,
      requestIdempotencyKey: idempotencyKey,
      verifyIdempotencyKey: createIdempotencyKey(),
    };
  },

  async verifyOtp(challenge, otpCode, purpose): Promise<OtpVerificationResult> {
    const deviceId = await getClientDeviceId();
    const tokens = unwrap(await verifyOtpApiV1AuthOtpVerifyPost({
      client: createSessionApiClient(),
      body: {
        app_version: APP_VERSION,
        challenge_id: challenge.challengeId,
        client_device_id: deviceId,
        code: otpCode.replace(/\s/g, ""),
        platform: platform(),
        purpose,
      },
      headers: idempotencyHeaders(challenge.verifyIdempotencyKey),
      throwOnError: true,
    }));
    const profile = await resolveProfile(tokens.access_token);
    const session = sessionFrom(tokens, profile, deviceId);
    await writeSession(session);
    return { session };
  },

  async bootstrapSession() {
    bootstrapFlight ??= refreshStoredSession().finally(() => {
      bootstrapFlight = null;
    });
    return bootstrapFlight;
  },

  async getAuthConfig() {
    return unwrap(await getAuthConfigApiV1AuthConfigGet({
      client: createSessionApiClient(),
      throwOnError: true,
    }));
  },

  async getManagerContact(challengeId) {
    return unwrap(await getManagerContactApiV1AuthManagerContactGet({
      client: createSessionApiClient(),
      query: { challenge_id: challengeId },
      throwOnError: true,
    }));
  },

  async logout() {
    const session = readSessionSync();
    try {
      if (session) {
        await logoutApiV1AuthLogoutPost({
          client: createSessionApiClient(),
          body: { refresh_token: session.refreshToken },
          headers: idempotencyHeaders(session.logoutIdempotencyKey),
          throwOnError: true,
        });
      }
    } catch {
      return;
    } finally {
      await forceLocalLogout();
    }
  },
};

registerUnauthorizedHandler(async (error) => {
  if (error.code === "account_deactivated") {
    await forceLocalLogout();
    if (typeof window !== "undefined") {
      window.location.replace("/auth/deactivated");
    }
    return false;
  }
  if (error.code !== "session_expired" && error.code !== "refresh_invalid") {
    return false;
  }
  try {
    return Boolean(await refreshStoredSession());
  } catch (refreshError) {
    if (refreshError instanceof ApiClientError && refreshError.status === 0) {
      throw refreshError;
    }
    await forceLocalLogout();
    return false;
  }
});

export async function discardSession() {
  await forceLocalLogout();
}

export async function enterDeactivatedAccount(challengeId?: string) {
  await forceLocalLogout();
  if (challengeId) {
    rememberDeactivatedChallenge(challengeId);
  }
}

let reauthRequestFlight: Promise<OtpChallenge> | null = null;

export async function beginReauthentication() {
  reauthRequestFlight ??= (async () => {
    const requestIdempotencyKey = createIdempotencyKey();
    const challenge = await identityService.requestReauthOtp(
      requestIdempotencyKey,
    );
    writePendingLogin({ challenge, purpose: "reauth" });
    await markSessionForReauth();
    return challenge;
  })().finally(() => {
    reauthRequestFlight = null;
  });
  return reauthRequestFlight;
}

export function isDeactivatedError(error: unknown) {
  return error instanceof ApiClientError && error.code === "account_deactivated";
}

export type { OtpChallenge };
