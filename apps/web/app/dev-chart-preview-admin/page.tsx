// TEMPORARY dev-only route to visually verify the amCharts5 KPI chart
// migration without a live backend/auth session. Delete this file (and this
// directory) before the change is considered done.
import { ManagementRoleProvider } from "@/src/features/management/role-context";
import { AdminKpiHomeDashboardScreen } from "@/src/features/kpi/home-dashboard";

export default function DevChartPreviewAdminPage() {
  return (
    <ManagementRoleProvider routeRole="admin">
      <AdminKpiHomeDashboardScreen />
    </ManagementRoleProvider>
  );
}
