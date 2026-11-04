// Conversões entre data/hora local (formulários) e instantes ISO 8601 em UTC (API).
// A API só aceita instantes com offset e responde em UTC (`Z`); o fuso de exibição é IANA.

export function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Sao_Paulo";
}

function zoneParts(instant: number, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date(instant));
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  return {
    year: get("year"),
    month: get("month"),
    day: get("day"),
    hour: get("hour"),
    minute: get("minute"),
    second: get("second"),
  };
}

function offsetMs(instant: number, timezone: string): number {
  const p = zoneParts(instant, timezone);
  return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - instant;
}

/** Data/hora de relógio local (`YYYY-MM-DD`, `HH:MM`) no fuso → instante ISO UTC. */
export function zonedToInstant(date: string, time: string, timezone: string): string {
  const [y, mo, d] = date.split("-").map(Number);
  const [h, mi] = time.split(":").map(Number);
  const wall = Date.UTC(y, mo - 1, d, h, mi);
  let instant = wall - offsetMs(wall, timezone);
  instant = wall - offsetMs(instant, timezone);
  return new Date(instant).toISOString();
}

/** Início do dia local (00:00) como instante ISO UTC. */
export function startOfDay(date: string, timezone: string): string {
  return zonedToInstant(date, "00:00", timezone);
}

/** Instante ISO → `{ date: YYYY-MM-DD, time: HH:MM }` no fuso. */
export function instantToZoned(iso: string, timezone: string): { date: string; time: string } {
  const p = zoneParts(Date.parse(iso), timezone);
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    date: `${p.year}-${pad(p.month)}-${pad(p.day)}`,
    time: `${pad(p.hour)}:${pad(p.minute)}`,
  };
}

export function todayIn(timezone: string): string {
  return instantToZoned(new Date().toISOString(), timezone).date;
}

/** Soma dias a uma data civil `YYYY-MM-DD` (sem fuso envolvido). */
export function addDays(date: string, days: number): string {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function formatDay(
  date: string,
  options: Intl.DateTimeFormatOptions = { day: "2-digit", month: "short" },
): string {
  // Datas civis não são instantes: formatar em UTC evita mudar o dia.
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC", ...options }).format(
    new Date(`${date}T12:00:00Z`),
  );
}
