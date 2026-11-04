"use client";

// Telas ligadas à API FastAPI (dados reais da conta autenticada). Não usa `src/lib/demo`.

import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import { ApiError } from "@/lib/api/client";
import {
  appointments as appointmentsApi,
  describeError,
  newIdempotencyKey,
  routines as routinesApi,
  tasks as tasksApi,
  type Appointment,
  type Occurrence,
  type Routine,
  type Task,
  type TaskPriority,
} from "@/lib/api/domain";
import {
  describeRule,
  formToRule,
  ruleToForm,
  validateRecurrence,
  WEEKDAY_LABELS,
  type RecurrenceForm,
} from "@/lib/recurrence";
import {
  addDays,
  formatDay,
  instantToZoned,
  startOfDay,
  todayIn,
  zonedToInstant,
} from "@/lib/time";
import { Badge, Empty, Field, FormActions, Header, Panel, handleDialogKeys } from "./ui";

export interface LiveProps {
  timezone: string;
  notify: (message: string) => void;
  authLost: () => void;
}

// -- infraestrutura -----------------------------------------------------------------------

/** `key` identifica os parâmetros do carregamento: mudou, recarrega. */
function useLoad<T>(loader: () => Promise<T>, authLost: () => void, key = "") {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const loaderRef = useRef(loader);
  useEffect(() => {
    loaderRef.current = loader;
  });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let active = true;
    // Estado de carregamento é derivado do ciclo da requisição.
    queueMicrotask(() => active && setLoading(true));
    loaderRef
      .current()
      .then((value) => {
        if (!active) return;
        setData(value);
        setError("");
      })
      .catch((reason: unknown) => {
        if (!active) return;
        if (reason instanceof ApiError && reason.body.code === "unauthenticated") authLost();
        setError(describeError(reason));
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [tick, authLost, key]);
  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { data, error, loading, reload };
}

function LoadState({
  loading,
  error,
  hasData,
  reload,
  children,
}: {
  loading: boolean;
  error: string;
  hasData: boolean;
  reload: () => void;
  children: ReactNode;
}) {
  if (error)
    return (
      <div role="alert" className="error-box">
        {error}{" "}
        <button className="button secondary tiny" onClick={reload}>
          Tentar novamente
        </button>
      </div>
    );
  if (loading && !hasData)
    return (
      <p className="muted" role="status">
        Carregando…
      </p>
    );
  return <>{children}</>;
}

/** Executa uma mutação mostrando sucesso ou erro; devolve `true` se concluída. */
function useAction({ notify, authLost }: Pick<LiveProps, "notify" | "authLost">) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = useCallback(
    async (action: () => Promise<unknown>, success: string): Promise<boolean> => {
      setBusy(true);
      setError("");
      try {
        await action();
        notify(success);
        return true;
      } catch (reason) {
        if (reason instanceof ApiError && reason.body.code === "unauthenticated") authLost();
        setError(describeError(reason));
        return false;
      } finally {
        setBusy(false);
      }
    },
    [notify, authLost],
  );
  return { busy, error, run, clear: () => setError("") };
}

function ActionError({ message }: { message: string }) {
  return message ? (
    <p role="alert" className="error-box">
      {message}
    </p>
  ) : null;
}

function wantsNew(): boolean {
  return typeof window !== "undefined" && new URLSearchParams(window.location.search).has("novo");
}

function syncLabel(status: Appointment["sync_status"]): string {
  return status === "synced"
    ? "Sincronizado"
    : status === "failed"
      ? "Falha na sincronização"
      : status === "not_applicable"
        ? "Sem sincronização"
        : "Sincronização pendente";
}

const priorityLabel: Record<TaskPriority, string> = { low: "Baixa", medium: "Média", high: "Alta" };

// -- Hoje -----------------------------------------------------------------------------------

interface TodayData {
  appointments: Appointment[];
  tasks: Task[];
  routines: { routine: Routine; occurrence: Occurrence | null }[];
}

async function loadRoutineOccurrences(
  from: string,
  to: string,
): Promise<{ routine: Routine; occurrences: Occurrence[] }[]> {
  const list = await routinesApi.list();
  const active = list.items.filter((routine) => routine.active);
  return Promise.all(
    active.map(async (routine) => ({
      routine,
      occurrences: (await routinesApi.generate(routine.id, { from, to })).occurrences,
    })),
  );
}

