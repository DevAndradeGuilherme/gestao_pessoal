import type { Recurrence } from "./types";

export function validateAppointment(title: string, date: string, time: string, endTime: string): string {
  if (!title.trim() || !date || !time) return "Informe título, data e horário.";
  if (endTime && endTime <= time) return "O fim deve ser posterior ao início no mesmo dia.";
  return "";
}

export function validateTask(title: string, date: string, time: string): string {
  if (!title.trim()) return "Informe o título da tarefa.";
  if (time && !date) return "Escolha uma data para usar um horário.";
  return "";
}

export function validateRoutine(title: string, startDate: string, recurrence: Recurrence): string {
  if (!title.trim() || !startDate) return "Informe título e data inicial.";
  if (recurrence.kind === "weekly" && !recurrence.weekdays.length) return "Escolha pelo menos um dia da semana.";
  if (recurrence.kind === "interval" && (!Number.isInteger(recurrence.every) || recurrence.every < 1)) return "O intervalo deve ser um número inteiro maior que zero.";
  return "";
}
