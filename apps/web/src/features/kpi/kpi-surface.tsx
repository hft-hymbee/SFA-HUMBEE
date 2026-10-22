"use client";

import { EmptyState, ErrorState, Skeleton } from "humbee-design-system";
import styles from "./home-dashboard.module.css";

export function KpiQueryFallback({
  isPending,
  isError,
  onRetry,
  empty,
}: {
  isPending: boolean;
  isError: boolean;
  onRetry: () => void;
  empty?: boolean;
}) {
  if (isPending) {
    return (
      <div className={styles.dashboardBody}>
        <Skeleton height={28} radius={8} />
        <Skeleton height={168} radius={12} />
        <Skeleton height={120} radius={12} />
        <Skeleton height={120} radius={12} />
      </div>
    );
  }
  if (isError) {
    return (
      <div className={styles.dashboardBody}>
        <div className={styles.card}>
          <ErrorState
            title="KPI data unavailable"
            message="Live KPI data could not be loaded."
            onRetry={onRetry}
          />
        </div>
      </div>
    );
  }
  if (empty) {
    return (
      <div className={styles.dashboardBody}>
        <div className={styles.card}>
          <EmptyState
            icon="Dashboard"
            title="No KPI rows yet"
            message="No live KPI cards were returned for this surface."
          />
        </div>
      </div>
    );
  }
  return null;
}
