// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { newDemoState } from "@/lib/demo/store";
import { localDate, shiftDate } from "@/lib/demo/dates";
import { AgendaView, RoutinesView, TasksView, TodayView } from "./workspace-views";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
beforeEach(() => vi.stubGlobal("crypto", { randomUUID: () => "id-novo" }));

describe("telas críticas da demonstração", () => {
  it("mostra estado vazio e indicadores sem concluir itens automaticamente", () => {
    const state = { ...newDemoState(), timezone: "America/Sao_Paulo" };
    render(<TodayView state={state} save={vi.fn()} />);
    expect(screen.getByText("O dia está livre")).toBeTruthy();
    expect(screen.getByText("Nenhuma tarefa hoje")).toBeTruthy();
    expect(screen.getByText("Nenhuma rotina hoje")).toBeTruthy();
  });

  it("cria tarefa sem horário e sem opção Google marcada", () => {
    const save = vi.fn();
    render(<TasksView state={newDemoState()} save={save} />);
    fireEvent.click(screen.getByRole("button", { name: "+ Nova tarefa" }));
    fireEvent.change(screen.getByLabelText("O que precisa ser feito? *"), {
      target: { value: "Pagar a conta" },
    });
    expect(screen.getByLabelText(/Solicitar sincronização com Google Agenda/)).toHaveProperty(
      "checked",
      false,
    );
    fireEvent.click(screen.getByRole("button", { name: "Criar tarefa" }));
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        tasks: [
          expect.objectContaining({
            title: "Pagar a conta",
            date: "",
            time: "",
            syncGoogle: false,
          }),
        ],
      }),
      expect.any(String),
    );
  });

  it("valida o fim sem inventar uma duração para o compromisso", () => {
    const save = vi.fn();
    render(<AgendaView state={newDemoState()} save={save} />);
    fireEvent.click(screen.getByRole("button", { name: "+ Novo compromisso" }));
    fireEvent.change(screen.getByLabelText("Título *"), { target: { value: "Consulta" } });
    fireEvent.change(screen.getByLabelText("Horário *"), { target: { value: "14:00" } });
    fireEvent.change(screen.getByLabelText("Fim (opcional)"), { target: { value: "13:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Criar compromisso" }));
    expect(screen.getByRole("alert").textContent).toContain("posterior");
    expect(save).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Fim (opcional)"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Criar compromisso" }));
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ appointments: [expect.objectContaining({ endTime: "" })] }),
      expect.any(String),
    );
  });

  it("registra uma ocorrência somente após ação explícita", () => {
    const state = newDemoState();
    const day = localDate(new Date(), state.timezone);
    state.routines = [
      {
        id: "rotina-1",
        title: "Meditar",
        startDate: shiftDate(day, -3),
        time: "",
        recurrence: { kind: "daily" },
        results: {},
      },
    ];
    const save = vi.fn();
    render(<RoutinesView state={state} save={save} />);
    expect(save).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: `Marcar Meditar realizada em ${day}` }));
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        routines: [expect.objectContaining({ results: { [day]: "realizada" } })],
      }),
      expect.any(String),
    );
  });
});