export function LiveTodayView({ timezone, notify, authLost }: LiveProps) {
  const date = todayIn(timezone);
  const loader = async (): Promise<TodayData> => {
    const from = startOfDay(date, timezone);
    const to = startOfDay(addDays(date, 1), timezone);
    const [appts, taskPage, withOccurrences] = await Promise.all([
      appointmentsApi.list({ from, to, status: "scheduled" }),
      tasksApi.list(),
      loadRoutineOccurrences(from, to),
    ]);
    return {
      appointments: appts.items,
      tasks: taskPage.items,
      routines: withOccurrences.flatMap(({ routine, occurrences }) =>
        occurrences.map((occurrence) => ({ routine, occurrence })),
      ),
    };
  };
  const { data, error, loading, reload } = useLoad(loader, authLost, `${date}|${timezone}`);
  const action = useAction({ notify, authLost });

  const tasks = (data?.tasks ?? []).filter((task) => {
    if (task.status === "cancelled") return false;
    const due = task.due_at ? instantToZoned(task.due_at, timezone).date : null;
    return due === date || (!due && task.status === "pending");
  });
  const overdue = (data?.tasks ?? []).filter(
    (task) =>
      task.status === "pending" && task.due_at && instantToZoned(task.due_at, timezone).date < date,
  ).length;
  const routineRows = data?.routines ?? [];
  const completed =
    tasks.filter((task) => task.status === "completed").length +
    routineRows.filter((row) => row.occurrence?.status === "completed").length;
  const pending =
    (data?.appointments.length ?? 0) +
    tasks.filter((task) => task.status === "pending").length +
    routineRows.filter((row) => row.occurrence?.status === "pending").length;

  const upcoming = [
    ...(data?.appointments ?? []).map((item) => ({
      key: item.id,
      type: "Compromisso",
      title: item.title,
      time: instantToZoned(item.starts_at, timezone).time,
    })),
    ...tasks
      .filter((task) => task.status === "pending")
      .map((task) => ({
        key: task.id,
        type: "Tarefa",
        title: task.title,
        time: task.due_at ? instantToZoned(task.due_at, timezone).time : "Sem horário",
      })),
    ...routineRows
      .filter((row) => row.occurrence?.status === "pending")
      .map((row) => ({
        key: row.occurrence!.id,
        type: "Rotina",
        title: row.routine.title,
        time: instantToZoned(row.occurrence!.scheduled_for, timezone).time,
      })),
  ].sort((a, b) => a.time.localeCompare(b.time));

  async function toggleTask(task: Task) {
    const ok = await action.run(
      () => (task.status === "completed" ? tasksApi.reopen(task.id) : tasksApi.complete(task.id)),
      task.status === "completed" ? "Tarefa reaberta." : "Tarefa concluída.",
    );
    if (ok) reload();
  }
  async function completeOccurrence(row: { routine: Routine; occurrence: Occurrence | null }) {
    if (!row.occurrence) return;
    const ok = await action.run(
      () => routinesApi.complete(row.routine.id, row.occurrence!.id),
      "Realização registrada.",
    );
    if (ok) reload();
  }

  return (
    <>
      <Header
        eyebrow="VISÃO GERAL"
        title="Bom dia, vamos organizar hoje."
        description={new Intl.DateTimeFormat("pt-BR", {
          timeZone: timezone,
          weekday: "long",
          day: "numeric",
          month: "long",
        }).format(new Date())}
        action={
          <div className="heading-actions">
            <Link className="button secondary" href="/tarefas?novo=1">
              + Nova tarefa
            </Link>
            <Link className="button primary" href="/agenda?novo=1">
              + Compromisso
            </Link>
          </div>
        }
      />
      <ActionError message={action.error} />
      <LoadState loading={loading} error={error} hasData={data !== null} reload={reload}>
        <div className="stats">
          <div className="stat">
            <span>Concluídos</span>
            <strong>{completed}</strong>
            <small>Confirmados por você</small>
          </div>
          <div className="stat">
            <span>Pendentes</span>
            <strong>{pending}</strong>
            <small>Para acompanhar</small>
          </div>
          <div className="stat">
            <span>Atrasados</span>
            <strong>{overdue}</strong>
            <small>Tarefas com prazo vencido</small>
          </div>
        </div>
        <div className="two-column">
          <Panel
            title="Próximas atividades"
            action={
              <Link href="/agenda" className="subtle-link">
                Ver agenda →
              </Link>
            }
          >
            {upcoming.length ? (
              <div className="item-list">
                {upcoming.map((item) => (
                  <div className="activity-row" key={`${item.type}-${item.key}`}>
                    <div className="activity-time">{item.time}</div>
                    <div>
                      <strong>{item.title}</strong>
                      <small>{item.type}</small>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Empty
                title="O dia está livre"
                description="Crie um compromisso, tarefa ou rotina para começar."
              />
            )}
          </Panel>
          <Panel title="Ações rápidas">
            <div className="quick-actions">
              <Link href="/agenda?novo=1">
                ▦ <span>Marcar compromisso</span>
                <b>→</b>
              </Link>
              <Link href="/tarefas?novo=1">
                ☑ <span>Adicionar tarefa</span>
                <b>→</b>
              </Link>
              <Link href="/rotinas?novo=1">
                ↻ <span>Criar rotina</span>
                <b>→</b>
              </Link>
            </div>
          </Panel>
        </div>
        <div className="two-column">
          <Panel title="Tarefas de hoje">
            {tasks.length ? (
              <div className="item-list">
                {tasks.map((task) => (
                  <div className="task-row" key={task.id}>
                    <button
                      className={task.status === "completed" ? "check done" : "check"}
                      disabled={action.busy}
                      aria-label={
                        task.status === "completed"
                          ? `Reabrir ${task.title}`
                          : `Concluir ${task.title}`
                      }
                      onClick={() => toggleTask(task)}
                    >
                      {task.status === "completed" ? "✓" : ""}
                    </button>
                    <span className={task.status === "completed" ? "completed" : ""}>
                      {task.title}
                    </span>
                    <Badge>
                      {task.due_at ? instantToZoned(task.due_at, timezone).time : "Sem horário"}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <Empty
                title="Nenhuma tarefa hoje"
                description="Suas tarefas para hoje aparecerão aqui."
              />
            )}
          </Panel>
          <Panel title="Rotinas de hoje">
            {routineRows.length ? (
              <div className="item-list">
                {routineRows.map((row) => (
                  <div className="task-row" key={row.occurrence?.id ?? row.routine.id}>
                    <span className="routine-dot">↻</span>
                    <span>{row.routine.title}</span>
                    {row.occurrence?.status === "pending" ? (
                      <button
                        className="button tiny"
                        disabled={action.busy}
                        onClick={() => completeOccurrence(row)}
                      >
                        Marcar feita
                      </button>
                    ) : (
                      <Badge tone="green">
                        {row.occurrence?.status === "completed" ? "Realizada" : "Não realizada"}
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <Empty
                title="Nenhuma rotina hoje"
                description="As ocorrências previstas aparecerão aqui."
              />
            )}
          </Panel>
        </div>
      </LoadState>
    </>
  );
}

// -- Agenda ---------------------------------------------------------------------------------

export function LiveAgendaView({ timezone, notify, authLost }: LiveProps) {
  const [mode, setMode] = useState<"dia" | "semana" | "mes">("semana");
  const [anchor, setAnchor] = useState(() => todayIn(timezone));
  const [editing, setEditing] = useState<Appointment | "new" | null>(() =>
    wantsNew() ? "new" : null,
  );
  const start =
    mode === "dia"
      ? anchor
      : mode === "semana"
        ? addDays(anchor, -((new Date(`${anchor}T12:00:00Z`).getUTCDay() + 6) % 7))
        : `${anchor.slice(0, 7)}-01`;
  const days =
    mode === "dia"
      ? 1
      : mode === "semana"
        ? 7
        : new Date(Number(anchor.slice(0, 4)), Number(anchor.slice(5, 7)), 0).getDate();
  const dates = Array.from({ length: days }, (_, index) => addDays(start, index));
  const rangeFrom = startOfDay(start, timezone);
  const rangeTo = startOfDay(addDays(start, days), timezone);
  const loader = () => appointmentsApi.list({ from: rangeFrom, to: rangeTo, status: "scheduled" });
  const { data, error, loading, reload } = useLoad(loader, authLost, `${rangeFrom}|${rangeTo}`);
  const items = (data?.items ?? []).map((item) => ({
    item,
    ...instantToZoned(item.starts_at, timezone),
    end: item.ends_at ? instantToZoned(item.ends_at, timezone).time : "",
  }));

  function move(direction: number) {
    if (mode === "mes") {
      const month = new Date(`${anchor.slice(0, 7)}-01T12:00:00Z`);
      month.setUTCMonth(month.getUTCMonth() + direction);
      setAnchor(month.toISOString().slice(0, 10));
    } else setAnchor(addDays(anchor, direction * (mode === "dia" ? 1 : 7)));
  }
  return (
    <>
      <Header
        eyebrow="ORGANIZAÇÃO"
        title="Agenda"
        description="Seus compromissos, do jeito que o seu dia acontece."
        action={
          <button className="button primary" onClick={() => setEditing("new")}>
            + Novo compromisso
          </button>
        }
      />
      <div className="toolbar">
        <div className="segmented" role="group" aria-label="Visualização da agenda">
          {(["dia", "semana", "mes"] as const).map((value) => (
            <button
              key={value}
              className={mode === value ? "selected" : ""}
              onClick={() => setMode(value)}
            >
              {value === "mes" ? "Mês" : value === "dia" ? "Dia" : "Semana"}
            </button>
          ))}
        </div>
        <div className="date-controls">
          <button aria-label="Período anterior" onClick={() => move(-1)}>
            ‹
          </button>
          <button onClick={() => setAnchor(todayIn(timezone))}>Hoje</button>
          <button aria-label="Próximo período" onClick={() => move(1)}>
            ›
          </button>
          <strong>{formatDay(start, { month: "long", year: "numeric" })}</strong>
        </div>
      </div>
      <LoadState loading={loading} error={error} hasData={data !== null} reload={reload}>
        <Panel
          title={
            mode === "mes" ? "Visão mensal" : mode === "semana" ? "Visão semanal" : "Visão diária"
          }
        >
          <div className={mode === "mes" ? "calendar-grid month" : "calendar-grid"}>
            {dates.map((date) => (
              <button
                key={date}
                className={date === todayIn(timezone) ? "calendar-day current" : "calendar-day"}
                onClick={() => {
                  setAnchor(date);
                  setMode("dia");
                }}
              >
                <span>{formatDay(date, { weekday: "short" })}</span>
                <strong>{date.slice(-2)}</strong>
                <small>{items.filter((row) => row.date === date).length || ""}</small>
              </button>
            ))}
          </div>
        </Panel>
        <Panel title="Compromissos do período">
          {items.length ? (
            <div className="item-list">
              {items.map(({ item, date, time, end }) => (
                <div className="resource-row" key={item.id}>
                  <div className="date-tile">
                    <strong>{date.slice(-2)}</strong>
                    <small>{formatDay(date, { month: "short" })}</small>
                  </div>
                  <div className="resource-main">
                    <strong>{item.title}</strong>
                    <small>
                      {time}
                      {end ? ` – ${end}` : ""}
                      {item.location ? ` · ${item.location}` : ""}
                    </small>
                    <Badge tone="orange">{syncLabel(item.sync_status)}</Badge>
                  </div>
                  <button className="button secondary tiny" onClick={() => setEditing(item)}>
                    Editar
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <Empty
              title="Nenhum compromisso neste período"
              description="Use o botão acima para registrar um horário."
            />
          )}
        </Panel>
      </LoadState>
      {editing && (
        <LiveAppointmentForm
          timezone={timezone}
          notify={notify}
          authLost={authLost}
          item={editing}
          close={() => setEditing(null)}
          saved={reload}
        />
      )}
    </>
  );
}

function LiveAppointmentForm({
  timezone,
  notify,
  authLost,
  item,
  close,
  saved,
}: LiveProps & { item: Appointment | "new"; close: () => void; saved: () => void }) {
  const current = item === "new" ? null : item;
  const start = current ? instantToZoned(current.starts_at, timezone) : null;
  const end = current?.ends_at ? instantToZoned(current.ends_at, timezone).time : "";
  const [title, setTitle] = useState(current?.title ?? "");
  const [date, setDate] = useState(start?.date ?? todayIn(timezone));
  const [time, setTime] = useState(start?.time ?? "");
  const [endTime, setEndTime] = useState(end);
  const [location, setLocation] = useState(current?.location ?? "");
  const [description, setDescription] = useState(current?.description ?? "");
  const [problem, setProblem] = useState("");
  const action = useAction({ notify, authLost });
  // Mesma chave em reenvios do mesmo formulário: repetir o clique não duplica o compromisso.
  const [key] = useState(newIdempotencyKey);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !date || !time) return setProblem("Informe título, data e horário.");
    if (endTime && endTime <= time)
      return setProblem("O fim deve ser posterior ao início no mesmo dia.");
    setProblem("");
    const startsAt = zonedToInstant(date, time, timezone);
    const endsAt = endTime ? zonedToInstant(date, endTime, timezone) : null;
    const ok = await action.run(
      async () => {
        if (!current) {
          await appointmentsApi.create(
            {
              title: title.trim(),
              starts_at: startsAt,
              ends_at: endsAt,
              description: description.trim() || null,
              location: location.trim() || null,
            },
            { idempotencyKey: key },
          );
          return;
        }
        const textChanged =
          title.trim() !== current.title ||
          (description.trim() || null) !== current.description ||
          (location.trim() || null) !== current.location;
        const timeChanged =
          startsAt !== new Date(current.starts_at).toISOString() ||
          endsAt !== (current.ends_at ? new Date(current.ends_at).toISOString() : null);
        if (textChanged)
          await appointmentsApi.update(current.id, {
            title: title.trim(),
            description: description.trim() || null,
            location: location.trim() || null,
          });
        if (timeChanged)
          await appointmentsApi.reschedule(current.id, { starts_at: startsAt, ends_at: endsAt });
      },
      current ? "Compromisso atualizado." : "Compromisso criado.",
    );
    if (ok) {
      saved();
      close();
    }
  }
  async function cancel() {
    if (!current) return;
    const ok = await action.run(() => appointmentsApi.cancel(current.id), "Compromisso cancelado.");
    if (ok) {
      saved();
      close();
    }
  }
  return (
    <div className="modal-backdrop">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="appointment-form-title"
        onKeyDown={(event) => handleDialogKeys(event, close)}
      >
        <div className="modal-head">
          <div>
            <p className="eyebrow">AGENDA</p>
            <h2 id="appointment-form-title">
              {current ? "Editar compromisso" : "Novo compromisso"}
            </h2>
          </div>
          <button className="icon-button" onClick={close} aria-label="Fechar">
            ×
          </button>
        </div>
        <form onSubmit={submit} className="form-stack">
          <Field label="Título *">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={200}
              autoFocus
            />
          </Field>
          <div className="form-grid">
            <Field label="Data *">
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
            </Field>
            <Field label="Horário *">
              <input type="time" value={time} onChange={(e) => setTime(e.target.value)} required />
            </Field>
          </div>
          <Field label="Fim (opcional)">
            <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
          </Field>
          <Field label="Local">
            <input value={location} onChange={(e) => setLocation(e.target.value)} maxLength={500} />
          </Field>
          <Field label="Descrição">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              maxLength={5000}
            />
          </Field>
          <p className="field-hint">
            Nenhuma duração será presumida. A sincronização com o Google Agenda ainda não está
            disponível: o compromisso fica salvo e marcado como pendente.
          </p>
          <ActionError message={problem || action.error} />
          {current && (
            <button className="danger-link" type="button" disabled={action.busy} onClick={cancel}>
              Cancelar compromisso
            </button>
          )}
          <FormActions
            cancel={close}
            busy={action.busy}
            label={current ? "Salvar alterações" : "Criar compromisso"}
          />
        </form>
      </div>
    </div>
  );
}

// -- Tarefas --------------------------------------------------------------------------------

export function LiveTasksView({ timezone, notify, authLost }: LiveProps) {
  const [editing, setEditing] = useState<Task | "new" | null>(() => (wantsNew() ? "new" : null));
  const [status, setStatus] = useState("todas");
  const [priority, setPriority] = useState("todas");
  const [period, setPeriod] = useState("todas");
  const loader = () => tasksApi.list();
  const { data, error, loading, reload } = useLoad(loader, authLost);
  const action = useAction({ notify, authLost });
  const date = todayIn(timezone);

  const rows = (data?.items ?? [])
    .map((task) => ({
      task,
      due: task.due_at ? instantToZoned(task.due_at, timezone) : null,
    }))
    .filter(
      ({ task, due }) =>
        task.status !== "cancelled" &&
        (status === "todas" || task.status === status) &&
        (priority === "todas" || task.priority === priority) &&
        (period === "todas" ||
          (period === "sem_prazo"
            ? !due
            : period === "atrasadas"
              ? due !== null && due.date < date && task.status === "pending"
              : period === "hoje"
                ? due?.date === date
                : due !== null && due.date >= date && due.date < addDays(date, 7))),
    );

  async function toggle(task: Task) {
    const ok = await action.run(
      () => (task.status === "completed" ? tasksApi.reopen(task.id) : tasksApi.complete(task.id)),
      task.status === "completed" ? "Tarefa reaberta." : "Tarefa concluída.",
    );
    if (ok) reload();
  }
  return (
    <>
      <Header
        eyebrow="FOCO"
        title="Tarefas"
        description="Um passo de cada vez. Acompanhe o que precisa ser feito."
        action={
          <button className="button primary" onClick={() => setEditing("new")}>
            + Nova tarefa
          </button>
        }
      />
      <div className="filter-bar">
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="todas">Todas</option>
            <option value="pending">Pendentes</option>
            <option value="completed">Concluídas</option>
          </select>
        </label>
        <label>
          Prioridade
          <select value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="todas">Todas</option>
            <option value="high">Alta</option>
            <option value="medium">Média</option>
            <option value="low">Baixa</option>
          </select>
        </label>
        <label>
          Período
          <select value={period} onChange={(e) => setPeriod(e.target.value)}>
            <option value="todas">Qualquer período</option>
            <option value="hoje">Hoje</option>
            <option value="semana">Próximos 7 dias</option>
            <option value="atrasadas">Atrasadas</option>
            <option value="sem_prazo">Sem prazo</option>
          </select>
        </label>
      </div>
      <ActionError message={action.error} />
      <LoadState loading={loading} error={error} hasData={data !== null} reload={reload}>
        <Panel title={`${rows.length} ${rows.length === 1 ? "tarefa" : "tarefas"}`}>
          {rows.length ? (
            <div className="item-list">
              {rows.map(({ task, due }) => (
                <div className="resource-row" key={task.id}>
                  <button
                    className={task.status === "completed" ? "check done" : "check"}
                    disabled={action.busy}
                    aria-label={
                      task.status === "completed"
                        ? `Reabrir ${task.title}`
                        : `Concluir ${task.title}`
                    }
                    onClick={() => toggle(task)}
                  >
                    {task.status === "completed" ? "✓" : ""}
                  </button>
                  <div className="resource-main">
                    <strong className={task.status === "completed" ? "completed" : ""}>
                      {task.title}
                    </strong>
                    <small>
                      {due ? `${formatDay(due.date)} · ${due.time}` : "Sem prazo"}
                      {task.completed_at
                        ? ` · concluída em ${formatDay(instantToZoned(task.completed_at, timezone).date)}`
                        : ""}
                    </small>
                  </div>
                  {task.priority && (
                    <Badge
                      tone={
                        task.priority === "high"
                          ? "red"
                          : task.priority === "medium"
                            ? "orange"
                            : "neutral"
                      }
                    >
                      {priorityLabel[task.priority]}
                    </Badge>
                  )}
                  {task.sync_to_calendar && <Badge>Google solicitado</Badge>}
                  <button className="button secondary tiny" onClick={() => setEditing(task)}>
                    Editar
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <Empty
              title="Nenhuma tarefa encontrada"
              description="Crie uma tarefa ou ajuste os filtros para ver outros itens."
            />
          )}
          {data && data.total > data.items.length && (
            <p className="field-hint">
              Exibindo {data.items.length} de {data.total} tarefas (limite da página).
            </p>
          )}
        </Panel>
      </LoadState>
      {editing && (
        <LiveTaskForm
          timezone={timezone}
          notify={notify}
          authLost={authLost}
          item={editing}
          close={() => setEditing(null)}
          saved={reload}
        />
      )}
    </>
  );
}

function LiveTaskForm({
  timezone,
  notify,
  authLost,
  item,
  close,
  saved,
}: LiveProps & { item: Task | "new"; close: () => void; saved: () => void }) {
  const current = item === "new" ? null : item;
  const due = current?.due_at ? instantToZoned(current.due_at, timezone) : null;
  const [title, setTitle] = useState(current?.title ?? "");
  const [date, setDate] = useState(due?.date ?? "");
  const [time, setTime] = useState(due?.time ?? "");
  const [priority, setPriority] = useState<TaskPriority | "">(current?.priority ?? "");
  const [syncGoogle, setSyncGoogle] = useState(current?.sync_to_calendar ?? false);
  const [problem, setProblem] = useState("");
  const action = useAction({ notify, authLost });
  const [key] = useState(newIdempotencyKey);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return setProblem("Informe o título da tarefa.");
    // Sem horário padrão: um prazo exige data e hora explícitas.
    if (!!date !== !!time) return setProblem("Para definir um prazo, informe data e horário.");
    setProblem("");
    const dueAt = date && time ? zonedToInstant(date, time, timezone) : null;
    const ok = await action.run(
      () =>
        current
          ? tasksApi.update(current.id, {
              title: title.trim(),
              due_at: dueAt,
              priority: priority || null,
              sync_to_calendar: syncGoogle,
            })
          : tasksApi.create(
              {
                title: title.trim(),
                due_at: dueAt,
                priority: priority || null,
                sync_to_calendar: syncGoogle,
              },
              { idempotencyKey: key },
            ),
      current ? "Tarefa atualizada." : "Tarefa criada.",
    );
    if (ok) {
      saved();
      close();
    }
  }
  return (
    <div className="modal-backdrop">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="task-form-title"
        onKeyDown={(event) => handleDialogKeys(event, close)}
      >
        <div className="modal-head">
          <div>
            <p className="eyebrow">TAREFAS</p>
            <h2 id="task-form-title">{current ? "Editar tarefa" : "Nova tarefa"}</h2>
          </div>
          <button className="icon-button" onClick={close} aria-label="Fechar">
            ×
          </button>
        </div>
        <form className="form-stack" onSubmit={submit}>
          <Field label="O que precisa ser feito? *">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              autoFocus
              maxLength={200}
            />
          </Field>
          <div className="form-grid">
            <Field label="Prazo (opcional)">
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </Field>
            <Field label="Horário do prazo">
              <input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
            </Field>
          </div>
          <Field label="Prioridade">
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as TaskPriority | "")}
            >
              <option value="">Sem prioridade</option>
              <option value="low">Baixa</option>
              <option value="medium">Média</option>
              <option value="high">Alta</option>
            </select>
          </Field>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={syncGoogle}
              onChange={(e) => setSyncGoogle(e.target.checked)}
            />
            <span>
              Solicitar sincronização com Google Agenda
              <small>
                Opcional e somente por sua escolha. A integração ainda não está disponível; o pedido
                fica registrado na tarefa.
              </small>
            </span>
          </label>
          <ActionError message={problem || action.error} />
          <FormActions
            cancel={close}
            busy={action.busy}
            label={current ? "Salvar alterações" : "Criar tarefa"}
          />
        </form>
      </div>
    </div>
  );
}

// -- Rotinas --------------------------------------------------------------------------------

interface RoutineRow {
  routine: Routine;
  occurrences: Occurrence[];
}

export function LiveRoutinesView({ timezone, notify, authLost }: LiveProps) {
  const [editing, setEditing] = useState<Routine | "new" | null>(() => (wantsNew() ? "new" : null));
  const date = todayIn(timezone);
  const dates = Array.from({ length: 7 }, (_, index) => addDays(date, index - 3));
  const loader = async (): Promise<RoutineRow[]> => {
    const from = startOfDay(dates[0], timezone);
    const to = startOfDay(addDays(dates[6], 1), timezone);
    const list = await routinesApi.list();
    return Promise.all(
      list.items.map(async (routine) => ({
        routine,
        occurrences: routine.active
          ? (await routinesApi.generate(routine.id, { from, to })).occurrences
          : [],
      })),
    );
  };
  const { data, error, loading, reload } = useLoad(loader, authLost, `${date}|${timezone}`);
  const action = useAction({ notify, authLost });

  async function mark(
    row: RoutineRow,
    occurrence: Occurrence,
    kind: "complete" | "skip" | "reopen",
  ) {
    const ok = await action.run(
      () => routinesApi[kind](row.routine.id, occurrence.id),
      kind === "complete"
        ? "Realização registrada."
        : kind === "skip"
          ? "Ocorrência marcada como não realizada."
          : "Ocorrência reaberta.",
    );
    if (ok) reload();
  }
  async function toggleActive(routine: Routine) {
    const ok = await action.run(
      () =>
        routine.active ? routinesApi.deactivate(routine.id) : routinesApi.activate(routine.id),
      routine.active ? "Rotina desativada." : "Rotina reativada.",
    );
    if (ok) reload();
  }
  return (
    <>
      <Header
        eyebrow="CONSTÂNCIA"
        title="Rotinas"
        description="Crie seus ritmos e registre cada realização de forma consciente."
        action={
          <button className="button primary" onClick={() => setEditing("new")}>
            + Nova rotina
          </button>
        }
      />
      <ActionError message={action.error} />
      <LoadState loading={loading} error={error} hasData={data !== null} reload={reload}>
        <Panel title="Suas rotinas">
          {data?.length ? (
            <div className="routine-list">
              {data.map((row) => {
                const byDay = new Map(
                  row.occurrences.map((o) => [instantToZoned(o.scheduled_for, timezone).date, o]),
                );
                return (
                  <div className="routine-card" key={row.routine.id}>
                    <div className="routine-top">
                      <div>
                        <span className="routine-dot">↻</span>
                        <h3>
                          {row.routine.title} {!row.routine.active && <Badge>Inativa</Badge>}
                        </h3>
                        <small>{describeRule(row.routine.recurrence_rule)}</small>
                      </div>
                      <div className="heading-actions">
                        <button
                          className="button secondary tiny"
                          disabled={action.busy}
                          onClick={() => toggleActive(row.routine)}
                        >
                          {row.routine.active ? "Desativar" : "Reativar"}
                        </button>
                        <button
                          className="button secondary tiny"
                          onClick={() => setEditing(row.routine)}
                        >
                          Editar
                        </button>
                      </div>
                    </div>
                    {row.routine.active && (
                      <div className="occurrences">
                        {dates.map((day) => {
                          const occurrence = byDay.get(day);
                          return (
                            <div
                              className={occurrence ? "occurrence" : "occurrence inactive"}
                              key={day}
                            >
                              <span>{formatDay(day, { weekday: "short" })}</span>
                              <strong>{day.slice(-2)}</strong>
                              {occurrence ? (
                                <div className="occurrence-actions">
                                  <button
                                    title="Marcar realizada"
                                    disabled={action.busy}
                                    aria-label={`Marcar ${row.routine.title} realizada em ${day}`}
                                    className={occurrence.status === "completed" ? "selected" : ""}
                                    onClick={() =>
                                      mark(
                                        row,
                                        occurrence,
                                        occurrence.status === "completed" ? "reopen" : "complete",
                                      )
                                    }
                                  >
                                    ✓
                                  </button>
                                  <button
                                    title="Marcar não realizada"
                                    disabled={action.busy}
                                    aria-label={`Marcar ${row.routine.title} não realizada em ${day}`}
                                    className={
                                      occurrence.status === "skipped" ? "selected missed" : ""
                                    }
                                    onClick={() =>
                                      mark(
                                        row,
                                        occurrence,
                                        occurrence.status === "skipped" ? "reopen" : "skip",
                                      )
                                    }
                                  >
                                    –
                                  </button>
                                </div>
                              ) : (
                                <small>·</small>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                    <p className="field-hint">
                      Histórico:{" "}
                      {row.occurrences
                        .filter((o) => o.status !== "pending")
                        .sort((a, b) => b.scheduled_for.localeCompare(a.scheduled_for))
                        .slice(0, 5)
                        .map(
                          (o) =>
                            `${formatDay(instantToZoned(o.scheduled_for, timezone).date)} ${o.status === "completed" ? "realizada" : "não realizada"}`,
                        )
                        .join(" · ") || "Nenhum registro nesta semana"}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : (
            <Empty
              title="Sua rotina começa aqui"
              description="Crie uma rotina diária, semanal, por intervalo ou no último dia do mês."
            />
          )}
        </Panel>
      </LoadState>
      {editing && (
        <LiveRoutineForm
          timezone={timezone}
          notify={notify}
          authLost={authLost}
          item={editing}
          close={() => setEditing(null)}
          saved={reload}
        />
      )}
    </>
  );
}

function LiveRoutineForm({
  timezone,
  notify,
  authLost,
  item,
  close,
  saved,
}: LiveProps & { item: Routine | "new"; close: () => void; saved: () => void }) {
  const current = item === "new" ? null : item;
  const initial = current ? ruleToForm(current.recurrence_rule) : ({ kind: "daily" } as const);
  const editable = initial !== null;
  const [title, setTitle] = useState(current?.title ?? "");
  const [startDate, setStartDate] = useState(
    current?.recurrence_rule.start_date ?? todayIn(timezone),
  );
  const [time, setTime] = useState(current?.recurrence_rule.time.slice(0, 5) ?? "");
  const [kind, setKind] = useState<RecurrenceForm["kind"]>(initial?.kind ?? "daily");
  const [weekdays, setWeekdays] = useState(
    initial?.kind === "weekly" ? initial.weekdays : [1, 2, 3, 4, 5],
  );
  const [every, setEvery] = useState(initial?.kind === "interval" ? initial.every : 2);
  const [unit, setUnit] = useState<"days" | "weeks">(
    initial?.kind === "interval" ? initial.unit : "days",
  );
  const [problem, setProblem] = useState("");
  const action = useAction({ notify, authLost });
  const [key] = useState(newIdempotencyKey);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return setProblem("Informe o nome da rotina.");
    const form: RecurrenceForm =
      kind === "weekly"
        ? { kind, weekdays }
        : kind === "interval"
          ? { kind, every, unit }
          : { kind };
    if (editable) {
      if (!startDate || !time) return setProblem("Informe a data inicial e o horário.");
      const issue = validateRecurrence(form);
      if (issue) return setProblem(issue);
    }
    setProblem("");
    const rule = editable
      ? formToRule(form, {
          startDate,
          time,
          timezone: current?.recurrence_rule.timezone ?? timezone,
        })
      : undefined;
    const ok = await action.run(
      () =>
        current
          ? routinesApi.update(current.id, {
              title: title.trim(),
              ...(rule ? { recurrence_rule: rule } : {}),
            })
          : routinesApi.create(
              { title: title.trim(), recurrence_rule: rule! },
              { idempotencyKey: key },
            ),
      current ? "Rotina atualizada." : "Rotina criada.",
    );
    if (ok) {
      saved();
      close();
    }
  }
  return (
    <div className="modal-backdrop">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="routine-form-title"
        onKeyDown={(event) => handleDialogKeys(event, close)}
      >
        <div className="modal-head">
          <div>
            <p className="eyebrow">ROTINAS</p>
            <h2 id="routine-form-title">{current ? "Editar rotina" : "Nova rotina"}</h2>
          </div>
          <button className="icon-button" onClick={close} aria-label="Fechar">
            ×
          </button>
        </div>
        <form className="form-stack" onSubmit={submit}>
          <Field label="Nome da rotina *">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              autoFocus
              required
              maxLength={200}
            />
          </Field>
          {editable ? (
            <>
              <div className="form-grid">
                <Field label="Início *">
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    required
                  />
                </Field>
                <Field label="Horário *">
                  <input
                    type="time"
                    value={time}
                    onChange={(e) => setTime(e.target.value)}
                    required
                  />
                </Field>
              </div>
              <Field label="Recorrência">
                <select
                  value={kind}
                  onChange={(e) => setKind(e.target.value as RecurrenceForm["kind"])}
                >
                  <option value="daily">Todos os dias</option>
                  <option value="weekly">Dias da semana</option>
                  <option value="interval">A cada intervalo</option>
                  <option value="monthly_last">Último dia do mês</option>
                </select>
              </Field>
              {kind === "weekly" && (
                <fieldset className="weekday-field">
                  <legend>Dias da semana</legend>
                  {WEEKDAY_LABELS.map((label, index) => (
                    <label key={label}>
                      <input
                        type="checkbox"
                        checked={weekdays.includes(index)}
                        onChange={(e) =>
                          setWeekdays(
                            e.target.checked
                              ? [...weekdays, index]
                              : weekdays.filter((day) => day !== index),
                          )
                        }
                      />
                      {label}
                    </label>
                  ))}
                </fieldset>
              )}
              {kind === "interval" && (
                <div className="form-grid">
                  <Field label="A cada">
                    <input
                      type="number"
                      min={1}
                      value={every}
                      onChange={(e) => setEvery(Number(e.target.value))}
                    />
                  </Field>
                  <Field label="Unidade">
                    <select
                      value={unit}
                      onChange={(e) => setUnit(e.target.value as "days" | "weeks")}
                    >
                      <option value="days">Dias</option>
                      <option value="weeks">Semanas</option>
                    </select>
                  </Field>
                </div>
              )}
              <p className="field-hint">
                Horários seguem o fuso {current?.recurrence_rule.timezone ?? timezone}. Alterar a
                regra reposiciona as ocorrências já geradas.
              </p>
            </>
          ) : (
            <p className="field-hint">
              Esta rotina usa uma regra personalizada ({describeRule(current!.recurrence_rule)}).
              Aqui só é possível alterar o nome.
            </p>
          )}
          <ActionError message={problem || action.error} />
          <FormActions
            cancel={close}
            busy={action.busy}
            label={current ? "Salvar alterações" : "Criar rotina"}
          />
        </form>
      </div>
    </div>
  );
}

// -- Configurações --------------------------------------------------------------------------

export function LiveSettingsView({ email, timezone }: { email: string; timezone: string }) {
  return (
    <>
      <Header
        eyebrow="SEU ESPAÇO"
        title="Configurações"
        description="Ajuste como você prefere acompanhar seus dias."
      />
      <div className="settings-grid">
        <Panel title="Perfil">
          <div className="settings-body">
            <p className="eyebrow">CONTA</p>
            <strong>{email}</strong>
            <p className="muted">
              Fuso usado para exibir horários: {timezone} (detectado neste navegador).
            </p>
          </div>
        </Panel>
        <Panel title="Integrações">
          <div className="integration-row">
            <span className="integration-icon">G</span>
            <div>
              <strong>Google Agenda</strong>
              <small>Não configurado</small>
            </div>
            <Badge>Indisponível</Badge>
          </div>
          <div className="integration-row">
            <span className="integration-icon">W</span>
            <div>
              <strong>WhatsApp</strong>
              <small>Não configurado</small>
            </div>
            <Badge>Indisponível</Badge>
          </div>
        </Panel>
      </div>
      <Panel title="Fuso e notificações">
        <div className="settings-body">
          <p className="muted">
            A API ainda não publica endpoints de perfil nem de preferências de notificação (a tabela
            existe no banco, mas sem contrato HTTP). Por isso esses ajustes não podem ser salvos
            nesta versão e nenhum valor local é exibido como se fosse da sua conta.
          </p>
        </div>
      </Panel>
    </>
  );
}
