"use client";

import { ErrorState, Skeleton } from "humbee-design-system";
import { useMemo } from "react";
import type { AttendanceHistoryDay } from "@humbee/api-contract";
import { buildAttendanceMonthModel, type AttendanceMonthTone } from "./month-grid";
import styles from "./month-card.module.css";
import { istBusinessDate, useAttendanceHistory } from "./service";

const WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"] as const;

const TONE_CLASS: Record<Exclude<AttendanceMonthTone, "empty">, string> = {
  leave: styles.leave ?? "",
  left: styles.left ?? "",
  no_punch: styles.noPunch ?? "",
  present: styles.present ?? "",
};

const LEGEND = [
  { className: styles.present, key: "present", label: "Present" },
  { className: styles.leave, key: "leave", label: "Leave" },
  { className: styles.noPunch, key: "noPunch", label: "No punch" },
  { className: `${styles.swatch} ${styles.swatchLeft}`, key: "left", label: "Left" },
] as const;

function toneLabel(tone: AttendanceMonthTone) {
  if (tone === "present") return "Present";
  if (tone === "leave") return "Leave";
  if (tone === "no_punch") return "No punch";
  if (tone === "left") return "Left";
  return "";
}

export function AttendanceMonthCard({
  days,
  isError,
  isPending,
  monthKey,
  onRetry,
  onSelectDay,
  selectedDay,
}: {
  days: AttendanceHistoryDay[];
  isError?: boolean;
  isPending?: boolean;
  monthKey: string;
  onRetry?: () => void;
  onSelectDay?: (day: number) => void;
  selectedDay?: number;
}) {
  const model = useMemo(
    () => buildAttendanceMonthModel(monthKey, days, istBusinessDate()),
    [days, monthKey],
  );
  const counts = {
    leave: model.leave,
    left: model.left,
    noPunch: model.noPunch,
    present: model.present,
  };

  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <h3 className={styles.title}>Attendance</h3>
        <span className={styles.meta}>{model.present} / {model.elapsed} days</span>
      </div>
      {isPending ? (
        <Skeleton height={180} radius={8} />
      ) : isError ? (
        <ErrorState title="Attendance unavailable" message="Month-to-date attendance could not be loaded." onRetry={onRetry} />
      ) : (
        <>
          <div className={styles.dow}>
            {WEEKDAYS.map((day, index) => <span key={`${day}-${index}`}>{day}</span>)}
          </div>
          <div className={styles.grid}>
            {model.cells.map((cell, index) => {
              const day = cell.day;
              if (day === null) return <span className={styles.placeholder} key={`empty-${index}`} />;
              const className = [
                styles.cell,
                cell.tone === "empty" ? "" : TONE_CLASS[cell.tone],
                cell.isToday ? styles.today : "",
                selectedDay === day ? styles.selected : "",
              ].filter(Boolean).join(" ");
              const status = toneLabel(cell.tone);
              const label = `${day}${status ? `, ${status}` : ""}${cell.isToday ? ", today" : ""}`;
              if (!onSelectDay) {
                return <span className={className} key={day}>{day}</span>;
              }
              return (
                <button
                  aria-label={label}
                  className={className}
                  key={day}
                  type="button"
                  onClick={() => onSelectDay(day)}
                >
                  {day}
                </button>
              );
            })}
          </div>
          <div className={styles.legend}>
            {LEGEND.map((item) => (
              <span className={styles.legendItem} key={item.key}>
                <span className={item.key === "left" ? item.className : `${styles.swatch} ${item.className}`} />
                {item.label} <b>{counts[item.key]}</b>
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function SalespersonAttendanceSection() {
  const monthKey = istBusinessDate().slice(0, 7);
  const history = useAttendanceHistory(monthKey);
  return (
    <AttendanceMonthCard
      days={history.data?.days ?? []}
      isError={history.isError}
      isPending={history.isPending}
      monthKey={monthKey}
      onRetry={() => { void history.refetch(); }}
    />
  );
}
