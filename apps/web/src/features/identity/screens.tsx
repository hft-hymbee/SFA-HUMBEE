"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BottomSheet,
  Button,
  Icon,
  OTPInput,
  TextField,
  TopAppBar,
} from "humbee-design-system";
import humbeeLogo from "humbee-design-system/assets/humbee_go_logo.svg";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import {
  clearDeactivatedChallenge,
  clearPendingLogin,
  getServerDeactivatedChallenge,
  getServerPendingLogin,
  homeForRole,
  readDeactivatedChallenge,
  readPendingLogin,
  subscribeToDeactivatedChallenge,
  subscribeToPendingLogin,
  writePendingLogin,
} from "@/src/shared/auth/session";
import { ApiClientError, createIdempotencyKey } from "@/src/shared/api";
import { useConnectivity } from "@/src/shared/capabilities";
import { mutationErrorMessage, useAppMutation } from "@/src/shared/state";
import { SpCard } from "@/src/features/shell/components";
import { SpInlineSkeleton } from "@/src/features/shell/loading";
import {
  beginReauthentication,
  enterDeactivatedAccount,
  identityService,
  isDeactivatedError,
} from "./service";

function errorMessage(error: unknown) {
  if (error instanceof ApiClientError) {
    if (error.code === "invalid_code") {
      const details = typeof error.details === "object" && error.details
        ? error.details as { attempts_remaining?: unknown }
        : null;
      const remaining = typeof details?.attempts_remaining === "number"
        ? details.attempts_remaining
        : null;
      return remaining === null
        ? "That code is invalid. Try again."
        : `That code is invalid. ${remaining} ${remaining === 1 ? "attempt" : "attempts"} remaining.`;
    }
    if (error.code === "challenge_expired") return "This code has expired. Request a new code.";
    if (error.code === "otp_rate_limited") return "Too many attempts. Wait before trying again.";
    if (error.code === "phone_not_registered") return "This number is not registered.";
    if (error.code === "account_deactivated") return "This account has been deactivated.";
    if (error.code === "network_unavailable" || error.code === "offline_write_blocked") {
      return "Connect to the internet and try again.";
    }
  }
  return mutationErrorMessage(error);
}

function useAuthConfig() {
  return useQuery({
    queryKey: ["identity", "auth-config"],
    queryFn: () => identityService.getAuthConfig(),
    staleTime: 5 * 60 * 1000,
  });
}

export function SplashScreen() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    void identityService.bootstrapSession()
      .then((session) => {
        if (active) router.replace(session ? homeForRole(session.role) : "/auth");
      })
      .catch(async (bootstrapError) => {
        if (isDeactivatedError(bootstrapError)) {
          await enterDeactivatedAccount();
          if (active) router.replace("/auth/deactivated");
          return;
        }
        if (active) setError(errorMessage(bootstrapError));
      });
    return () => {
      active = false;
    };
  }, [attempt, router]);

  return (
    <section className="sp-screen sp-login-screen sp-splash">
      <Image className="sp-splash-logo" src={humbeeLogo} alt="Humbee GO" priority />
      <p>Sales Force Automation</p>
      {error ? (
        <p className="sp-meta sp-splash-version">{error}</p>
      ) : (
        <div className="sp-stack" style={{ width: "min(16rem, 100%)" }}>
          <SpInlineSkeleton width="36%" height={14} />
          <SpInlineSkeleton width="68%" height={12} />
        </div>
      )}
      {error ? (
        <Button
          variant="outlined"
          color="primary"
          label="Retry"
          onClick={() => {
            setError(null);
            setAttempt((value) => value + 1);
          }}
        />
      ) : null}
    </section>
  );
}

