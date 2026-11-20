const LOCALE = "en-IN";

export function leadInitials(name: string): string {
  const words = name
    .split(/\s+/)
    .map((w) => Array.from(w.replace(/[^\p{L}\p{N}]/gu, "")))
    .filter((chars) => chars.length > 0);
  const [first, second] = words;
  if (!first) return "";
  const letters = second ? `${first[0]}${second[0]}` : first.slice(0, 2).join("");
  return letters.toUpperCase();
}

function dayStart(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

export function leadShortDate(iso: string, today: Date): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const diffDays = Math.round((dayStart(today) - dayStart(date)) / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return date.toLocaleDateString(LOCALE, { day: "numeric", month: "short" });
}

export function leadDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const day = date.toLocaleDateString(LOCALE, { day: "numeric", month: "short", year: "numeric" });
  const time = date.toLocaleTimeString(LOCALE, { hour: "numeric", minute: "2-digit", hour12: true });
  return `${day}, ${time}`;
}

export function leadTurnover(cr: number | null): string | null {
  if (cr === null || cr === undefined) return null;
  return `₹ ${cr.toFixed(2)} cr`;
}

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  manager: "Manager",
  sales_person: "Sales Person",
};

/** Human label for an employee `role_code`; unknown codes pass through. */
export function leadRoleLabel(roleCode: string | null | undefined): string {
  if (!roleCode) return "";
  return ROLE_LABELS[roleCode] ?? roleCode;
}
