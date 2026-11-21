import { formatBpPct, isBpFilled } from "@/src/shared/business-profiler";
import styles from "./business-profiler.module.css";

/** One outlet's BP %: green when filled, amber below the threshold. */
export function BpBadge({ pct }: { pct: number }) {
  const filled = isBpFilled(pct);
  return (
    <span className={`${styles.badge} ${filled ? styles.filled : styles.notFilled}`} title={filled ? "Business profiler filled" : "Business profiler not filled"}>
      <span className={styles.dot} aria-hidden="true" />
      BP {formatBpPct(pct)}
    </span>
  );
}

/** Visited outlets split by BP status. */
export function BpCounts({ filled, notFilled, align = "start" }: { filled: number; notFilled: number; align?: "start" | "center" }) {
  return (
    <p className={`${styles.counts}${align === "center" ? ` ${styles.center}` : ""}`}>
      <span className={styles.countsLabel}>Business profiler</span>
      <span className={styles.countsItem}>
        <span className={`${styles.dot} ${styles.filled}`} aria-hidden="true" />
        <strong>{filled}</strong> filled
      </span>
      <span className={styles.countsItem}>
        <span className={`${styles.dot} ${styles.notFilled}`} aria-hidden="true" />
        <strong>{notFilled}</strong> not filled
      </span>
    </p>
  );
}
