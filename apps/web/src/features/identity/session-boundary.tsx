"use client";

import { SkeletonRow } from "humbee-design-system";
import { usePathname, useRouter } from "next/navigation";
import {
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import {
  getServerSession,
  homeForRole,
  readSessionSync,
  subscribeToSession,
} from "@/src/shared/auth/session";
import type { UserRole } from "@/src/shared/auth";
import {
  discardSession,
  enterDeactivatedAccount,
  identityService,
  isDeactivatedError,
} from "./service";
import { ReauthOverlay } from "./screens";

function requiredRole(pathname: string): UserRole | "management" | null {
  if (pathname === "/sp" || pathname.startsWith("/sp/")) return "sp";
  if (pathname === "/manager" || pathname.startsWith("/manager/")) return "manager";
  if (pathname === "/admin" || pathname.startsWith("/admin/")) return "admin";
  if (pathname === "/mgmt" || pathname.startsWith("/mgmt/")) return "management";
  return null;
}

function BootstrapState() {
  return (
    <main aria-label="Restoring session" style={{ padding: "var(--space-md)" }}>
      <SkeletonRow />
      <SkeletonRow />
      <SkeletonRow />
    </main>
  );
}

export function SessionBoundary({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useSyncExternalStore(
    subscribeToSession,
    readSessionSync,
    getServerSession,
  );
  const [bootstrapped, setBootstrapped] = useState(false);

  useEffect(() => {
    let active = true;
    const stored = readSessionSync();
    if (!stored) {
      void Promise.resolve().then(() => {
        if (active) setBootstrapped(true);
      });
      return () => {
        active = false;
      };
    }

    void identityService.bootstrapSession()
      .catch(async (error) => {
        if (isDeactivatedError(error)) {
          await enterDeactivatedAccount();
          if (active) router.replace("/auth/deactivated");
          return;
        }
        await discardSession();
        if (active) router.replace("/auth");
      })
      .finally(() => {
        if (active) setBootstrapped(true);
      });

    return () => {
      active = false;
    };
  }, [router]);

  const expectedRole = requiredRole(pathname);
  const isReauthRoute = pathname === "/auth/reauth";
  const isAuthRoute = !isReauthRoute
    && (pathname === "/auth" || pathname.startsWith("/auth/"));
  const roleMismatch = Boolean(
    session
      && expectedRole
      && expectedRole !== "management"
      && session.role !== expectedRole,
  );
  const managementMismatch = Boolean(
    session
      && expectedRole === "management"
      && session.role === "sp",
  );

  useEffect(() => {
    if (!bootstrapped) return;
    if (expectedRole && !session) {
      router.replace("/auth");
      return;
    }
    if (isReauthRoute && !session) {
      router.replace("/auth");
      return;
    }
    if (session && (roleMismatch || managementMismatch || isAuthRoute)) {
      router.replace(homeForRole(session.role));
    }
  }, [
    bootstrapped,
    expectedRole,
    isAuthRoute,
    isReauthRoute,
    managementMismatch,
    roleMismatch,
    router,
    session,
  ]);

  if (!bootstrapped) return <BootstrapState />;
  if ((expectedRole || isReauthRoute) && (!session || roleMismatch || managementMismatch)) return null;
  if (session && isAuthRoute) return null;

  return (
    <>
      <div inert={session?.status === "reauth_required" ? true : undefined}>
        {children}
      </div>
      {session?.status === "reauth_required" ? <ReauthOverlay /> : null}
    </>
  );
}
