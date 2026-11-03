// Tipos espelhando os schemas compartilhados do backend (`docs/openapi.json`).
// Fonte de verdade: Pydantic em `backend/app/core`. Alterações exigem atualizar
// `docs/CONTRATOS.md` e regenerar o OpenAPI.

export type ErrorCode =
  | "validation_error"
  | "bad_request"
  | "unauthenticated"
  | "forbidden"
  | "not_found"
  | "method_not_allowed"
  | "conflict"
  | "idempotency_conflict"
  | "rate_limited"
  | "external_service_error"
  | "service_unavailable"
  | "internal_error";

export interface ErrorDetail {
  field: string | null;
  message: string;
  type: string | null;
}

export interface ErrorBody {
  code: ErrorCode;
  message: string;
  details: ErrorDetail[];
  request_id: string | null;
}

export interface ErrorResponse {
  error: ErrorBody;
}

export interface Page<T> {
  items: T[];
  limit: number;
  offset: number;
  total: number;
}

export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  environment: string;
}
