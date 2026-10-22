export type AttendanceMonthTone = "empty" | "leave" | "left" | "no_punch" | "present";

export type AttendanceMonthCell = {
  day: number | null;
  isToday: boolean;
  tone: AttendanceMonthTone;
};

export type AttendanceMonthModel = {
  cells: AttendanceMonthCell[];
  elapsed: number;
  isCurrentMonth: boolean;
  leave: number;
  left: number;
  noPunch: number;
  present: number;
};

function pad2(value: number) {
  return String(value).padStart(2, "0");
}

function isoDay(year: number, month: number, day: number) {
  return `${year}-${pad2(month)}-${pad2(day)}`;
}

function istWeekday(isoDate: string) {
  return new Date(`${isoDate}T12:00:00+05:30`).getUTCDay();
}

function recordedTone(status: string | undefined): Exclude<AttendanceMonthTone, "empty" | "left"> | null {
  const value = status?.toLowerCase();
  if (value === "present" || value === "late") return "present";
  if (value === "leave") return "leave";
  if (value === "absent") return "no_punch";
  return null;
}

export function shiftMonthKey(monthKey: string, offset: number) {
  const [year, month] = monthKey.split("-").map(Number);
  if (year == null || month == null) return monthKey;
  const next = new Date(Date.UTC(year, month - 1 + offset, 1));
  return `${next.getUTCFullYear()}-${pad2(next.getUTCMonth() + 1)}`;
}

export function buildAttendanceMonthModel(
  monthKey: string,
  days: Array<{ business_date: string; status: string }>,
  businessDate: string,
): AttendanceMonthModel {
  const [year, month] = monthKey.split("-").map(Number);
  const empty: AttendanceMonthModel = {
    cells: [],
    elapsed: 0,
    isCurrentMonth: Boolean(businessDate) && businessDate.startsWith(monthKey),
    leave: 0,
    left: 0,
    noPunch: 0,
    present: 0,
  };
  if (!year || !month) return empty;

  const daysInMonth = new Date(year, month, 0).getDate();
  const firstWeekday = istWeekday(isoDay(year, month, 1));
  const leading = firstWeekday;
  const records = new Map(days.map((day) => [day.business_date, day.status]));
  const cells: AttendanceMonthCell[] = Array.from({ length: leading }, () => ({
    day: null,
    isToday: false,
    tone: "empty",
  }));

  let elapsed = 0;
  let leave = 0;
  let left = 0;
  let noPunch = 0;
  let present = 0;

  for (let day = 1; day <= daysInMonth; day += 1) {
    const iso = isoDay(year, month, day);

    const isToday = iso === businessDate;
    const recorded = recordedTone(records.get(iso));
    let tone: AttendanceMonthTone;

    if (iso > businessDate) {
      tone = "left";
      left += 1;
    } else if (recorded === "present") {
      tone = "present";
      present += 1;
      elapsed += 1;
    } else if (recorded === "leave") {
      tone = "leave";
      leave += 1;
      elapsed += 1;
    } else if (isToday) {
      tone = "left";
      left += 1;
    } else {
      tone = "no_punch";
      noPunch += 1;
      elapsed += 1;
    }

    cells.push({ day, isToday, tone });
  }

  return {
    cells,
    elapsed,
    isCurrentMonth: empty.isCurrentMonth,
    leave,
    left,
    noPunch,
    present,
  };
}
