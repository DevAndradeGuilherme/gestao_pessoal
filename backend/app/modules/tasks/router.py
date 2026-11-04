"""Transporte HTTP de tarefas (`/api/v1/tasks`)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUserDep
from app.core.errors import ErrorResponse
from app.core.schemas import Page
from app.modules.common.deps import ClockDep, IdempotencyKeyDep, PageDep, StoresDep
from app.modules.common.types import UtcDatetime
from app.modules.tasks.repository import TaskFilter
from app.modules.tasks.schemas import (
    TaskComplete,
    TaskCreate,
    TaskPriority,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)
from app.modules.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])

_CONFLICTS = {409: {"model": ErrorResponse, "description": "Conflito de estado ou idempotência"}}


def _service(stores: StoresDep, clock: ClockDep) -> TaskService:
    return TaskService(stores.tasks, stores.idempotency, clock)


@router.post("", response_model=TaskRead, status_code=201, responses=_CONFLICTS)
def create_task(
    body: TaskCreate,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
) -> TaskRead:
    return _service(stores, clock).create(user, body, key)


@router.get("", response_model=Page[TaskRead])
def list_tasks(
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    page: PageDep,
    status: Annotated[TaskStatus | None, Query()] = None,
    priority: Annotated[TaskPriority | None, Query()] = None,
    category: Annotated[str | None, Query(max_length=100)] = None,
    due_at_from: Annotated[UtcDatetime | None, Query()] = None,
    due_at_to: Annotated[UtcDatetime | None, Query()] = None,
    overdue: Annotated[bool, Query(description="Somente pendentes com prazo vencido")] = False,
) -> Page[TaskRead]:
    """Ordenado por `due_at` ascendente (sem prazo por último). Intervalo `[from, to)`."""
    flt = TaskFilter(
        status=status, priority=priority, category=category, due_from=due_at_from, due_to=due_at_to
    )
    return _service(stores, clock).list(user, flt, page.limit, page.offset, overdue=overdue)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, user: CurrentUserDep, stores: StoresDep, clock: ClockDep) -> TaskRead:
    return _service(stores, clock).get(user, task_id)


@router.patch("/{task_id}", response_model=TaskRead, responses=_CONFLICTS)
def update_task(
    task_id: UUID,
    body: TaskUpdate,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
) -> TaskRead:
    return _service(stores, clock).update(user, task_id, body, key)


@router.post("/{task_id}/complete", response_model=TaskRead, responses=_CONFLICTS)
def complete_task(
    task_id: UUID,
    user: CurrentUserDep,
    stores: StoresDep,
    clock: ClockDep,
    key: IdempotencyKeyDep,
    body: TaskComplete | None = None,
) -> TaskRead:
    """Conclusão explícita; grava `completed_at`. Já concluída => sem alteração."""
    return _service(stores, clock).complete(user, task_id, body, key)


@router.post("/{task_id}/reopen", response_model=TaskRead, responses=_CONFLICTS)
def reopen_task(
    task_id: UUID, user: CurrentUserDep, stores: StoresDep, clock: ClockDep, key: IdempotencyKeyDep
) -> TaskRead:
    return _service(stores, clock).reopen(user, task_id, key)


@router.post("/{task_id}/cancel", response_model=TaskRead, responses=_CONFLICTS)
def cancel_task(
    task_id: UUID, user: CurrentUserDep, stores: StoresDep, clock: ClockDep, key: IdempotencyKeyDep
) -> TaskRead:
    return _service(stores, clock).cancel(user, task_id, key)
