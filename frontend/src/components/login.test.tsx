// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/lib/auth", () => ({
  isSupabaseConfigured: () => true,
  getSupabase: () => ({
    auth: { signInWithPassword: async () => ({ error: new Error("inválido") }) },
  }),
}));

import { Login } from "./login";

afterEach(cleanup);

describe("login", () => {
  it("apresenta erro de autenticação sem expor detalhes do provedor", async () => {
    render(<Login />);
    fireEvent.change(screen.getByLabelText("E-mail"), { target: { value: "pessoa@example.com" } });
    fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "senha" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain("Confira seu e-mail"),
    );
    expect(screen.getByRole("button", { name: "Entrar" })).toHaveProperty("disabled", false);
  });
});
