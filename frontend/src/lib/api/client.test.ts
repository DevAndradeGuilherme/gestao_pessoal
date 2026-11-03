import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, getApiBaseUrl } from "./client";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("getApiBaseUrl", () => {
  it("usa a variável de ambiente sem barra final", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example/");
    expect(getApiBaseUrl()).toBe("https://api.example");
  });
});

describe("apiFetch", () => {
  it("devolve o JSON em respostas 2xx e envia o token", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/health", { accessToken: "jwt" })).resolves.toEqual({ status: "ok" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/health");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer jwt");
  });

  it("converte o envelope de erro em ApiError", async () => {
    const envelope = {
      error: { code: "not_found", message: "Não encontrado", details: [], request_id: "r1" },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(404, envelope)));

    const error = await apiFetch("/x").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).body.code).toBe("not_found");
  });

  it("gera ApiError genérico quando o corpo não segue o envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response("Bad Gateway", { status: 502, headers: { "X-Request-ID": "r2" } }),
        ),
    );

    const error = (await apiFetch("/x").catch((e: unknown) => e)) as ApiError;

    expect(error.body.code).toBe("internal_error");
    expect(error.body.request_id).toBe("r2");
  });
});
