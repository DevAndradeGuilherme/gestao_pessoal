import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@supabase/supabase-js", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({
        data: { session: { access_token: "jwt-de-teste" } },
        error: null,
      }),
    },
  }),
}));

import { ApiError } from "./client";
import { appointments, describeError, routines, tasks } from "./domain";

const fetchMock = vi.fn();
beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co");
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "publica");
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  fetchMock.mockReset();
  fetchMock.mockImplementation(
    async () => new Response(JSON.stringify({ items: [], limit: 200, offset: 0, total: 0 })),
  );
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

function lastCall() {
  const [url, init] = fetchMock.mock.calls.at(-1)!;
  return { url: url as string, init: init as RequestInit, headers: new Headers(init.headers) };
}

describe("adaptadores de domínio", () => {
  it("lista compromissos com intervalo semiaberto e token Bearer", async () => {
    await appointments.list({ from: "2030-01-01T03:00:00.000Z", to: "2030-01-08T03:00:00.000Z" });
    const { url, headers } = lastCall();
    expect(url).toContain("http://api.test/api/v1/appointments?");
    expect(url).toContain("starts_at_from=2030-01-01T03%3A00%3A00.000Z");
    expect(url).toContain("limit=200");
    expect(headers.get("Authorization")).toBe("Bearer jwt-de-teste");
  });

  it("envia Idempotency-Key e nunca user_id nas mutações", async () => {
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 201 }));
    await tasks.create({ title: "x" }, { idempotencyKey: "chave-1" });
    const { headers, init } = lastCall();
    expect(headers.get("Idempotency-Key")).toBe("chave-1");
    expect(JSON.parse(init.body as string)).toEqual({ title: "x" });
    expect(init.body).not.toContain("user_id");
  });

  it("gera chave nova por ação quando não informada e usa as rotas de ação", async () => {
    fetchMock.mockImplementation(async () => new Response("{}"));
    await appointments.cancel("a1");
    const first = lastCall();
    expect(first.url).toBe("http://api.test/api/v1/appointments/a1/cancel");
    await routines.complete("r1", "o1");
    const second = lastCall();
    expect(second.url).toBe("http://api.test/api/v1/routines/r1/occurrences/o1/complete");
    expect(second.headers.get("Idempotency-Key")).not.toBe(first.headers.get("Idempotency-Key"));
  });

  it("converte erros do envelope em ApiError e mensagens amigáveis", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: { code: "service_unavailable", message: "x", details: [], request_id: "r" },
        }),
        { status: 503 },
      ),
    );
    const error = await tasks.list().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(describeError(error)).toContain("indisponível");
    expect(describeError(new TypeError("fetch failed"))).toContain("conectar");
  });
});
