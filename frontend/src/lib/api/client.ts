import type { ErrorBody, ErrorResponse } from "./types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/+$/, "");
}

/** Erro HTTP da API já convertido para o envelope `{ error: {...} }`. */
export class ApiError extends Error {
  readonly status: number;
  readonly body: ErrorBody;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const error = (value as { error: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as ErrorBody).code === "string" &&
    typeof (error as ErrorBody).message === "string"
  );
}

export interface ApiRequestInit extends RequestInit {
  /** JWT de acesso do Supabase; enviado como `Authorization: Bearer`. */
  accessToken?: string;
}

/**
 * Chama a API FastAPI e devolve o JSON tipado.
 * Respostas não-2xx viram `ApiError`, inclusive quando o corpo não segue o envelope.
 */
export async function apiFetch<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { accessToken, headers, ...rest } = init;
  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");
  if (rest.body !== undefined && !requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json");
  }
  if (accessToken) requestHeaders.set("Authorization", `Bearer ${accessToken}`);

  const response = await fetch(`${getApiBaseUrl()}${path}`, { ...rest, headers: requestHeaders });
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const body: ErrorBody = isErrorResponse(payload)
      ? payload.error
      : {
          code: "internal_error",
          message: `Resposta inesperada da API (HTTP ${response.status}).`,
          details: [],
          request_id: response.headers.get("X-Request-ID"),
        };
    throw new ApiError(response.status, body);
  }

  return payload as T;
}
