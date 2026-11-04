import type { Recurrence } from "./types";

export function localDate(date: Date, timezone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function dateLabel(date: string, _timezone: string, options: Intl.DateTimeFormatOptions = {}) {
  // Datas civis não são instantes: formatar em UTC evita mudar o dia em fusos extremos.
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC", day: "2-digit", month: "short", ...options }).format(
    new Date(`${date}T12:00:00Z`),
  );
}

export function shiftDate(date: string, days: number): string {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function occursOn(rule: Recurrence, startDate: string, date: string): boolean {
  if (date < startDate) return false;
  const day = new Date(`${date}T12:00:00Z`).getUTCDay();
  if (rule.kind === "daily") return true;
  if (rule.kind === "weekly") return rule.weekdays.includes(day);
  if (rule.kind === "monthly_last") return shiftDate(date, 1).slice(5, 7) !== date.slice(5, 7);
  const diff = Math.round((Date.parse(`${date}T12:00:00Z`) - Date.parse(`${startDate}T12:00:00Z`)) / 86400000);
  return diff % (rule.every * (rule.unit === "weeks" ? 7 : 1)) === 0;
}