export function LoginScreen() {
  const router = useRouter();
  const { writesEnabled } = useConnectivity();
  const [phone, setPhone] = useState("");
  const [requestKey, setRequestKey] = useState(createIdempotencyKey);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    clearDeactivatedChallenge();
  }, []);
  const digits = phone.replace(/\D/g, "");
  const valid = digits.length === 10;
  const requestOtp = useAppMutation({
    mutationFn: ({ value, idempotencyKey }: { value: string; idempotencyKey: string }) =>
      identityService.requestLoginOtp(value, idempotencyKey),
    onError: async (requestError) => {
      if (isDeactivatedError(requestError) && requestError instanceof ApiClientError) {
        const details = requestError.details as { challenge_id?: unknown } | undefined;
        const challengeId = typeof details?.challenge_id === "string"
          ? details.challenge_id
          : undefined;
        await enterDeactivatedAccount(challengeId);
        router.replace("/auth/deactivated");
        return;
      }
      setError(errorMessage(requestError));
    },
    onSuccess: (challenge, variables) => {
      writePendingLogin({ challenge, phone: variables.value, purpose: "login" });
      router.push("/auth/otp");
    },
  });

  const sendOtp = () => {
    if (!valid || requestOtp.isPending || !writesEnabled) return;
    setError(null);
    requestOtp.mutate({ value: phone, idempotencyKey: requestKey });
  };

  return (
    <section
      className="sp-screen sp-login-screen sp-login-screen--combined"
      style={{ backgroundImage: 'url("/brand/humbee-honeycomb.svg")' }}
    >
      <div className="sp-scroll">
        <div className="sp-login-brand">
          <Image className="sp-login-logo" src={humbeeLogo} alt="Humbee GO" priority />
        </div>
        <div className="sp-login-body">
          <div>
            <h1 className="sp-login-title">Log in</h1>
            <p className="sp-copy" style={{ margin: "var(--space-xs) 0 0" }}>
              Sign in to start your day
            </p>
          </div>
          {error ? (
            <div className="sp-login-error">
              <Icon name="Warning" size={20} color="var(--color-error)" />
              <span>{error}</span>
            </div>
          ) : null}
          <TextField
            label="Mobile number"
            placeholder="98765 43210"
            startAdornment={<strong className="sp-body-strong">+91</strong>}
            value={phone}
            error={Boolean(error)}
            inputProps={{ inputMode: 'numeric', maxLength: 10, pattern: '[0-9]*' }}
            onChange={(event) => {
              setError(null);
              setRequestKey(createIdempotencyKey());
              const value = (event.target as HTMLInputElement).value.replace(/\D/g, '').slice(0, 10);
              setPhone(value);
            }}
          />
          <Button
            variant="filled"
            color="primary"
            label={writesEnabled ? "Send OTP" : "Connect to send OTP"}
            disabled={!valid || requestOtp.isPending || !writesEnabled}
            onClick={sendOtp}
            style={{ width: "100%" }}
          />
        </div>
        <p className="sp-meta sp-login-footer" style={{ textAlign: "center" }}>
          Number not working? Contact your manager
        </p>
      </div>
    </section>
  );
}

