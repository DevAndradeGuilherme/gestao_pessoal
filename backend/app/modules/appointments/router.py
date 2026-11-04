"""Transporte HTTP de compromissos (`/api/v1/appointments`)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUserDep
from app.core.errors import ErrorResponse
from app.core.schemas import Page
from app.modules.appointments.repository import AppointmentFilter
from app.modules.appointments.schemas import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentRead,
    AppointmentReschedule,
    AppointmentStatus,
    AppointmentUpdate,
)
from app.modules.appointments.service import AppointmentService
from app.modules.common.deps import ClockDep, IdempotencyKeyDep, PageDep, StoresDep
from app.modules.common.types import UtcDatetime

router = APIRouter(prefix="/appointments", tags=["appointments"])

_CONFLICTS = {
    409: {"model": ErrorResponse, "description": "Compromisso cancelado ou idempotency_conflict"}
}


def _service(stores: StoresDep, clock: ClockDep) -> AppointmentService:
    return AppointmentService(stores.appointments, stores.idempotency, clock)


@router.post("", response_model=AppointmentRead, status_code=201, responses=_CONFLICTS)
def create_appointment(
    body: AppointmentCreate,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
) -> AppointmentRead:
    return _service(stores, clock).create(user, body, key)


@router.get("", response_model=Page[AppointmentRead])
def list_appointments(
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    page: PageDep,
    starts_at_from: Annotated[UtcDatetime | None, Query()] = None,
    starts_at_to: Annotated[UtcDatetime | None, Query()] = None,
    status: Annotated[AppointmentStatus | None, Query()] = None,
) -> Page[AppointmentRead]:
    """Ordenado por `starts_at` ascendente. Intervalo semiaberto `[from, to)`."""
    flt = AppointmentFilter(starts_from=starts_at_from, starts_to=starts_at_to, status=status)
    return _service(stores, clock).list(user, flt, page.limit, page.offset)


@router.get("/{appointment_id}", response_model=AppointmentRead)
def get_appointment(
    appointment_id: UUID, user: CurrentUserDep, stores: StoresDep, clock: ClockDep
) -> AppointmentRead:
    return _service(stores, clock).get(user, appointment_id)


@router.patch("/{appointment_id}", response_model=AppointmentRead, responses=_CONFLICTS)
def update_appointment(
    appointment_id: UUID,
    body: AppointmentUpdate,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
) -> AppointmentRead:
    return _service(stores, clock).update(user, appointment_id, body, key)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentRead, responses=_CONFLICTS)
def reschedule_appointment(
    appointment_id: UUID,
    body: AppointmentReschedule,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
) -> AppointmentRead:
    return _service(stores, clock).reschedule(user, appointment_id, body, key)


@router.post("/{appointment_id}/cancel", response_model=AppointmentRead, responses=_CONFLICTS)
def cancel_appointment(
    appointment_id: UUID,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
    body: AppointmentCancel | None = None,
) -> AppointmentRead:
    """Cancelamento é transição de estado auditada, não exclusão física."""
    return _service(stores, clock).cancel(user, appointment_id, body, key)
