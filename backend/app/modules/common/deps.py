"""Injeção de dependências dos módulos de domínio.

`get_stores` falha fechada (503) até GP-03 entregar a persistência real: nenhuma rota de
domínio grava em memória por acidente. Testes sobrescrevem `get_stores` e `get_clock`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, Query

from app.core.errors import AppError, ErrorCode
from app.core.schemas import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, PageParams
from app.modules.appointments.repository import AppointmentRepository
from app.modules.common.audit import AuditRepository
from app.modules.common.idempotency import IdempotencyStore
from app.modules.common.types import Clock
from app.modules.routines.repository import RoutineRepository
from app.modules.tasks.repository import TaskRepository


@dataclass(frozen=True)
class Stores:
    appointments: AppointmentRepository
    tasks: TaskRepository
    routines: RoutineRepository
    audit: AuditRepository
    idempotency: IdempotencyStore


def get_stores() -> Stores:
    raise AppError(503, ErrorCode.SERVICE_UNAVAILABLE, "Persistência ainda não configurada.")


def get_clock() -> Clock:
    return lambda: datetime.now(UTC)


def get_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    return idempotency_key


StoresDep = Annotated[Stores, Depends(get_stores)]
ClockDep = Annotated[Clock, Depends(get_clock)]
IdempotencyKeyDep = Annotated[str | None, Depends(get_idempotency_key)]


def get_page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PageParams:
    """Paginação `limit`/`offset` do core, utilizável junto de outros filtros de query.

    `core.schemas.PageParamsQuery` (modelo de query) não combina com parâmetros avulsos.
    """
    return PageParams(limit=limit, offset=offset)


PageDep = Annotated[PageParams, Depends(get_page_params)]
