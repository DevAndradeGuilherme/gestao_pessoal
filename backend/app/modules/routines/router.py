"""Transporte HTTP de rotinas e ocorrências (`/api/v1/routines`)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUserDep
from app.core.errors import ErrorResponse
from app.core.schemas import Page
from app.modules.common.deps import ClockDep, IdempotencyKeyDep, PageDep, StoresDep
from app.modules.common.types import UtcDatetime
from app.modules.routines.repository import OccurrenceFilter
from app.modules.routines.schemas import (
    OccurrenceComplete,
    OccurrenceGeneration,
    OccurrenceRead,
    OccurrenceStatus,
    OccurrenceWindow,
    RoutineCreate,
    RoutineRead,
    RoutineUpdate,
)
from app.modules.routines.service import RoutineService

router = APIRouter(prefix="/routines", tags=["routines"])

_CONFLICTS = {409: {"model": ErrorResponse, "description": "Conflito de estado ou idempotência"}}


def _service(stores: StoresDep, clock: ClockDep) -> RoutineService:
    return RoutineService(stores.routines, stores.idempotency, clock)


@router.post("", response_model=RoutineRead, status_code=201, responses=_CONFLICTS)
def create_routine(
    body: RoutineCreate,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
) -> RoutineRead:
    return _service(stores, clock).create(user, body, key)


@router.get("", response_model=Page[RoutineRead])
def list_routines(
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    page: PageDep,
    active: Annotated[bool | None, Query()] = None,
) -> Page[RoutineRead]:
    """Mais recentes primeiro (`created_at` descendente)."""
    return _service(stores, clock).list(user, active, page.limit, page.offset)


@router.get("/{routine_id}", response_model=RoutineRead)
def get_routine(
    routine_id: UUID, user: CurrentUserDep, stores: StoresDep, clock: ClockDep
) -> RoutineRead:
    return _service(stores, clock).get(user, routine_id)


@router.patch("/{routine_id}", response_model=RoutineRead, responses=_CONFLICTS)
def update_routine(
    routine_id: UUID,
    body: RoutineUpdate,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
) -> RoutineRead:
    return _service(stores, clock).update(user, routine_id, body, key)


@router.post("/{routine_id}/deactivate", response_model=RoutineRead, responses=_CONFLICTS)
def deactivate_routine(
    routine_id: UUID,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
) -> RoutineRead:
    """Desativa (não exclui); histórico de ocorrências é preservado."""
    return _service(stores, clock).deactivate(user, routine_id, key)


@router.post("/{routine_id}/activate", response_model=RoutineRead, responses=_CONFLICTS)
def activate_routine(
    routine_id: UUID,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
) -> RoutineRead:
    return _service(stores, clock).activate(user, routine_id, key)


@router.get("/{routine_id}/occurrences", response_model=Page[OccurrenceRead])
def list_occurrences(
    routine_id: UUID,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    page: PageDep,
    scheduled_for_from: Annotated[UtcDatetime | None, Query()] = None,
    scheduled_for_to: Annotated[UtcDatetime | None, Query()] = None,
    status: Annotated[OccurrenceStatus | None, Query()] = None,
) -> Page[OccurrenceRead]:
    """Ocorrências já materializadas, por `scheduled_for` ascendente. Intervalo `[from, to)`."""
    flt = OccurrenceFilter(scheduled_for_from, scheduled_for_to, status)
    return _service(stores, clock).list_occurrences(user, routine_id, flt, page.limit, page.offset)


@router.post(
    "/{routine_id}/occurrences/generate", response_model=OccurrenceGeneration, responses=_CONFLICTS
)
def generate_occurrences(
    routine_id: UUID,
    body: OccurrenceWindow,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
) -> OccurrenceGeneration:
    """Materializa ocorrências `pending` da janela. Idempotente por natureza (sem duplicar)."""
    return _service(stores, clock).generate_occurrences(user, routine_id, body)


@router.post(
    "/{routine_id}/occurrences/{occurrence_id}/complete",
    response_model=OccurrenceRead,
    responses=_CONFLICTS,
)
def complete_occurrence(
    routine_id: UUID,
    occurrence_id: UUID,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
    body: OccurrenceComplete | None = None,
) -> OccurrenceRead:
    return _service(stores, clock).complete_occurrence(user, routine_id, occurrence_id, body, key)


@router.post(
    "/{routine_id}/occurrences/{occurrence_id}/skip",
    response_model=OccurrenceRead,
    responses=_CONFLICTS,
)
def skip_occurrence(
    routine_id: UUID,
    occurrence_id: UUID,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
) -> OccurrenceRead:
    """Sinaliza que a ocorrência não foi realizada."""
    return _service(stores, clock).skip_occurrence(user, routine_id, occurrence_id, key)


@router.post(
    "/{routine_id}/occurrences/{occurrence_id}/reopen",
    response_model=OccurrenceRead,
    responses=_CONFLICTS,
)
def reopen_occurrence(
    routine_id: UUID,
    occurrence_id: UUID,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
) -> OccurrenceRead:
    return _service(stores, clock).reopen_occurrence(user, routine_id, occurrence_id, key)
