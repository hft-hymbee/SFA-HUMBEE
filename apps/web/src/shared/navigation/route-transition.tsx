"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";

const SP_TAB_ROOTS = new Set(["/sp", "/sp/beats", "/sp/route", "/sp/orders", "/sp/more"]);
const MANAGEMENT_TAB_ROOTS = new Set([
  "/mgmt",
  "/mgmt/team",
  "/mgmt/org-tree",
  "/mgmt/approvals",
  "/mgmt/coverage",
  "/mgmt/more",
  "/manager",
  "/manager/team",
  "/manager/approvals",
  "/manager/coverage",
  "/manager/more",
  "/admin",
  "/admin/org-tree",
  "/admin/approvals",
  "/admin/coverage",
  "/admin/more",
]);

const PAGE_OPENING_SEARCH_PARAMS = ["id", "orderId", "beatId", "stopId", "visitId", "employeeId", "schedule"];

function isTabRoot(pathname: string) {
  return SP_TAB_ROOTS.has(pathname) || MANAGEMENT_TAB_ROOTS.has(pathname);
}

function pathDepth(pathname: string) {
  return pathname.split("/").filter(Boolean).length;
}

function routeKeyFor(pathname: string, searchParams: Pick<URLSearchParams, "get">) {
  const pageOpeningParams = PAGE_OPENING_SEARCH_PARAMS
    .map((name) => {
      const value = searchParams.get(name);
      return value ? `${name}=${encodeURIComponent(value)}` : null;
    })
    .filter(Boolean);
  return pageOpeningParams.length ? `${pathname}?${pageOpeningParams.join("&")}` : pathname;
}

function routeDepth(pathname: string, routeKey: string) {
  const queryDepth = routeKey.includes("?") ? routeKey.split("&").length : 0;
  return pathDepth(pathname) + queryDepth;
}

function motionFor(fromPathname: string | null, fromRouteKey: string | null, toPathname: string, toRouteKey: string) {
  if (!fromPathname || !fromRouteKey || fromRouteKey === toRouteKey) return "tab";
  if (isTabRoot(fromPathname) && isTabRoot(toPathname)) return "tab";
  if (isTabRoot(toPathname) && !isTabRoot(fromPathname)) return "back";
  if (!isTabRoot(toPathname) && isTabRoot(fromPathname)) return "forward";
  if (routeDepth(toPathname, toRouteKey) < routeDepth(fromPathname, fromRouteKey)) return "back";
  return "forward";
}

export function RouteTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const routeKey = routeKeyFor(pathname, searchParams);
  const [transition, setTransition] = useState({
    pathname,
    routeKey,
    motion: "tab",
  });
  if (transition.routeKey !== routeKey) {
    setTransition({
      pathname,
      routeKey,
      motion: motionFor(transition.pathname, transition.routeKey, pathname, routeKey),
    });
  }
  const isBeatCreation = pathname.startsWith("/sp/beats/create/");

  return (
    <div
      className="route-transition"
      data-flow={isBeatCreation ? "beat-creation" : undefined}
      data-motion={transition.motion}
      key={routeKey}
    >
      {children}
    </div>
  );
}
