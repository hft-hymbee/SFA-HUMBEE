import type { ReactNode } from "react";
import { ManagementRoleProvider } from "@/src/features/management/role-context";
import { RouteTransition } from "@/src/shared/navigation";

export default function ManagementLayout({ children }: { children: ReactNode }) {
  return (
    <ManagementRoleProvider>
      <RouteTransition>{children}</RouteTransition>
    </ManagementRoleProvider>
  );
}
