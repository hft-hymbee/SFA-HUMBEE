"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import {
  SpBottomNavigation,
  SpMobileFrame,
} from "@/src/features/shell/components";

export interface RoleNavItem {
  href: string;
  label: string;
  active?: boolean;
}

interface RoleHeader {
  title: string;
  subtitle: string;
}

interface AuthShellProps {
  header: RoleHeader;
  children: ReactNode;
}

export function AuthShell({ header, children }: AuthShellProps) {
  return (
    <div className="auth-shell">
      <header className="shell-header">
        <h1>{header.title}</h1>
        <p>{header.subtitle}</p>
      </header>
      <main>{children}</main>
    </div>
  );
}

interface SalesPersonShellProps {
  children: ReactNode;
}

export function SalesPersonShell({
  children,
}: SalesPersonShellProps) {
  return (
    <SpMobileFrame>
      <main className="sp-main">{children}</main>
      <SpBottomNavigation />
    </SpMobileFrame>
  );
}

interface ManagementShellProps {
  header: RoleHeader;
  navItems: RoleNavItem[];
  children: ReactNode;
}

export function ManagementShell({
  header,
  navItems,
  children,
}: ManagementShellProps) {
  const pathname = usePathname();

  return (
    <div className="mgmt-shell role-shell">
      <header className="shell-header">
        <div className="mgmt-header-copy">
          <h1>{header.title}</h1>
          <p>{header.subtitle}</p>
        </div>
      </header>
      <nav aria-label="Management primary navigation" className="mgmt-nav">
        {navItems.map((item) => {
          const active = item.href === "/mgmt"
            ? pathname === item.href
            : pathname.startsWith(item.href);
          return (
          <Link
            key={item.href}
            className="mgmt-nav-link"
            data-active={active || item.active}
            href={item.href}
          >
            {item.label}
          </Link>
          );
        })}
      </nav>
      <main className="mgmt-content">{children}</main>
    </div>
  );
}
