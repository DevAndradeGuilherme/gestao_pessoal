"""Persistência de tarefas atrás de interface (GP-03 implementa a versão real).

Mesmo contrato de `AppointmentRepository`: filtro por `user_id`, entidade + auditoria na mesma
transação, falhas como `RepositoryError`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.common.audit import AuditEntry
from app.modules.common.memory import InMemoryAudit
from app.modules.tasks.schemas import TaskPriority, TaskRead, TaskStatus


@dataclass(frozen=True)
class TaskFilter:
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    category: str | None = None
    due_from: datetime | None = None  # inclusivo
    due_to: datetime | None = None  # exclusivo
    overdue_before: datetime | None = None  # pendentes com due_at < este instante


class TaskRepository(Protocol):
    def add(self, task: TaskRead, audit: AuditEntry) -> None: ...

    def get(self, user_id: UUID, task_id: UUID) -> TaskRead | None: ...

    def list(
        self, user_id: UUID, flt: TaskFilter, limit: int, offset: int
    ) -> tuple[list[TaskRead], int]:
        """Ordenação: `due_at` ascendente (nulos por último), `created_at`, `id`."""
        ...

    def update(self, task: TaskRead, audit: AuditEntry) -> None: ...


class InMemoryTaskRepository:
    def __init__(self, audit: InMemoryAudit) -> None:
        self._rows: dict[UUID, TaskRead] = {}
        self._audit = audit

    def add(self, task: TaskRead, audit: AuditEntry) -> None:
        self._rows[task.id] = task
        self._audit.entries.append(audit)

    def get(self, user_id: UUID, task_id: UUID) -> TaskRead | None:
        row = self._rows.get(task_id)
        return row if row is not None and row.user_id == user_id else None

    def list(
        self, user_id: UUID, flt: TaskFilter, limit: int, offset: int
    ) -> tuple[list[TaskRead], int]:
        rows = [r for r in self._rows.values() if r.user_id == user_id]
        if flt.status is not None:
            rows = [r for r in rows if r.status == flt.status]
        if flt.priority is not None:
            rows = [r for r in rows if r.priority == flt.priority]
        if flt.category is not None:
            rows = [r for r in rows if r.category == flt.category]
        if flt.due_from is not None:
            rows = [r for r in rows if r.due_at is not None and r.due_at >= flt.due_from]
        if flt.due_to is not None:
            rows = [r for r in rows if r.due_at is not None and r.due_at < flt.due_to]
        if flt.overdue_before is not None:
            rows = [
                r
                for r in rows
                if r.status == TaskStatus.PENDING
                and r.due_at is not None
                and r.due_at < flt.overdue_before
            ]
        rows.sort(key=lambda r: (r.due_at is None, r.due_at or r.created_at, r.created_at, r.id))
        return rows[offset : offset + limit], len(rows)

    def update(self, task: TaskRead, audit: AuditEntry) -> None:
        self._rows[task.id] = task
        self._audit.entries.append(audit)
