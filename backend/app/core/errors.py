"""Envelope de erro padrão da API (contrato em `docs/CONTRATOS.md`).

Toda resposta de erro tem o formato `{"error": {...}}` definido por `ErrorResponse`.
Módulos de domínio sinalizam falhas levantando `AppError`, nunca montando
respostas de erro manualmente.
"""

import logging
from enum import StrEnum
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_id import REQUEST_ID_HEADER

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    BAD_REQUEST = "bad_request"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    CONFLICT = "conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    RATE_LIMITED = "rate_limited"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INTERNAL_ERROR = "internal_error"


_STATUS_TO_CODE: dict[int, ErrorCode] = {
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.CONFLICT,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
    502: ErrorCode.EXTERNAL_SERVICE_ERROR,
    503: ErrorCode.SERVICE_UNAVAILABLE,
}


class ErrorDetail(BaseModel):
    """Detalhe por campo; `field` usa caminho pontuado (ex.: `body.starts_at`)."""

    field: str | None = None
    message: str
    type: str | None = None


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    details: list[ErrorDetail] = []
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class AppError(Exception):
    """Erro de aplicação com status HTTP e código estável para os clientes."""

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


def _error_response(
    request: Request,
    status_code: int,
    code: ErrorCode,
    message: str,
    details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    # Lido de `request.state` porque o handler de 500 roda fora do RequestIdMiddleware.
    request_id = getattr(request.state, "request_id", None)
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details or [], request_id=request_id)
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _error_response(request, exc.status_code, exc.code, exc.message, exc.details)


async def _http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _STATUS_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    return _error_response(request, exc.status_code, code, message, headers=exc.headers)


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        ErrorDetail(
            field=".".join(str(part) for part in err.get("loc", ())) or None,
            message=err.get("msg", "Valor inválido."),
            type=err.get("type"),
        )
        for err in exc.errors()
    ]
    return _error_response(
        request, 422, ErrorCode.VALIDATION_ERROR, "Os dados enviados são inválidos.", details
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Detalhes ficam apenas no log do servidor; o cliente recebe mensagem genérica.
    logger.exception("Erro não tratado", exc_info=exc)
    response = _error_response(request, 500, ErrorCode.INTERNAL_ERROR, "Erro interno inesperado.")
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_error_handler)
