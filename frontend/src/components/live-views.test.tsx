// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/domain", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/domain")>()),
  appointments: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    reschedule: vi.fn(),
    cancel: vi.fn(),
  },
  tasks: { list: vi.fn(), create: vi.fn(), update: vi.fn(), complete: vi.fn(), reopen: vi.fn() },
  routines: { list: vi.fn(), generate: vi.fn(), complete: vi.fn() },
}));

import { ApiError } from "@/lib/api/client";
import { appointments, tasks, routines } from "@/lib/api/domain";
import { LiveAgendaView, LiveRoutinesView, LiveTasksView, LiveTodayView } from "./live-views";

const page = (items: unknown[]) => ({ items, limit: 200, offset: 0, total: items.length });
const props = { timezone: "America/Sao_Paulo", notify: vi.fn(), authLost: vi.fn() };

beforeEach(() => {
  vi.mocked(appointments.list).mockResolvedValue(page([]) as never);
  vi.mocked(tasks.list).mockResolvedValue(page([]) as never);
  vi.mocked(routines.list).mockResolvedValue(page([]) as never);
  props.notify.mockReset();
  props.authLost.mockReset();
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("telas ligadas à API", () => {
  it("mostra carregamento e depois o estado vazio do dia", async () => {
    render(<LiveTodayView {...props} />);
    expect(screen.getByRole("status").textContent).toContain("Carregando");
    await screen.findByText("O dia está livre");
    expect(screen.getByText("Nenhuma tarefa hoje")).toBeTruthy();
    expect(screen.getByText("Nenhuma rotina hoje")).toBeTruthy();
  });

  it("exibe falha da API com nova tentativa, sem mostrar dados", async () => {
    vi.mocked(tasks.list).mockRejectedValueOnce(
      new ApiError(503, {
        code: "service_unavailable",
        message: "Persistência temporariamente indisponível.",
        details: [],
        request_id: "r1",
      }),
    );
    render(<LiveTasksView {...props} />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("indisponível");
    vi.mocked(tasks.list).mockResolvedValueOnce(page([]) as never);
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    await screen.findByText("Nenhuma tarefa encontrada");
  });

  it("sessão rejeitada pela API aciona a saída do espaço autenticado", async () => {
    vi.mocked(appointments.list).mockRejectedValueOnce(
      new ApiError(401, { code: "unauthenticated", message: "x", details: [], request_id: null }),
    );
    render(<LiveAgendaView {...props} />);
    await screen.findByRole("alert");
    expect(props.authLost).toHaveBeenCalled();
  });

  it("cria compromisso sem fim presumido e com instante UTC", async () => {
    vi.mocked(appointments.create).mockResolvedValue({} as never);
    render(<LiveAgendaView {...props} />);
    await screen.findByText("Nenhum compromisso neste período");
    fireEvent.click(screen.getByRole("button", { name: "+ Novo compromisso" }));
    fireEvent.change(screen.getByLabelText("Título *"), { target: { value: "Consulta" } });
    fireEvent.change(screen.getByLabelText("Data *"), { target: { value: "2030-01-10" } });
    fireEvent.change(screen.getByLabelText("Horário *"), { target: { value: "14:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Criar compromisso" }));
    await waitFor(() => expect(appointments.create).toHaveBeenCalledTimes(1));
    const [body, options] = vi.mocked(appointments.create).mock.calls[0];
    expect(body).toMatchObject({
      title: "Consulta",
      starts_at: "2030-01-10T17:00:00.000Z",
      ends_at: null,
    });
    expect(options?.idempotencyKey).toBeTruthy();
    await waitFor(() => expect(props.notify).toHaveBeenCalledWith("Compromisso criado."));
  });

  it("mantém o formulário aberto e mostra o erro quando a criação falha", async () => {
    vi.mocked(tasks.create).mockRejectedValueOnce(new TypeError("fetch failed"));
    render(<LiveTasksView {...props} />);
    await screen.findByText("Nenhuma tarefa encontrada");
    fireEvent.click(screen.getByRole("button", { name: "+ Nova tarefa" }));
    fireEvent.change(screen.getByLabelText("O que precisa ser feito? *"), {
      target: { value: "Pagar conta" },
    });
    expect(screen.getByLabelText(/Solicitar sincronização com Google Agenda/)).toHaveProperty(
      "checked",
      false,
    );
    fireEvent.click(screen.getByRole("button", { name: "Criar tarefa" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("conectar");
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(props.notify).not.toHaveBeenCalled();
  });

  it("exige data e horário juntos no prazo da tarefa (sem horário presumido)", async () => {
    render(<LiveTasksView {...props} />);
    await screen.findByText("Nenhuma tarefa encontrada");
    fireEvent.click(screen.getByRole("button", { name: "+ Nova tarefa" }));
    fireEvent.change(screen.getByLabelText("O que precisa ser feito? *"), {
      target: { value: "x" },
    });
    fireEvent.change(screen.getByLabelText("Prazo (opcional)"), {
      target: { value: "2030-01-10" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Criar tarefa" }));
    expect((await screen.findByRole("alert")).textContent).toContain("data e horário");
    expect(tasks.create).not.toHaveBeenCalled();
  });

  it("registra realização de rotina só após clique explícito", async () => {
    const routine = {
      id: "r1",
      title: "Meditar",
      active: true,
      recurrence_rule: {
        frequency: "daily",
        interval: 1,
        by_weekday: null,
        by_month_day: null,
        time: "07:00:00",
        timezone: "America/Sao_Paulo",
        start_date: "2030-01-01",
        end_date: null,
        count: null,
      },
    };
    vi.mocked(routines.list).mockResolvedValue(page([routine]) as never);
    vi.mocked(routines.generate).mockImplementation(async () => {
      const day = new Date();
      const iso = new Date(
        Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 10),
      ).toISOString();
      return {
        created: 1,
        occurrences: [
          {
            id: "o1",
            routine_id: "r1",
            user_id: "u",
            scheduled_for: iso,
            status: "pending",
            completed_at: null,
          },
        ],
      } as never;
    });
    vi.mocked(routines.complete).mockResolvedValue({} as never);
    render(<LiveRoutinesView {...props} />);
    await screen.findByText("Meditar");
    expect(routines.complete).not.toHaveBeenCalled();
    const button = (
      await screen.findAllByRole("button", { name: /Marcar Meditar realizada em/ })
    )[0];
    fireEvent.click(button);
    await waitFor(() => expect(routines.complete).toHaveBeenCalledWith("r1", "o1"));
  });
});
