"""Regras de domínio de tarefas. Usado por web e WhatsApp (mesmo serviço).

`completed_at` só é gravado por comando explícito de conclusão; o passar do tempo nunca conclui.
Transições para o estado em que a tarefa já está são idempotentes (sem mutação nem auditoria).
"""

from dataclasses import replace
from uuid import UUID, uuid4

from pydantic import BaseModel

from app.auth.models import CurrentUser
from app.core.schemas import Page
from app.modules.common.audit import build_audit
from app.modules.common.errors import (
    conflict,
    invalid,
    not_found,
    translate_repository_errors,
)
from app.modules.common.idempotency import IdempotencyStore, NoPayload, run_idempotent
from app.modules.common.types import CLOCK_SKEW, Clock
from app.modules.tasks.repository import TaskFilter, TaskRepository
from app.modules.tasks.schemas import (
    TaskComplete,
    TaskCreate,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)

ENTITY = "task"
_EDITABLE = ("title", "description", "due_at", "priority", "category", "sync_to_calendar")


class TaskService:
    def __init__(self, repo: TaskRepository, idempotency: IdempotencyStore, clock: Clock) -> None:
        self._repo = repo
        self._idem = idempotency
        self._clock = clock

    @translate_repository_errors
    def create(
        self, user: CurrentUser, data: TaskCreate, idempotency_key: str | None = None
    ) -> TaskRead:
        def action() -> TaskRead:
            now = self._clock()
            task = TaskRead(
                id=uuid4(),
                user_id=user.id,
                **data.model_dump(),
                status=TaskStatus.PENDING,
                created_at=now,
                updated_at=now,
            )
            audit = build_audit(
                user, ENTITY, task.id, "task.created", now, after=task, fields=_EDITABLE
            )
            self._repo.add(task, audit)
            return task

        return self._idempotent(user, idempotency_key, "tasks.create", data, action)

    @translate_repository_errors
    def get(self, user: CurrentUser, task_id: UUID) -> TaskRead:
        task = self._repo.get(user.id, task_id)
        if task is None:
            raise not_found("Tarefa")
        return task

    @translate_repository_errors
    def list(
        self, user: CurrentUser, flt: TaskFilter, limit: int, offset: int, *, overdue: bool = False
    ) -> Page[TaskRead]:
        if flt.due_from and flt.due_to and flt.due_from >= flt.due_to:
            raise invalid("query.due_at_to", "due_at_to deve ser posterior a due_at_from.")
        if overdue:
            flt = replace(flt, overdue_before=self._clock())
        items, total = self._repo.list(user.id, flt, limit, offset)
        return Page[TaskRead](items=items, limit=limit, offset=offset, total=total)

    @translate_repository_errors
    def update(
        self,
        user: CurrentUser,
        task_id: UUID,
        data: TaskUpdate,
        idempotency_key: str | None = None,
    ) -> TaskRead:
        def action() -> TaskRead:
            current = self._not_cancelled(self.get(user, task_id))
            updated = current.model_copy(update=data.model_dump(exclude_unset=True))
            if updated == current:
                return current
            now = self._clock()
            updated = updated.model_copy(update={"updated_at": now})
            audit = build_audit(
                user,
                ENTITY,
                current.id,
                "task.updated",
                now,
                before=current,
                after=updated,
                fields=_EDITABLE,
            )
            self._repo.update(updated, audit)
            return updated

        return self._idempotent(user, idempotency_key, f"tasks.update:{task_id}", data, action)

    @translate_repository_errors
    def complete(
        self,
        user: CurrentUser,
        task_id: UUID,
        data: TaskComplete | None = None,
        idempotency_key: str | None = None,
    ) -> TaskRead:
        data = data or TaskComplete()

        def action() -> TaskRead:
            current = self.get(user, task_id)
            if current.status == TaskStatus.COMPLETED:
                return current
            self._not_cancelled(current)
            now = self._clock()
            completed_at = data.completed_at or now
            if completed_at > now + CLOCK_SKEW:
                raise invalid("body.completed_at", "completed_at não pode estar no futuro.")
            updated = current.model_copy(
                update={
                    "status": TaskStatus.COMPLETED,
                    "completed_at": completed_at,
                    "updated_at": now,
                }
            )
            audit = build_audit(
                user,
                ENTITY,
                current.id,
                "task.completed",
                now,
                before=current,
                after=updated,
                fields=("status", "completed_at"),
            )
            self._repo.update(updated, audit)
            return updated

        return self._idempotent(user, idempotency_key, f"tasks.complete:{task_id}", data, action)

    @translate_repository_errors
    def reopen(
        self, user: CurrentUser, task_id: UUID, idempotency_key: str | None = None
    ) -> TaskRead:
        def action() -> TaskRead:
            current = self.get(user, task_id)
            if current.status == TaskStatus.PENDING:
                return current
            self._not_cancelled(current)
            now = self._clock()
            updated = current.model_copy(
                update={"status": TaskStatus.PENDING, "completed_at": None, "updated_at": now}
            )
            audit = build_audit(
                user,
                ENTITY,
                current.id,
                "task.reopened",
                now,
                before=current,
                after=updated,
                fields=("status", "completed_at"),
            )
            self._repo.update(updated, audit)
            return updated

        return self._idempotent(
            user, idempotency_key, f"tasks.reopen:{task_id}", NoPayload(), action
        )

    @translate_repository_errors
    def cancel(
        self, user: CurrentUser, task_id: UUID, idempotency_key: str | None = None
    ) -> TaskRead:
        def action() -> TaskRead:
            current = self.get(user, task_id)
            if current.status == TaskStatus.CANCELLED:
                return current
            if current.status == TaskStatus.COMPLETED:
                raise conflict("Tarefa concluída não pode ser cancelada; reabra-a antes.")
            now = self._clock()
            updated = current.model_copy(update={"status": TaskStatus.CANCELLED, "updated_at": now})
            audit = build_audit(
                user,
                ENTITY,
                current.id,
                "task.cancelled",
                now,
                before=current,
                after=updated,
                fields=("status",),
            )
            self._repo.update(updated, audit)
            return updated

        return self._idempotent(
            user, idempotency_key, f"tasks.cancel:{task_id}", NoPayload(), action
        )

    # -- helpers ---------------------------------------------------------------------------

    @staticmethod
    def _not_cancelled(task: TaskRead) -> TaskRead:
        if task.status == TaskStatus.CANCELLED:
            raise conflict("Tarefa cancelada não pode ser alterada.")
        return task

    def _idempotent(
        self,
        user: CurrentUser,
        key: str | None,
        scope: str,
        data: BaseModel,
        action,  # noqa: ANN001
    ) -> TaskRead:
        return run_idempotent(
            self._idem,
            user,
            key,
            scope,
            data.model_dump(mode="json", exclude_unset=True),
            TaskRead,
            self._clock(),
            action,
        )
