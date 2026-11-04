// Tradução entre o formulário de rotinas e `RecurrenceRule` da API (ADR-003).

import type { RecurrenceRule, RecurrenceRuleInput, Weekday } from "./api/domain";

export type RecurrenceForm =
  | { kind: "daily" }
  | { kind: "weekly"; weekdays: number[] } // 0 = domingo … 6 = sábado
  | { kind: "interval"; every: number; unit: "days" | "weeks" }
  | { kind: "monthly_last" };

const WEEKDAYS: Weekday[] = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
export const WEEKDAY_LABELS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

function weekdayOf(date: string): number {
  return new Date(`${date}T12:00:00Z`).getUTCDay();
}

export function formToRule(
  form: RecurrenceForm,
  base: { startDate: string; time: string; timezone: string },
): RecurrenceRuleInput {
  const common = { time: base.time, timezone: base.timezone, start_date: base.startDate };
  switch (form.kind) {
    case "daily":
      return { ...common, frequency: "daily", interval: 1 };
    case "weekly":
      return {
        ...common,
        frequency: "weekly",
        interval: 1,
        by_weekday: [...form.weekdays].sort((a, b) => a - b).map((d) => WEEKDAYS[d]),
      };
    case "interval":
      return form.unit === "days"
        ? { ...common, frequency: "daily", interval: form.every }
        : {
            ...common,
            frequency: "weekly",
            interval: form.every,
            by_weekday: [WEEKDAYS[weekdayOf(base.startDate)]],
          };
    case "monthly_last":
      return { ...common, frequency: "monthly", interval: 1, by_month_day: [-1] };
  }
}

/** `null` quando a regra existe na API mas não é representável no formulário simples. */
export function ruleToForm(rule: RecurrenceRule): RecurrenceForm | null {
  if (rule.frequency === "daily") {
    return rule.interval === 1
      ? { kind: "daily" }
      : { kind: "interval", every: rule.interval, unit: "days" };
  }
  if (rule.frequency === "weekly") {
    const days = (rule.by_weekday ?? []).map((d) => WEEKDAYS.indexOf(d));
    if (rule.interval === 1) return { kind: "weekly", weekdays: days };
    return days.length === 1 ? { kind: "interval", every: rule.interval, unit: "weeks" } : null;
  }
  if (rule.interval === 1 && rule.by_month_day?.length === 1 && rule.by_month_day[0] === -1) {
    return { kind: "monthly_last" };
  }
  return null;
}

export function describeRule(rule: RecurrenceRule): string {
  const form = ruleToForm(rule);
  const time = rule.time.slice(0, 5);
  if (!form) return `Regra personalizada · ${time}`;
  const text =
    form.kind === "daily"
      ? "Todos os dias"
      : form.kind === "monthly_last"
        ? "Último dia do mês"
        : form.kind === "interval"
          ? `A cada ${form.every} ${form.unit === "days" ? "dia(s)" : "semana(s)"}`
          : `Semanal · ${form.weekdays.map((d) => WEEKDAY_LABELS[d]).join(", ")}`;
  return `${text} · ${time}`;
}

export function validateRecurrence(form: RecurrenceForm): string {
  if (form.kind === "weekly" && !form.weekdays.length)
    return "Escolha pelo menos um dia da semana.";
  if (form.kind === "interval" && (!Number.isInteger(form.every) || form.every < 1))
    return "O intervalo deve ser um número inteiro maior que zero.";
  return "";
}
