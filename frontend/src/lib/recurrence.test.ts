import { describe, expect, it } from "vitest";
import type { RecurrenceRule } from "./api/domain";
import { describeRule, formToRule, ruleToForm, validateRecurrence } from "./recurrence";

const base = { startDate: "2030-01-07", time: "19:00", timezone: "America/Sao_Paulo" };

describe("recorrência", () => {
  it("monta regras da API a partir do formulário", () => {
    expect(formToRule({ kind: "daily" }, base)).toMatchObject({ frequency: "daily", interval: 1 });
    expect(formToRule({ kind: "weekly", weekdays: [3, 1] }, base)).toMatchObject({
      frequency: "weekly",
      by_weekday: ["mon", "wed"],
    });
    expect(formToRule({ kind: "interval", every: 3, unit: "days" }, base)).toMatchObject({
      frequency: "daily",
      interval: 3,
    });
    // 2030-01-07 é segunda-feira.
    expect(formToRule({ kind: "interval", every: 2, unit: "weeks" }, base)).toMatchObject({
      frequency: "weekly",
      interval: 2,
      by_weekday: ["mon"],
    });
    expect(formToRule({ kind: "monthly_last" }, base)).toMatchObject({
      frequency: "monthly",
      by_month_day: [-1],
    });
  });

  it("faz o caminho inverso e sinaliza regras não representáveis", () => {
    const rule = formToRule({ kind: "weekly", weekdays: [1, 5] }, base) as RecurrenceRule;
    expect(ruleToForm(rule)).toEqual({ kind: "weekly", weekdays: [1, 5] });
    expect(describeRule({ ...rule, time: "19:00:00" })).toBe("Semanal · Seg, Sex · 19:00");
    const custom: RecurrenceRule = {
      ...rule,
      frequency: "monthly",
      by_weekday: null,
      by_month_day: [1, 15],
    };
    expect(ruleToForm(custom)).toBeNull();
  });

  it("valida dias e intervalo", () => {
    expect(validateRecurrence({ kind: "weekly", weekdays: [] })).toContain("dia da semana");
    expect(validateRecurrence({ kind: "interval", every: 0, unit: "days" })).toContain("maior");
    expect(validateRecurrence({ kind: "daily" })).toBe("");
  });
});
