import type { ReactNode } from "react";
import { ManagementRoleProvider } from "@/src/features/management/role-context";
import { RouteTransition } from "@/src/shared/navigation";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <ManagementRoleProvider routeRole="admin">
      <RouteTransition>{children}</RouteTransition>
    </ManagementRoleProvider>
  );
}
