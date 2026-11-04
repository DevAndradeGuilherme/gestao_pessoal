// Adaptadores HTTP tipados dos recursos de domínio (espelham `docs/openapi.json`, `/api/v1`).
// Toda chamada passa por `authenticatedApiFetch`; erros chegam como `ApiError`.
// O `user_id` vem somente do JWT: nenhum payload o envia.

import { authenticatedApiFetch } from "../auth";
import type { Page } from "./types";

export type SyncStatus = "not_applicable" | "pending" | "synced" | "failed";

export interface Appointment {
  id: string;
  user_id: string;
  title: string;
  starts_at: string;
  ends_at: string | null;
  description: string | null;
  location: string | null;
  status: "scheduled" | "cancelled";
  google_event_id: string | null;
  google_calendar_id: string | null;
  sync_status: SyncStatus;
  created_at: string;
  updated_at: string;
}
export interface AppointmentCreate {
  title: string;
  starts_at: string;
  ends_at?: string | null;
  description?: string | null;
  location?: string | null;
}
export interface AppointmentUpdate {
  title?: string;
  description?: string | null;
  location?: string | null;
}

export type TaskStatus = "pending" | "completed" | "cancelled";
export type TaskPriority = "low" | "medium" | "high";
export interface Task {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  due_at: string | null;
  priority: TaskPriority | null;
  category: string | null;
  status: TaskStatus;
  completed_at: string | null;
  sync_to_calendar: boolean;
  google_event_id: string | null;
  created_at: string;
  updated_at: string;
}
export interface TaskCreate {
  title: string;
  description?: string | null;
  due_at?: string | null;
  priority?: TaskPriority | null;
  category?: string | null;
  sync_to_calendar?: boolean;
}
export type TaskUpdate = Partial<TaskCreate>;

export type Weekday = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";
export interface RecurrenceRule {
  frequency: "daily" | "weekly" | "monthly";
  interval: number;
  by_weekday: Weekday[] | null;
  by_month_day: number[] | null;
  time: string;
  timezone: string;
  start_date: string;
  end_date: string | null;
  count: number | null;
}
export type RecurrenceRuleInput = Partial<RecurrenceRule> &
  Pick<RecurrenceRule, "frequency" | "time" | "timezone" | "start_date">;
export interface Routine {
  id: string;
  user_id: string;
  title: string;
  recurrence_rule: RecurrenceRule;
  active: boolean;
  created_at: string;
  updated_at: string;
}
export type OccurrenceStatus = "pending" | "completed" | "skipped";
export interface Occurrence {
  id: string;
  routine_id: string;
  user_id: string;
  scheduled_for: string;
  status: OccurrenceStatus;
  completed_at: string | null;
}
export interface OccurrenceGeneration {
  created: number;
  occurrences: Occurrence[];
}

const MAX_LIMIT = 200;

/** Chave de idempotência por tentativa lógica: o formulário reutiliza a mesma em reenvios. */
export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

