import type { DemoState } from "./types";

const KEY = "gp05-demo-v1";

export function newDemoState(): DemoState {
  return {
    appointments: [],
    tasks: [],
    routines: [],
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Sao_Paulo",
    morningSummary: "07:00",
    eveningReview: "23:00",
    quietStart: "00:00",
    quietEnd: "07:00",
  };
}

export function readDemoState(): DemoState {
  if (typeof window === "undefined") return newDemoState();
  try {
    const stored = localStorage.getItem(KEY);
    if (!stored) return newDemoState();
    const parsed: unknown = JSON.parse(stored);
    if (!parsed || typeof parsed !== "object") return newDemoState();
    const value = parsed as Partial<DemoState>;
    if (!Array.isArray(value.appointments) || !Array.isArray(value.tasks) || !Array.isArray(value.routines)) {
      return newDemoState();
    }
    return { ...newDemoState(), ...value };
  } catch {
    return newDemoState();
  }
}

export function writeDemoState(state: DemoState): void {
  localStorage.setItem(KEY, JSON.stringify(state));
}
