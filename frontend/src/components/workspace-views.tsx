"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { dateLabel, localDate, occursOn, shiftDate } from "@/lib/demo/dates";
import type { Appointment, DemoState, Recurrence, Routine, Task } from "@/lib/demo/types";
import { validateAppointment, validateRoutine, validateTask } from "@/lib/demo/validation";
import { Badge, Empty, Field, FormActions, Header, Panel, handleDialogKeys } from "./ui";

type Save = (next: DemoState, message: string) => void;
type ViewProps = { state: DemoState; save: Save };

function today(state: DemoState) {
  return localDate(new Date(), state.timezone);
}
function id() {
  return crypto.randomUUID();
}
export function TodayView({ state, save }: ViewProps) {
  const date = today(state);
  const appointments = state.appointments.filter(
    (item) => item.date === date && item.status !== "cancelado",
  );
  const tasks = state.tasks.filter(
    (item) => item.date === date || (!item.date && item.status === "pendente"),
  );
  const routines = state.routines.filter((item) => occursOn(item.recurrence, item.startDate, date));
  const completed =
    tasks.filter((item) => item.status === "concluido").length +
    routines.filter((item) => item.results[date] === "realizada").length;
  const pending =
    appointments.filter((item) => item.status === "pendente").length +
    tasks.filter((item) => item.status === "pendente").length +
    routines.filter((item) => !item.results[date]).length;
  const overdue = state.tasks.filter(
    (item) => item.date && item.date < date && item.status === "pendente",
  ).length;
  const upcoming = [
    ...appointments.map((item) => ({
      key: item.id,
      type: "Compromisso",
      title: item.title,
      time: item.time || "Dia inteiro",
      date: item.date,
    })),
    ...tasks
      .filter((item) => item.status === "pendente")
      .map((item) => ({
        key: item.id,
        type: "Tarefa",
        title: item.title,
        time: item.time || "Sem horário",
        date: item.date || date,
      })),
    ...routines
      .filter((item) => !item.results[date])
      .map((item) => ({
        key: item.id,
        type: "Rotina",
        title: item.title,
        time: item.time || "Sem horário",
        date,
      })),
  ].sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`));
  return (
    <>
      <Header
        eyebrow="VISÃO GERAL"
        title="Bom dia, vamos organizar hoje."
        description={new Intl.DateTimeFormat("pt-BR", {
          timeZone: state.timezone,
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
                    className={task.status === "concluido" ? "check done" : "check"}
                    aria-label={
                      task.status === "concluido"
                        ? `Reabrir ${task.title}`
                        : `Concluir ${task.title}`
                    }
                    onClick={() =>
                      save(
                        {
                          ...state,
                          tasks: state.tasks.map((current) =>
                            current.id === task.id
                              ? {
                                  ...current,
                                  status: task.status === "concluido" ? "pendente" : "concluido",
                                  completedAt:
                                    task.status === "concluido" ? null : new Date().toISOString(),
                                }
                              : current,
                          ),
                        },
                        task.status === "concluido" ? "Tarefa reaberta." : "Tarefa concluída.",
                      )
                    }
                  >
                    {task.status === "concluido" ? "✓" : ""}
                  </button>
                  <span className={task.status === "concluido" ? "completed" : ""}>
                    {task.title}
                  </span>
                  <Badge>{task.time || "Sem horário"}</Badge>
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
          {routines.length ? (
            <div className="item-list">
              {routines.map((routine) => (
                <div className="task-row" key={routine.id}>
                  <span className="routine-dot">↻</span>
                  <span>{routine.title}</span>
                  {routine.results[date] ? (
                    <Badge tone="green">
                      {routine.results[date] === "realizada" ? "Realizada" : "Não realizada"}
                    </Badge>
                  ) : (
                    <button
                      className="button tiny"
                      onClick={() =>
                        save(
                          {
                            ...state,
                            routines: state.routines.map((current) =>
                              current.id === routine.id
                                ? {
                                    ...current,
                                    results: { ...current.results, [date]: "realizada" },
                                  }
                                : current,
                            ),
                          },
                          "Realização registrada.",
                        )
                      }
                    >
                      Marcar feita
                    </button>
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
    </>
  );
}

export function AgendaView({ state, save }: ViewProps) {
  const [mode, setMode] = useState<"dia" | "semana" | "mes">("semana");
  const [anchor, setAnchor] = useState(() => today(state));
  const [editing, setEditing] = useState<Appointment | "new" | null>(() =>
    typeof window !== "undefined" && new URLSearchParams(window.location.search).has("novo")
      ? "new"
      : null,
  );
  const start =
    mode === "dia"
      ? anchor
      : mode === "semana"
        ? shiftDate(anchor, -((new Date(`${anchor}T12:00:00Z`).getUTCDay() + 6) % 7))
        : `${anchor.slice(0, 7)}-01`;
  const days =
    mode === "dia"
      ? 1
      : mode === "semana"
        ? 7
        : new Date(Number(anchor.slice(0, 4)), Number(anchor.slice(5, 7)), 0).getDate();
  const dates = Array.from({ length: days }, (_, index) => shiftDate(start, index));
  const visible = state.appointments
    .filter(
      (item) =>
        item.date >= start && item.date <= dates[dates.length - 1] && item.status !== "cancelado",
    )
    .sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`));
  function move(direction: number) {
    if (mode === "mes") {
      const month = new Date(`${anchor.slice(0, 7)}-01T12:00:00Z`);
      month.setUTCMonth(month.getUTCMonth() + direction);
      setAnchor(month.toISOString().slice(0, 10));
    } else setAnchor(shiftDate(anchor, direction * (mode === "dia" ? 1 : 7)));
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
          <button onClick={() => setAnchor(today(state))}>Hoje</button>
          <button aria-label="Próximo período" onClick={() => move(1)}>
            ›
          </button>
          <strong>{dateLabel(start, state.timezone, { month: "long", year: "numeric" })}</strong>
        </div>
      </div>
      <Panel
        title={
          mode === "mes" ? "Visão mensal" : mode === "semana" ? "Visão semanal" : "Visão diária"
        }
      >
        <div className={mode === "mes" ? "calendar-grid month" : "calendar-grid"}>
          {dates.map((date) => (
            <button
              key={date}
              className={date === today(state) ? "calendar-day current" : "calendar-day"}
              onClick={() => {
                setAnchor(date);
                setMode("dia");
              }}
            >
              <span>{dateLabel(date, state.timezone, { weekday: "short" })}</span>
              <strong>{date.slice(-2)}</strong>
              <small>
                {state.appointments.filter(
                  (item) => item.date === date && item.status !== "cancelado",
                ).length || ""}
              </small>
            </button>
          ))}
        </div>
      </Panel>
      <Panel title="Compromissos do período">
        {visible.length ? (
          <div className="item-list">
            {visible.map((item) => (
              <div className="resource-row" key={item.id}>
                <div className="date-tile">
                  <strong>{item.date.slice(-2)}</strong>
                  <small>{dateLabel(item.date, state.timezone, { month: "short" })}</small>
                </div>
                <div className="resource-main">
                  <strong>{item.title}</strong>
                  <small>
                    {item.time}
                    {item.endTime ? ` – ${item.endTime}` : ""}
                    {item.location ? ` · ${item.location}` : ""}
                  </small>
                  <Badge tone="orange">
                    {item.syncStatus === "nao_conectado"
                      ? "Google não conectado"
                      : item.syncStatus === "sincronizado"
                        ? "Sincronizado"
                        : item.syncStatus === "falhou"
                          ? "Falha na sincronização"
                          : "Sincronização pendente"}
                  </Badge>
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
      {editing && (
        <AppointmentForm state={state} save={save} item={editing} close={() => setEditing(null)} />
      )}
    </>
  );
}

function AppointmentForm({
  state,
  save,
  item,
  close,
}: ViewProps & { item: Appointment | "new"; close: () => void }) {
  const current = item === "new" ? null : item;
  const [title, setTitle] = useState(current?.title ?? "");
  const [date, setDate] = useState(current?.date ?? today(state));
  const [time, setTime] = useState(current?.time ?? "");
  const [endTime, setEndTime] = useState(current?.endTime ?? "");
  const [location, setLocation] = useState(current?.location ?? "");
  const [description, setDescription] = useState(current?.description ?? "");
  const [error, setError] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    const issue = validateAppointment(title, date, time, endTime);
    if (issue) {
      setError(issue);
      return;
    }
    const updated: Appointment = {
      id: current?.id ?? id(),
      title: title.trim(),
      date,
      time,
      endTime,
      location: location.trim(),
      description: description.trim(),
      status: "pendente",
      syncStatus: "nao_conectado",
    };
    save(
      {
        ...state,
        appointments: current
          ? state.appointments.map((value) => (value.id === current.id ? updated : value))
          : [...state.appointments, updated],
      },
      current ? "Compromisso atualizado na demonstração." : "Compromisso criado na demonstração.",
    );
    close();
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
              maxLength={160}
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
            <input value={location} onChange={(e) => setLocation(e.target.value)} />
          </Field>
          <Field label="Descrição">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </Field>
          <p className="field-hint">
            Nenhuma duração será presumida. O Google Agenda não está conectado nesta demonstração.
          </p>
          {error && (
            <p role="alert" className="error-box">
              {error}
            </p>
          )}
          {current && (
            <button
              className="danger-link"
              type="button"
              onClick={() => {
                save(
                  {
                    ...state,
                    appointments: state.appointments.map((value) =>
                      value.id === current.id ? { ...value, status: "cancelado" } : value,
                    ),
                  },
                  "Compromisso cancelado na demonstração.",
                );
                close();
              }}
            >
              Cancelar compromisso
            </button>
          )}
          <FormActions cancel={close} label={current ? "Salvar alterações" : "Criar compromisso"} />
        </form>
      </div>
    </div>
  );
}

export function TasksView({ state, save }: ViewProps) {
  const [editing, setEditing] = useState<Task | "new" | null>(() =>
    typeof window !== "undefined" && new URLSearchParams(window.location.search).has("novo")
      ? "new"
      : null,
  );
  const [status, setStatus] = useState("todas");
  const [priority, setPriority] = useState("todas");
  const [period, setPeriod] = useState("todas");
  const date = today(state);
  const tasks = state.tasks
    .filter(
      (item) =>
        (status === "todas" || item.status === status) &&
        (priority === "todas" || item.priority === priority) &&
        (period === "todas" ||
          (period === "sem_prazo"
            ? !item.date
            : period === "atrasadas"
              ? item.date && item.date < date && item.status === "pendente"
              : period === "hoje"
                ? item.date === date
                : item.date >= date && item.date < shiftDate(date, 7))),
    )
    .sort((a, b) => `${a.date || "9999"}${a.time}`.localeCompare(`${b.date || "9999"}${b.time}`));
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
            <option value="pendente">Pendentes</option>
            <option value="concluido">Concluídas</option>
          </select>
        </label>
        <label>
          Prioridade
          <select value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="todas">Todas</option>
            <option value="alta">Alta</option>
            <option value="media">Média</option>
            <option value="baixa">Baixa</option>
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
      <Panel title={`${tasks.length} ${tasks.length === 1 ? "tarefa" : "tarefas"}`}>
        {tasks.length ? (
          <div className="item-list">
            {tasks.map((task) => (
              <div className="resource-row" key={task.id}>
                <button
                  className={task.status === "concluido" ? "check done" : "check"}
                  aria-label={
                    task.status === "concluido" ? `Reabrir ${task.title}` : `Concluir ${task.title}`
                  }
                  onClick={() =>
                    save(
                      {
                        ...state,
                        tasks: state.tasks.map((value) =>
                          value.id === task.id
                            ? {
                                ...value,
                                status: task.status === "concluido" ? "pendente" : "concluido",
                                completedAt:
                                  task.status === "concluido" ? null : new Date().toISOString(),
                              }
                            : value,
                        ),
                      },
                      task.status === "concluido" ? "Tarefa reaberta." : "Tarefa concluída.",
                    )
                  }
                >
                  {task.status === "concluido" ? "✓" : ""}
                </button>
                <div className="resource-main">
                  <strong className={task.status === "concluido" ? "completed" : ""}>
                    {task.title}
                  </strong>
                  <small>
                    {task.date
                      ? `${dateLabel(task.date, state.timezone)}${task.time ? ` · ${task.time}` : ""}`
                      : "Sem prazo"}
                  </small>
                </div>
                <Badge
                  tone={
                    task.priority === "alta"
                      ? "red"
                      : task.priority === "media"
                        ? "orange"
                        : "neutral"
                  }
                >
                  {task.priority === "media"
                    ? "Média"
                    : task.priority === "alta"
                      ? "Alta"
                      : "Baixa"}
                </Badge>
                {task.syncGoogle && <Badge>Google solicitado</Badge>}
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
      </Panel>
      {editing && (
        <TaskForm state={state} save={save} item={editing} close={() => setEditing(null)} />
      )}
    </>
  );
}

function TaskForm({
  state,
  save,
  item,
  close,
}: ViewProps & { item: Task | "new"; close: () => void }) {
  const current = item === "new" ? null : item;
  const [title, setTitle] = useState(current?.title ?? "");
  const [date, setDate] = useState(current?.date ?? "");
  const [time, setTime] = useState(current?.time ?? "");
  const [priority, setPriority] = useState<Task["priority"]>(current?.priority ?? "media");
  const [syncGoogle, setSyncGoogle] = useState(current?.syncGoogle ?? false);
  const [error, setError] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    const issue = validateTask(title, date, time);
    if (issue) {
      setError(issue);
      return;
    }
    const updated: Task = {
      id: current?.id ?? id(),
      title: title.trim(),
      date,
      time,
      priority,
      syncGoogle,
      status: current?.status ?? "pendente",
      completedAt: current?.completedAt ?? null,
    };
    save(
      {
        ...state,
        tasks: current
          ? state.tasks.map((value) => (value.id === current.id ? updated : value))
          : [...state.tasks, updated],
      },
      current ? "Tarefa atualizada na demonstração." : "Tarefa criada na demonstração.",
    );
    close();
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
              maxLength={160}
            />
          </Field>
          <div className="form-grid">
            <Field label="Prazo (opcional)">
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </Field>
            <Field label="Horário (opcional)">
              <input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
            </Field>
          </div>
          <Field label="Prioridade">
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as Task["priority"])}
            >
              <option value="baixa">Baixa</option>
              <option value="media">Média</option>
              <option value="alta">Alta</option>
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
                Opcional e somente por sua escolha. Nesta demonstração, nenhuma sincronização é
                feita.
              </small>
            </span>
          </label>
          {error && (
            <p role="alert" className="error-box">
              {error}
            </p>
          )}
          <FormActions cancel={close} label={current ? "Salvar alterações" : "Criar tarefa"} />
        </form>
      </div>
    </div>
  );
}

export function RoutinesView({ state, save }: ViewProps) {
  const [editing, setEditing] = useState<Routine | "new" | null>(() =>
    typeof window !== "undefined" && new URLSearchParams(window.location.search).has("novo")
      ? "new"
      : null,
  );
  const date = today(state);
  const dates = Array.from({ length: 7 }, (_, index) => shiftDate(date, index - 3));
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
      <Panel title="Suas rotinas">
        {state.routines.length ? (
          <div className="routine-list">
            {state.routines.map((routine) => (
              <div className="routine-card" key={routine.id}>
                <div className="routine-top">
                  <div>
                    <span className="routine-dot">↻</span>
                    <h3>{routine.title}</h3>
                    <small>
                      {describeRecurrence(routine.recurrence)}
                      {routine.time ? ` · ${routine.time}` : ""}
                    </small>
                  </div>
                  <button className="button secondary tiny" onClick={() => setEditing(routine)}>
                    Editar
                  </button>
                </div>
                <div className="occurrences">
                  {dates.map((day) => {
                    const active = occursOn(routine.recurrence, routine.startDate, day);
                    const result = routine.results[day];
                    return (
                      <div className={active ? "occurrence" : "occurrence inactive"} key={day}>
                        <span>{dateLabel(day, state.timezone, { weekday: "short" })}</span>
                        <strong>{day.slice(-2)}</strong>
                        {active ? (
                          <div className="occurrence-actions">
                            <button
                              title="Marcar realizada"
                              aria-label={`Marcar ${routine.title} realizada em ${day}`}
                              className={result === "realizada" ? "selected" : ""}
                              onClick={() =>
                                save(
                                  {
                                    ...state,
                                    routines: state.routines.map((value) =>
                                      value.id === routine.id
                                        ? {
                                            ...value,
                                            results: { ...value.results, [day]: "realizada" },
                                          }
                                        : value,
                                    ),
                                  },
                                  "Realização registrada.",
                                )
                              }
                            >
                              ✓
                            </button>
                            <button
                              title="Marcar não realizada"
                              aria-label={`Marcar ${routine.title} não realizada em ${day}`}
                              className={result === "nao_realizada" ? "selected missed" : ""}
                              onClick={() =>
                                save(
                                  {
                                    ...state,
                                    routines: state.routines.map((value) =>
                                      value.id === routine.id
                                        ? {
                                            ...value,
                                            results: { ...value.results, [day]: "nao_realizada" },
                                          }
                                        : value,
                                    ),
                                  },
                                  "Ocorrência marcada como não realizada.",
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
                <p className="field-hint">
                  Histórico:{" "}
                  {Object.entries(routine.results)
                    .sort(([a], [b]) => b.localeCompare(a))
                    .slice(0, 5)
                    .map(
                      ([day, result]) =>
                        `${dateLabel(day, state.timezone)} ${result === "realizada" ? "realizada" : "não realizada"}`,
                    )
                    .join(" · ") || "Nenhum registro ainda"}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <Empty
            title="Sua rotina começa aqui"
            description="Crie uma rotina diária, semanal, por intervalo ou no último dia do mês."
          />
        )}
      </Panel>
      {editing && (
        <RoutineForm state={state} save={save} item={editing} close={() => setEditing(null)} />
      )}
    </>
  );
}

function describeRecurrence(rule: Recurrence) {
  if (rule.kind === "daily") return "Todos os dias";
  if (rule.kind === "monthly_last") return "Último dia do mês";
  if (rule.kind === "interval")
    return `A cada ${rule.every} ${rule.unit === "days" ? "dia(s)" : "semana(s)"}`;
  return `Semanal · ${rule.weekdays.map((day) => ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"][day]).join(", ")}`;
}
function RoutineForm({
  state,
  save,
  item,
  close,
}: ViewProps & { item: Routine | "new"; close: () => void }) {
  const current = item === "new" ? null : item;
  const [title, setTitle] = useState(current?.title ?? "");
  const [startDate, setStartDate] = useState(current?.startDate ?? today(state));
  const [time, setTime] = useState(current?.time ?? "");
  const [kind, setKind] = useState<Recurrence["kind"]>(current?.recurrence.kind ?? "daily");
  const [weekdays, setWeekdays] = useState(
    current?.recurrence.kind === "weekly" ? current.recurrence.weekdays : [1, 2, 3, 4, 5],
  );
  const [every, setEvery] = useState(
    current?.recurrence.kind === "interval" ? current.recurrence.every : 2,
  );
  const [unit, setUnit] = useState<"days" | "weeks">(
    current?.recurrence.kind === "interval" ? current.recurrence.unit : "days",
  );
  const [error, setError] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    const recurrence: Recurrence =
      kind === "weekly"
        ? { kind, weekdays }
        : kind === "interval"
          ? { kind, every, unit }
          : { kind };
    const issue = validateRoutine(title, startDate, recurrence);
    if (issue) {
      setError(issue);
      return;
    }
    const updated: Routine = {
      id: current?.id ?? id(),
      title: title.trim(),
      startDate,
      time,
      recurrence,
      results: current?.results ?? {},
    };
    save(
      {
        ...state,
        routines: current
          ? state.routines.map((value) => (value.id === current.id ? updated : value))
          : [...state.routines, updated],
      },
      current ? "Rotina atualizada na demonstração." : "Rotina criada na demonstração.",
    );
    close();
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
            <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus required />
          </Field>
          <div className="form-grid">
            <Field label="Início *">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />
            </Field>
            <Field label="Horário (opcional)">
              <input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
            </Field>
          </div>
          <Field label="Recorrência">
            <select value={kind} onChange={(e) => setKind(e.target.value as Recurrence["kind"])}>
              <option value="daily">Todos os dias</option>
              <option value="weekly">Dias da semana</option>
              <option value="interval">A cada intervalo</option>
              <option value="monthly_last">Último dia do mês</option>
            </select>
          </Field>
          {kind === "weekly" && (
            <fieldset className="weekday-field">
              <legend>Dias da semana</legend>
              {["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"].map((label, index) => (
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
                <select value={unit} onChange={(e) => setUnit(e.target.value as "days" | "weeks")}>
                  <option value="days">Dias</option>
                  <option value="weeks">Semanas</option>
                </select>
              </Field>
            </div>
          )}
          {error && (
            <p role="alert" className="error-box">
              {error}
            </p>
          )}
          <FormActions cancel={close} label={current ? "Salvar alterações" : "Criar rotina"} />
        </form>
      </div>
    </div>
  );
}

export function SettingsView({ state, save, email }: ViewProps & { email: string }) {
  const [timezone, setTimezone] = useState(state.timezone);
  const [morningSummary, setMorningSummary] = useState(state.morningSummary);
  const [eveningReview, setEveningReview] = useState(state.eveningReview);
  const [quietStart, setQuietStart] = useState(state.quietStart);
  const [quietEnd, setQuietEnd] = useState(state.quietEnd);
  const [error, setError] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    try {
      new Intl.DateTimeFormat("pt-BR", { timeZone: timezone });
    } catch {
      setError("Informe um fuso IANA válido, como America/Sao_Paulo.");
      return;
    }
    setError("");
    save(
      { ...state, timezone, morningSummary, eveningReview, quietStart, quietEnd },
      "Preferências salvas neste navegador.",
    );
  }
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
            <strong>{email || "Demonstração local"}</strong>
            <p className="muted">Os dados de perfil reais dependem de GP-03.</p>
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
          <p className="field-hint">
            A conexão dependerá das integrações futuras. Nenhuma conta externa é acessada nesta
            tela.
          </p>
        </Panel>
      </div>
      <Panel title="Fuso e notificações">
        <form className="settings-form" onSubmit={submit}>
          <Field label="Fuso horário (IANA)">
            <input
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              required
              placeholder="America/Sao_Paulo"
            />
          </Field>
          <p className="field-hint">
            Horários são apresentados no fuso selecionado. Prefira nomes como America/Sao_Paulo.
          </p>
          <div className="form-grid">
            <Field label="Resumo matinal">
              <input
                type="time"
                value={morningSummary}
                onChange={(e) => setMorningSummary(e.target.value)}
                required
              />
            </Field>
            <Field label="Revisão noturna">
              <input
                type="time"
                value={eveningReview}
                onChange={(e) => setEveningReview(e.target.value)}
                required
              />
            </Field>
            <Field label="Silêncio a partir de">
              <input
                type="time"
                value={quietStart}
                onChange={(e) => setQuietStart(e.target.value)}
                required
              />
            </Field>
            <Field label="Silêncio até">
              <input
                type="time"
                value={quietEnd}
                onChange={(e) => setQuietEnd(e.target.value)}
                required
              />
            </Field>
          </div>
          <p className="field-hint">
            Estes valores são apenas uma prévia local; o envio de notificações depende de serviços
            futuros.
          </p>
          {error && (
            <p role="alert" className="error-box">
              {error}
            </p>
          )}
          <button className="button primary" type="submit">
            Salvar preferências
          </button>
        </form>
      </Panel>
    </>
  );
}