function write<T>(
  method: "POST" | "PATCH",
  path: string,
  body?: unknown,
  idempotencyKey: string = newIdempotencyKey(),
): Promise<T> {
  return authenticatedApiFetch<T>(path, {
    method,
    headers: { "Idempotency-Key": idempotencyKey },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export type Mutation = { idempotencyKey?: string };

// -- compromissos ---------------------------------------------------------------------------
export const appointments = {
  list: (range: { from?: string; to?: string; status?: "scheduled" | "cancelled" } = {}) =>
    authenticatedApiFetch<Page<Appointment>>(
      `/api/v1/appointments${qs({ starts_at_from: range.from, starts_at_to: range.to, status: range.status, limit: MAX_LIMIT })}`,
    ),
  create: (data: AppointmentCreate, m: Mutation = {}) =>
    write<Appointment>("POST", "/api/v1/appointments", data, m.idempotencyKey),
  update: (id: string, data: AppointmentUpdate, m: Mutation = {}) =>
    write<Appointment>("PATCH", `/api/v1/appointments/${id}`, data, m.idempotencyKey),
  reschedule: (
    id: string,
    data: { starts_at: string; ends_at?: string | null },
    m: Mutation = {},
  ) => write<Appointment>("POST", `/api/v1/appointments/${id}/reschedule`, data, m.idempotencyKey),
  cancel: (id: string, reason?: string, m: Mutation = {}) =>
    write<Appointment>(
      "POST",
      `/api/v1/appointments/${id}/cancel`,
      reason ? { reason } : undefined,
      m.idempotencyKey,
    ),
};

// -- tarefas --------------------------------------------------------------------------------
export const tasks = {
  list: (filter: { status?: TaskStatus; priority?: TaskPriority } = {}) =>
    authenticatedApiFetch<Page<Task>>(
      `/api/v1/tasks${qs({ status: filter.status, priority: filter.priority, limit: MAX_LIMIT })}`,
    ),
  create: (data: TaskCreate, m: Mutation = {}) =>
    write<Task>("POST", "/api/v1/tasks", data, m.idempotencyKey),
  update: (id: string, data: TaskUpdate, m: Mutation = {}) =>
    write<Task>("PATCH", `/api/v1/tasks/${id}`, data, m.idempotencyKey),
  complete: (id: string, m: Mutation = {}) =>
    write<Task>("POST", `/api/v1/tasks/${id}/complete`, {}, m.idempotencyKey),
  reopen: (id: string, m: Mutation = {}) =>
    write<Task>("POST", `/api/v1/tasks/${id}/reopen`, undefined, m.idempotencyKey),
  cancel: (id: string, m: Mutation = {}) =>
    write<Task>("POST", `/api/v1/tasks/${id}/cancel`, undefined, m.idempotencyKey),
};

// -- rotinas e ocorrências ------------------------------------------------------------------
export const routines = {
  list: () => authenticatedApiFetch<Page<Routine>>(`/api/v1/routines${qs({ limit: MAX_LIMIT })}`),
  create: (data: { title: string; recurrence_rule: RecurrenceRuleInput }, m: Mutation = {}) =>
    write<Routine>("POST", "/api/v1/routines", data, m.idempotencyKey),
  update: (
    id: string,
    data: { title?: string; recurrence_rule?: RecurrenceRuleInput },
    m: Mutation = {},
  ) => write<Routine>("PATCH", `/api/v1/routines/${id}`, data, m.idempotencyKey),
  deactivate: (id: string, m: Mutation = {}) =>
    write<Routine>("POST", `/api/v1/routines/${id}/deactivate`, undefined, m.idempotencyKey),
  activate: (id: string, m: Mutation = {}) =>
    write<Routine>("POST", `/api/v1/routines/${id}/activate`, undefined, m.idempotencyKey),
  /** Materializa as ocorrências da janela `[from, to)` (idempotente) e devolve todas. */
  generate: (id: string, window: { from: string; to: string }) =>
    authenticatedApiFetch<OccurrenceGeneration>(`/api/v1/routines/${id}/occurrences/generate`, {
      method: "POST",
      body: JSON.stringify({ window_start: window.from, window_end: window.to }),
    }),
  occurrences: (id: string, range: { from?: string; to?: string } = {}) =>
    authenticatedApiFetch<Page<Occurrence>>(
      `/api/v1/routines/${id}/occurrences${qs({ scheduled_for_from: range.from, scheduled_for_to: range.to, limit: MAX_LIMIT })}`,
    ),
  complete: (routineId: string, occurrenceId: string, m: Mutation = {}) =>
    write<Occurrence>(
      "POST",
      `/api/v1/routines/${routineId}/occurrences/${occurrenceId}/complete`,
      {},
      m.idempotencyKey,
    ),
  skip: (routineId: string, occurrenceId: string, m: Mutation = {}) =>
    write<Occurrence>(
      "POST",
      `/api/v1/routines/${routineId}/occurrences/${occurrenceId}/skip`,
      undefined,
      m.idempotencyKey,
    ),
  reopen: (routineId: string, occurrenceId: string, m: Mutation = {}) =>
    write<Occurrence>(
      "POST",
      `/api/v1/routines/${routineId}/occurrences/${occurrenceId}/reopen`,
      undefined,
      m.idempotencyKey,
    ),
};

export function describeError(error: unknown): string {
  if (error && typeof error === "object" && "body" in error && "status" in error) {
    const { status, body } = error as { status: number; body: { code: string; message: string } };
    if (body.code === "unauthenticated") return "Sua sessão expirou. Entre novamente.";
    if (body.code === "service_unavailable")
      return "O serviço de dados está indisponível. Nada foi alterado; tente novamente em instantes.";
    if (body.code === "validation_error")
      return "Alguns dados são inválidos. Confira o formulário.";
    if (status >= 500 || body.code === "internal_error")
      return "Erro inesperado no servidor. Tente novamente.";
    return body.message;
  }
  if (error instanceof TypeError) return "Não foi possível conectar à API. Verifique sua conexão.";
  if (error instanceof Error) return error.message;
  return "Erro desconhecido.";
}
