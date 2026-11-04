/** Modelo exclusivo do modo demonstração. Não representa schemas da API ainda não publicados. */
export type ItemStatus = "pendente" | "concluido" | "cancelado";
export type SyncStatus = "nao_conectado" | "pendente" | "sincronizado" | "falhou";

export interface Appointment {
  id: string;
  title: string;
  date: string;
  time: string;
  endTime: string;
  description: string;
  location: string;
  status: ItemStatus;
  syncStatus: SyncStatus;
}

export interface Task {
  id: string;
  title: string;
  date: string;
  time: string;
  priority: "baixa" | "media" | "alta";
  status: ItemStatus;
  syncGoogle: boolean;
  completedAt: string | null;
}

export type Recurrence =
  | { kind: "daily" }
  | { kind: "weekly"; weekdays: number[] }
  | { kind: "interval"; every: number; unit: "days" | "weeks" }
  | { kind: "monthly_last" };

export interface Routine {
  id: string;
  title: string;
  startDate: string;
  time: string;
  recurrence: Recurrence;
  results: Record<string, "realizada" | "nao_realizada">;
}

export interface DemoState {
  appointments: Appointment[];
  tasks: Task[];
  routines: Routine[];
  timezone: string;
  morningSummary: string;
  eveningReview: string;
  quietStart: string;
  quietEnd: string;
}
