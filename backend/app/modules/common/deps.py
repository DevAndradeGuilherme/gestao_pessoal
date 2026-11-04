"""Injeção de dependências dos módulos de domínio.

`get_stores` abre uma transação PostgreSQL por requisição (papel `app_backend`, RLS e
`request.jwt.claim.sub` do usuário autenticado). Entidade, auditoria e chave de idempotência são
confirmadas juntas no fim da requisição (`scope="function"`: o commit ocorre **antes** de a
resposta ser enviada, então uma falha de commit vira 503 e nunca um 2xx falso). Banco ausente ou
indisponível falha fechado (503). Testes sobrescrevem `get_stores` e `get_clock` com fakes.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import psycopg
from fastapi import Depends, Header, Query

from app.auth.dependencies import CurrentUserDep
from app.core.errors import AppError, ErrorCode
from app.core.schemas import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, PageParams
from app.db.repos.appointments import PgAppointmentRepository
from app.db.repos.common import PgAudit, PgIdempotency
from app.db.repos.routines import PgRoutineRepository
from app.db.repos.tasks import PgTaskRepository
from app.db.session import DatabaseNotConfiguredError, user_transaction
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


logger = logging.getLogger(__name__)


def get_stores(user: CurrentUserDep) -> Iterator[Stores]:
    """Stores PostgreSQL ligados à transação do usuário autenticado (identidade vem do JWT)."""
    try:
        with user_transaction(user) as conn:
            yield Stores(
                appointments=PgAppointmentRepository(conn),
                tasks=PgTaskRepository(conn),
                routines=PgRoutineRepository(conn),
                audit=PgAudit(conn),
                idempotency=PgIdempotency(conn),
            )
    except (psycopg.Error, OSError, DatabaseNotConfiguredError) as exc:
        # Só o tipo vai ao log: mensagens do driver podem conter host/usuário do banco.
        logger.error("database unavailable: %s", type(exc).__name__)
        raise AppError(
            503, ErrorCode.SERVICE_UNAVAILABLE, "Persistência temporariamente indisponível."
        ) from exc


def get_clock() -> Clock:
    return lambda: datetime.now(UTC)


def get_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    return idempotency_key


StoresDep = Annotated[Stores, Depends(get_stores, scope="function")]
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
