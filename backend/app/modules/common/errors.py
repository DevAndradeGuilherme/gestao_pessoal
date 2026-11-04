"""Erros e utilitários compartilhados pelos serviços de domínio."""

from collections.abc import Callable
from functools import wraps
from typing import Any

from app.core.errors import AppError, ErrorCode, ErrorDetail


class RepositoryError(Exception):
    """Falha de persistência (indisponibilidade, timeout, erro de driver).

    Implementações reais de repositório (GP-03) devem convertê-la a partir dos erros do driver.
    Regras de negócio violadas **não** usam esta exceção.
    """


def not_found(entity: str) -> AppError:
    # Recurso de outro usuário também responde 404 (não revela existência).
    return AppError(404, ErrorCode.NOT_FOUND, f"{entity} não encontrado(a).")


def conflict(message: str) -> AppError:
    return AppError(409, ErrorCode.CONFLICT, message)


def invalid(field: str, message: str) -> AppError:
    return AppError(
        422,
        ErrorCode.VALIDATION_ERROR,
        "Os dados enviados são inválidos.",
        [ErrorDetail(field=field, message=message, type="value_error")],
    )


def translate_repository_errors[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Converte `RepositoryError` em 503 `service_unavailable` (sem vazar detalhes do driver)."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> R:
        try:
            return fn(*args, **kwargs)
        except RepositoryError as exc:
            raise AppError(
                503, ErrorCode.SERVICE_UNAVAILABLE, "Persistência temporariamente indisponível."
            ) from exc

    return wrapper  # type: ignore[return-value]
