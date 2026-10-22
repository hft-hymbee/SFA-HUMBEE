"use client";

import type { LeaveRequestItem } from "@humbee/api-contract";
import { BottomSheet, Button, EmptyState, Icon, StatusChip } from "humbee-design-system";
import { useMemo, useState } from "react";
import { SpCard, SpStatusRow } from "@/src/features/shell/components";
import { balanceLabel, dayLabel, leaveChipStatus, leaveDateRange, leaveStatusLabel } from "./format";
import { leaveTypeMeta } from "./service";

const CALENDAR_STATUSES = new Set(["pending", "approved", "approved_with_edits", "auto_approved"]);
const WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"];

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function isoDate(year: number, month: number, day: number) {
  return `${year}-${pad(month)}-${pad(day)}`;
}

function shiftMonth(year: number, month: number, delta: number) {
  const date = new Date(Date.UTC(year, month - 1 + delta, 1));
  return { year: date.getUTCFullYear(), month: date.getUTCMonth() + 1 };
}

function nextIso(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(Date.UTC(year ?? 0, (month ?? 1) - 1, (day ?? 1) + 1));
  return isoDate(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
}

function todayParts() {
  const parts = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Kolkata",
    year: "numeric",
  }).formatToParts(new Date());
  const value = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((part) => part.type === type)?.value ?? "0");
  return { day: value("day"), month: value("month"), year: value("year") };
}

function isWeekend(iso: string) {
  const weekday = new Date(`${iso}T00:00:00Z`).getUTCDay();
  return weekday === 0 || weekday === 6;
}

type CalendarCell = {
  day: number;
  inMonth: boolean;
  iso: string;
};

function monthWeeks(year: number, month: number): CalendarCell[][] {
  const mondayOffset = (new Date(Date.UTC(year, month - 1, 1)).getUTCDay() + 6) % 7;
  const days = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const prev = shiftMonth(year, month, -1);
  const prevDays = new Date(Date.UTC(prev.year, prev.month, 0)).getUTCDate();
  const next = shiftMonth(year, month, 1);
  const cells: CalendarCell[] = [];

  for (let offset = mondayOffset - 1; offset >= 0; offset -= 1) {
    const day = prevDays - offset;
    cells.push({ day, inMonth: false, iso: isoDate(prev.year, prev.month, day) });
  }
  for (let day = 1; day <= days; day += 1) {
    cells.push({ day, inMonth: true, iso: isoDate(year, month, day) });
  }
  let nextDay = 1;
  while (cells.length % 7 !== 0) {
    cells.push({ day: nextDay, inMonth: false, iso: isoDate(next.year, next.month, nextDay) });
    nextDay += 1;
  }

  const weeks: CalendarCell[][] = [];
  for (let index = 0; index < cells.length; index += 7) weeks.push(cells.slice(index, index + 7));
  return weeks;
}

function leaveByDate(items: LeaveRequestItem[]) {
  const map = new Map<string, LeaveRequestItem>();
  for (const item of items) {
    if (!CALENDAR_STATUSES.has(item.status)) continue;
    for (let date = item.from_date; date <= item.to_date; date = nextIso(date)) {
      if (!map.has(date)) map.set(date, item);
    }
  }
  return map;
}

