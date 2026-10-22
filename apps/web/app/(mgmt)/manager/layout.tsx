import type { ReactNode } from "react";
import { ManagementRoleProvider } from "@/src/features/management/role-context";
import { RouteTransition } from "@/src/shared/navigation";

export default function ManagerLayout({ children }: { children: ReactNode }) {
  return (
    <ManagementRoleProvider routeRole="manager">
      <RouteTransition>{children}</RouteTransition>
    </ManagementRoleProvider>
  );
}