export function OtpScreen() {
  const router = useRouter();
  const { writesEnabled } = useConnectivity();
  const config = useAuthConfig();
  const pending = useSyncExternalStore(
    subscribeToPendingLogin,
    readPendingLogin,
    getServerPendingLogin,
  );
  const [otp, setOtp] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [secs, setSecs] = useState(pending?.challenge.resendAfterSeconds ?? 0);
  const [verifying, setVerifying] = useState(false);
  const otpLength = config.data?.otp_length ?? 0;

  useEffect(() => {
    if (secs <= 0) return;
    const timer = window.setTimeout(() => setSecs((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [secs]);

  const resend = async () => {
    if (!pending || !writesEnabled) {
      if (!pending) router.replace("/auth");
      return;
    }
    try {
      const requestKey = createIdempotencyKey();
      const challenge = pending.purpose === "login"
        ? await identityService.requestLoginOtp(pending.phone ?? "", requestKey)
        : await identityService.requestReauthOtp(requestKey);
      writePendingLogin({ ...pending, challenge });
      setSecs(challenge.resendAfterSeconds);
      setMessage(null);
    } catch (requestError) {
      setMessage(errorMessage(requestError));
    }
  };

  const verify = async () => {
    if (!pending || !writesEnabled) {
      if (!pending) router.replace("/auth");
      return;
    }
    setVerifying(true);
    setMessage(null);
    try {
      const result = await identityService.verifyOtp(
        pending.challenge,
        otp,
        pending.purpose,
      );
      clearPendingLogin();
      router.replace(homeForRole(result.session.role));
    } catch (verifyError) {
      if (isDeactivatedError(verifyError)) {
        await enterDeactivatedAccount(pending.challenge.challengeId);
        router.replace("/auth/deactivated");
        return;
      }
      setMessage(errorMessage(verifyError));
    } finally {
      setVerifying(false);
    }
  };

  if (!pending) {
    return (
      <section className="sp-screen">
        <TopAppBar title="Verify OTP" onBack={() => router.replace("/auth")} />
        <div className="sp-content">Your login attempt expired. Return to login.</div>
      </section>
    );
  }

  return (
    <section className="sp-screen">
      <TopAppBar title="Verify OTP" onBack={() => router.push("/auth")} />
      <div className="sp-content sp-scroll" style={{ gap: "var(--space-lg)" }}>
        <div>
          <h2 className="app-title app-title--h2" style={{ margin: 0 }}>
            Enter the code
          </h2>
          <p className="sp-copy" style={{ margin: "var(--space-xs) 0 0" }}>
            We sent a code to <strong>{pending.challenge.phone}</strong>
          </p>
        </div>
        <OTPInput
          length={otpLength || 6}
          value={otp}
          error={Boolean(message)}
          onChange={(value) => {
            setMessage(null);
            setOtp(value);
          }}
        />
        {message ? <span className="sp-login-error-text">{message}</span> : null}
        <p className="sp-copy">
          {secs > 0 ? (
            <>Resend code in <strong>{secs}s</strong></>
          ) : (
            <button
              className="sp-text-link"
              disabled={!writesEnabled}
              type="button"
              onClick={() => { void resend(); }}
            >
              Resend code
            </button>
          )}
        </p>
        <div style={{ marginTop: "auto" }}>
          <Button
            variant="filled"
            color="primary"
            label={writesEnabled ? "Verify & continue" : "Connect to verify"}
            disabled={!otpLength || otp.replace(/\s/g, "").length !== otpLength || verifying || !writesEnabled}
            onClick={() => { void verify(); }}
            style={{ width: "100%" }}
          />
        </div>
      </div>
    </section>
  );
}

export function AccountDeactivatedScreen() {
  const router = useRouter();
  const challengeId = useSyncExternalStore(
    subscribeToDeactivatedChallenge,
    readDeactivatedChallenge,
    getServerDeactivatedChallenge,
  );

  const contact = useQuery({
    queryKey: ["identity", "manager-contact", challengeId],
    queryFn: () => identityService.getManagerContact(challengeId!),
    enabled: Boolean(challengeId),
    retry: false,
  });
  const phone = contact.data?.manager_phone_e164 ?? null;

  const goToLogin = () => {
    clearDeactivatedChallenge();
    router.push("/auth");
  };

  return (
    <section className="sp-screen">
      <TopAppBar title="Sign in" onBack={goToLogin} />
      <div
        className="sp-content sp-scroll"
        style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}
      >
        <span className="sp-deactivated-icon">
          <Icon name="Lock" size={40} color="var(--color-error)" />
        </span>
        <h2
          className="sp-title sp-title--h2"
          style={{ margin: "var(--space-xs) 0 0" }}
        >
          Account deactivated
        </h2>
        <p className="sp-copy" style={{ maxWidth: 280 }}>
          Your login has been disabled by your administrator. Contact your manager to restore access.
        </p>
      </div>
      <div className="sp-sticky-footer">
        <div className="sp-stack">
          {phone ? (
            <Button
              variant="filled"
              color="primary"
              label="Call my manager"
              leftIcon={<Icon name="Call" size={20} color="currentColor" />}
              onClick={() => {
                window.location.assign(`tel:${phone}`);
              }}
              style={{ width: "100%" }}
            />
          ) : null}
          <Button
            variant="text"
            color="neutral"
            label="Back to login"
            onClick={goToLogin}
            style={{ width: "100%" }}
          />
        </div>
      </div>
    </section>
  );
}

export function ReauthOverlay() {
  const pathname = usePathname();
  const router = useRouter();
  const { writesEnabled } = useConnectivity();
  const config = useAuthConfig();
  const pending = useSyncExternalStore(
    subscribeToPendingLogin,
    readPendingLogin,
    getServerPendingLogin,
  );
  const [otp, setOtp] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const otpLength = config.data?.otp_length ?? 0;

  const verify = async () => {
    if (!pending || pending.purpose !== "reauth" || !writesEnabled) return;
    setVerifying(true);
    setMessage(null);
    try {
      const result = await identityService.verifyOtp(
        pending.challenge,
        otp,
        "reauth",
      );
      clearPendingLogin();
      if (pathname === "/auth/reauth") {
        router.replace(homeForRole(result.session.role));
      }
    } catch (verifyError) {
      if (isDeactivatedError(verifyError)) {
        await enterDeactivatedAccount(pending.challenge.challengeId);
        router.replace("/auth/deactivated");
        return;
      }
      setMessage(errorMessage(verifyError));
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="sp-reauth-scrim">
      <SpCard style={{ width: "100%", maxWidth: 330, borderRadius: 16 }}>
        <div className="sp-stack">
          <h2 className="sp-title sp-title--h2" style={{ margin: 0 }}>
            Session verification required
          </h2>
          <p className="sp-copy">
            Enter the code sent to <strong>{pending?.challenge.phone ?? "your registered number"}</strong>.
          </p>
          <OTPInput
            length={otpLength || 6}
            value={otp}
            error={Boolean(message)}
            onChange={(value) => {
              setMessage(null);
              setOtp(value);
            }}
          />
          {message ? <span className="sp-login-error-text">{message}</span> : null}
          <Button
            variant="filled"
            color="primary"
            label={writesEnabled ? "Verify & continue" : "Connect to verify"}
            disabled={!pending || !otpLength || otp.length !== otpLength || verifying || !writesEnabled}
            onClick={() => { void verify(); }}
            style={{ width: "100%" }}
          />
          <p className="sp-meta" style={{ textAlign: "center" }}>
            You&apos;ll return to where you left off.
          </p>
        </div>
      </SpCard>
    </div>
  );
}

export function ReauthScreen() {
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    void beginReauthentication().catch((requestError) => {
      setError(errorMessage(requestError));
    });
  }, []);
  return error ? <div className="sp-login-error">{error}</div> : null;
}

export function LogoutConfirmSheet({
  open = true,
  onClose,
}: {
  open?: boolean;
  onClose?: () => void;
}) {
  const router = useRouter();
  const { writesEnabled } = useConnectivity();
  const [loggingOut, setLoggingOut] = useState(false);
  const close = onClose ?? (() => router.back());
  const logout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    await identityService.logout();
    router.replace("/auth");
  };

  return (
    <BottomSheet open={open} title="Log out?" onClose={close}>
      <div className="sp-stack">
        <Button
          variant="filled"
          color="error"
          label={writesEnabled ? "Log out" : "Clear local session"}
          disabled={loggingOut}
          onClick={() => { void logout(); }}
          style={{ width: "100%" }}
        />
        <Button
          variant="outlined"
          color="neutral"
          label="Cancel"
          onClick={close}
          style={{ width: "100%" }}
        />
      </div>
    </BottomSheet>
  );
}
