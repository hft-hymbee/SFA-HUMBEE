"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import { useRouter as useNextRouter } from "next/navigation";
import {
  getServerSession,
  homeForRole,
  readSessionSync,
  subscribeToSession,
} from "@/src/shared/auth/session";
import type { ManagementRole } from "./service";

interface ManagementRoleValue {
  role: ManagementRole;
  isAdmin: boolean;
  basePath: `/${ManagementRole}`;
}

const ManagementRoleContext = createContext<ManagementRoleValue | null>(null);

export function ManagementRoleProvider({
  children,
  routeRole,
}: {
  children: ReactNode;
  routeRole?: ManagementRole;
}) {
  const router = useNextRouter();
  const session = useSyncExternalStore(subscribeToSession, readSessionSync, getServerSession);
  const sessionRole = session?.role === "admin" ? "admin" : "manager";
  const role = routeRole ?? sessionRole;
  const routeMismatch = !!routeRole && !!session && session.role !== routeRole;

  const value = useMemo<ManagementRoleValue>(() => ({
    role,
    isAdmin: role === "admin",
    basePath: `/${role}`,
  }), [role]);

  useEffect(() => {
    if (routeMismatch && session) {
      router.replace(homeForRole(session.role));
    }
  }, [routeMismatch, router, session]);

  if (routeMismatch) return null;

  return <ManagementRoleContext.Provider value={value}>{children}</ManagementRoleContext.Provider>;
}

export function useManagementRole() {
  const value = useContext(ManagementRoleContext);
  if (!value) throw new Error("useManagementRole must be used inside ManagementRoleProvider");
  return value;
}

export function managementPath(href: string, role: ManagementRole) {
  if (href === "/mgmt") return `/${role}`;
  if (href.startsWith("/mgmt/")) return `/${role}${href.slice(5)}`;
  return href;
}

export function useManagementPath() {
  const { role } = useManagementRole();
  return useCallback((href: string) => managementPath(href, role), [role]);
}

export function useManagementRouter() {
  const router = useNextRouter();
  const toRolePath = useManagementPath();

  return useMemo(() => ({
    back: router.back,
    forward: router.forward,
    refresh: router.refresh,
    prefetch: router.prefetch,
    push: (href: string, options?: Parameters<typeof router.push>[1]) => router.push(toRolePath(href), options),
    replace: (href: string, options?: Parameters<typeof router.replace>[1]) => router.replace(toRolePath(href), options),
  }), [router, toRolePath]);
}
