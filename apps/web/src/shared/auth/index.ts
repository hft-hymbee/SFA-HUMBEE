import type { KeyValueStore } from "@/src/shared/capabilities";

export type UserRole = "sp" | "manager" | "admin";
export type SessionStatus = "active" | "reauth_required";

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  deviceId: string;
  employeeId: string;
  displayName: string;
  role: UserRole;
  expiresAtIso: string;
  status: SessionStatus;
  refreshIdempotencyKey: string;
  logoutIdempotencyKey: string;
}

export interface OtpChallenge {
  challengeId: string;
  phone: string;
  resendAfterSeconds: number;
  expiresAtIso: string;
  requestIdempotencyKey: string;
  verifyIdempotencyKey: string;
}

export interface OtpVerificationResult {
  session: AuthSession;
}

export interface PhoneOtpAuthService {
  requestLoginOtp(phone: string, idempotencyKey: string): Promise<OtpChallenge>;
  requestReauthOtp(idempotencyKey: string): Promise<OtpChallenge>;
  verifyOtp(
    challenge: OtpChallenge,
    otpCode: string,
    purpose: "login" | "reauth",
  ): Promise<OtpVerificationResult>;
}

export const SESSION_KEY = "humbee.sfa.session";

export class SessionStore {
  private readonly key = SESSION_KEY;
  private readonly storage: KeyValueStore;

  constructor(storage: KeyValueStore) {
    this.storage = storage;
  }

  async read(): Promise<AuthSession | null> {
    const rawValue = await this.storage.getItem(this.key);
    if (!rawValue) {
      return null;
    }

    try {
      return JSON.parse(rawValue) as AuthSession;
    } catch {
      await this.storage.removeItem(this.key);
      return null;
    }
  }

  async write(session: AuthSession): Promise<void> {
    await this.storage.setItem(this.key, JSON.stringify(session));
  }

  async clear(): Promise<void> {
    await this.storage.removeItem(this.key);
  }
}
