import { describe, expect, it } from "vitest";
import { addDays, instantToZoned, startOfDay, zonedToInstant } from "./time";

describe("conversões de fuso", () => {
  it("converte relógio local de São Paulo (UTC-3) para UTC e volta", () => {
    const iso = zonedToInstant("2030-01-10", "14:00", "America/Sao_Paulo");
    expect(iso).toBe("2030-01-10T17:00:00.000Z");
    expect(instantToZoned(iso, "America/Sao_Paulo")).toEqual({ date: "2030-01-10", time: "14:00" });
  });

  it("respeita offsets diferentes e virada de dia", () => {
    expect(zonedToInstant("2030-01-10", "23:30", "America/Sao_Paulo")).toBe(
      "2030-01-11T02:30:00.000Z",
    );
    expect(zonedToInstant("2030-07-01", "09:00", "Europe/Lisbon")).toBe("2030-07-01T08:00:00.000Z");
    expect(instantToZoned("2030-01-11T02:30:00.000Z", "America/Sao_Paulo").date).toBe("2030-01-10");
  });

  it("início do dia local e soma de dias civis", () => {
    expect(startOfDay("2030-01-10", "America/Sao_Paulo")).toBe("2030-01-10T03:00:00.000Z");
    expect(addDays("2030-02-28", 1)).toBe("2030-03-01");
    expect(addDays("2030-01-01", -1)).toBe("2029-12-31");
  });
});
