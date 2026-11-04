import { describe, expect, it } from "vitest";
import { occursOn, shiftDate } from "./dates";
import { validateAppointment, validateRoutine, validateTask } from "./validation";

describe("validação dos formulários de demonstração", () => {
  it("aceita compromisso sem fim e rejeita fim anterior ao início", () => {
    expect(validateAppointment("Consulta", "2026-11-03", "14:00", "")).toBe("");
    expect(validateAppointment("Consulta", "2026-11-03", "14:00", "13:00")).toContain("posterior");
  });
  it("permite tarefa sem data e horário, mas não horário isolado", () => {
    expect(validateTask("Comprar pão", "", "")).toBe("");
    expect(validateTask("Comprar pão", "", "09:00")).toContain("data");
  });
  it("exige dias semanais e intervalo positivo", () => {
    expect(validateRoutine("Estudar", "2026-11-03", { kind: "weekly", weekdays: [] })).toContain(
      "dia",
    );
    expect(
      validateRoutine("Estudar", "2026-11-03", { kind: "interval", every: 0, unit: "days" }),
    ).toContain("intervalo");
  });
});

describe("ocorrências da demonstração", () => {
  it("não conclui ocorrência pela passagem do tempo", () => {
    expect(occursOn({ kind: "daily" }, "2026-11-01", "2026-11-03")).toBe(true);
    expect(occursOn({ kind: "daily" }, "2026-11-04", "2026-11-03")).toBe(false);
  });
  it("reconhece último dia do mês e ano bissexto", () => {
    expect(occursOn({ kind: "monthly_last" }, "2024-01-01", "2024-02-29")).toBe(true);
    expect(occursOn({ kind: "monthly_last" }, "2024-01-01", "2024-02-28")).toBe(false);
    expect(shiftDate("2024-02-28", 1)).toBe("2024-02-29");
  });
});