export function LeaveCalendar({
  items,
  onOpenRequest,
  onReachOldest,
}: {
  items: LeaveRequestItem[];
  onOpenRequest: (item: LeaveRequestItem) => void;
  onReachOldest?: () => void;
}) {
  const today = todayParts();
  const todayIso = isoDate(today.year, today.month, today.day);
  const [cursor, setCursor] = useState({ month: today.month, year: today.year });
  const [selected, setSelected] = useState<LeaveRequestItem | null>(null);
  const weeks = useMemo(() => monthWeeks(cursor.year, cursor.month), [cursor.month, cursor.year]);
  const dates = useMemo(() => leaveByDate(items), [items]);
  const oldestLoaded = useMemo(
    () => items.reduce<string | null>((oldest, item) => !oldest || item.from_date < oldest ? item.from_date : oldest, null),
    [items],
  );
  const monthName = new Intl.DateTimeFormat("en-IN", { month: "long", timeZone: "UTC" })
    .format(new Date(Date.UTC(cursor.year, cursor.month - 1, 1)));
  const selectedMeta = selected ? leaveTypeMeta(selected.leave_type) : null;
  const isCurrentMonth = cursor.month === today.month && cursor.year === today.year;
  const hasVisibleLeave = weeks.some((week) => week.some((cell) => cell.inMonth && dates.has(cell.iso)));
  // Rows arrive newest-first, so an older page is only worth fetching once the reader actually
  // walks back past what is loaded — never eagerly over the whole history.
  const showOlderMonth = () => {
    const next = shiftMonth(cursor.year, cursor.month, -1);
    setCursor(next);
    if (oldestLoaded && isoDate(next.year, next.month, 1) <= oldestLoaded) onReachOldest?.();
  };

  if (!items.length) {
    return (
      <EmptyState
        icon="Calendar"
        title="No leave yet"
        message="Apply for leave and it will show up on this calendar."
      />
    );
  }

  return (
    <>
      <SpCard padded={false}>
        <div className="sp-leave-cal">
          <div className="sp-leave-cal__nav">
            <div className="sp-leave-cal__heading">
              <h2 className="sp-leave-cal__title">{monthName}</h2>
              <p className="sp-leave-cal__year">{cursor.year}</p>
            </div>
            <div className="sp-leave-cal__nav-actions">
              <button
                aria-label="Previous month"
                className="sp-leave-cal__nav-btn"
                onClick={showOlderMonth}
                type="button"
              >
                <Icon color="currentColor" name="KeyboardArrowLeft" size={20} />
              </button>
              <button
                aria-label="Show this month"
                className="sp-leave-cal__today"
                disabled={isCurrentMonth}
                onClick={() => setCursor({ month: today.month, year: today.year })}
                type="button"
              >
                Today
              </button>
              <button
                aria-label="Next month"
                className="sp-leave-cal__nav-btn"
                onClick={() => setCursor((current) => shiftMonth(current.year, current.month, 1))}
                type="button"
              >
                <Icon color="currentColor" name="KeyboardArrowRight" size={20} />
              </button>
            </div>
          </div>

          <div className="sp-leave-cal__weekdays">
            {WEEKDAYS.map((day, index) => (
              <span key={`${day}-${index}`}>{day}</span>
            ))}
          </div>

          <div className="sp-leave-cal__month">
            {weeks.map((week) => (
              <div className="sp-leave-cal__week" key={week[0]?.iso}>
                {week.map((cell) => {
                  const leave = dates.get(cell.iso);
                  const weekend = isWeekend(cell.iso);
                  if (!leave) {
                    return (
                      <span
                        className="sp-leave-cal__day"
                        data-in-month={cell.inMonth}
                        data-today={cell.iso === todayIso}
                        data-weekend={weekend}
                        key={cell.iso}
                      >
                        <span className="sp-leave-cal__num">{cell.day}</span>
                      </span>
                    );
                  }
                  const meta = leaveTypeMeta(leave.leave_type);
                  return (
                    <button
                      aria-label={`${meta.label}, ${leaveDateRange(leave.from_date, leave.to_date)}, ${leaveStatusLabel(leave.status)}`}
                      className="sp-leave-cal__day"
                      data-in-month={cell.inMonth}
                      data-on-leave="true"
                      data-pending={leave.status === "pending"}
                      data-today={cell.iso === todayIso}
                      data-type={leave.leave_type}
                      data-weekend={weekend}
                      key={cell.iso}
                      onClick={() => setSelected(leave)}
                      type="button"
                    >
                      <span className="sp-leave-cal__num">{cell.day}</span>
                      <span className="sp-leave-cal__mark">{meta.abbr}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
          {!hasVisibleLeave ? (
            <p className="sp-meta">No leave in this month.</p>
          ) : null}
        </div>
      </SpCard>

      <BottomSheet
        onClose={() => setSelected(null)}
        open={Boolean(selected)}
        title={selectedMeta ? selectedMeta.label : "Leave"}
      >
        {selected && selectedMeta ? (
          <div className="sp-stack">
            <div className="sp-leave-cal__sheet-head">
              <div>
                <p className="sp-title">{leaveDateRange(selected.from_date, selected.to_date)}</p>
                <p className="sp-meta">{dayLabel(selected.day_count)}</p>
              </div>
              <StatusChip label={leaveStatusLabel(selected.status)} status={leaveChipStatus(selected.status)} type="filled" />
            </div>
            <SpStatusRow label="Leave type" value={selectedMeta.label} />
            <SpStatusRow label="Duration" value={dayLabel(selected.day_count)} />
            <SpStatusRow label="Applied" value={new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(selected.applied_at))} />
            {selected.reason ? <SpStatusRow label="Reason" value={selected.reason} /> : null}
            {selected.decision_note ? <SpStatusRow label="Manager note" value={selected.decision_note} /> : null}
            <SpStatusRow label="Balance after" value={balanceLabel(selected.balance_after_projected)} />
            <Button
              color="primary"
              label="Open request"
              onClick={() => onOpenRequest(selected)}
              style={{ width: "100%" }}
              variant="filled"
            />
          </div>
        ) : null}
      </BottomSheet>
    </>
  );
}
