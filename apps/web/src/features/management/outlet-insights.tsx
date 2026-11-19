"use client";

import { EmptyState } from "humbee-design-system";
import { useRouter, useSearchParams } from "next/navigation";
import { OutletInsightsScreen, type OutletInsightsFrameProps } from "@/src/features/outlets/insights-screen";
import { ManagementScreen } from "./ui";
import styles from "./management.module.css";

function ManagementInsightsFrame({ title, toolbar, children }: OutletInsightsFrameProps) {
  return (
    <ManagementScreen view="outlet-insights" title={title}>
      <div className={styles.insightsToolbar}>{toolbar}</div>
      {children}
    </ManagementScreen>
  );
}

export function ManagementOutletInsights() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const outletId = searchParams.get("outletId") ?? "";
  const name = searchParams.get("name") ?? "";
  if (!outletId) {
    return (
      <ManagementScreen view="outlet-insights">
        <div className={styles.content}>
          <EmptyState
            icon="LocationPin"
            title="Outlet unavailable"
            message="Open outlet insights from a visit in someone's day timeline."
            actionLabel="Back to coverage"
            onAction={() => router.push("/mgmt/coverage")}
          />
        </div>
      </ManagementScreen>
    );
  }
  return <OutletInsightsScreen outletId={outletId} outletName={name} Frame={ManagementInsightsFrame} />;
}
