"""Regras de domínio de rotinas e ocorrências. Usado por web e WhatsApp (mesmo serviço).

Geração de ocorrências é função pura (`recurrence.generate_occurrences`) + persistência
idempotente aqui; o disparo periódico assíncrono é responsabilidade de GP-09.
Ocorrência só vira `completed` por comando explícito; o passar do tempo não a conclui.
"""

from uuid import UUID, uuid4

from pydantic import BaseModel

from app.auth.models import CurrentUser
from app.core.schemas import Page
from app.modules.common.audit import build_audit
from app.modules.common.errors import conflict, invalid, not_found, translate_repository_errors
from app.modules.common.idempotency import IdempotencyStore, NoPayload, run_idempotent
from app.modules.common.types import CLOCK_SKEW, Clock
from app.modules.routines.recurrence import generate_occurrences
from app.modules.routines.repository import OccurrenceFilter, RoutineRepository
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

ROUTINE = "routine"
OCCURRENCE = "routine_occurrence"


class RoutineService:
    def __init__(self, repo: RoutineRepository, idempotency: IdempotencyStore, clock: Clock):
        self._repo = repo
        self._idem = idempotency
        self._clock = clock

    # -- rotinas ---------------------------------------------------------------------------

    @translate_repository_errors
    def create(
        self, user: CurrentUser, data: RoutineCreate, idempotency_key: str | None = None
    ) -> RoutineRead:
        def action() -> RoutineRead:
            now = self._clock()
            routine = RoutineRead(
                id=uuid4(),
                user_id=user.id,
                title=data.title,
                recurrence_rule=data.recurrence_rule,
                active=True,
                created_at=now,
                updated_at=now,
            )
            audit = build_audit(
                user,
                ROUTINE,
                routine.id,
                "routine.created",
                now,
                after=routine,
                fields=("title", "recurrence_rule", "active"),
            )
            self._repo.add(routine, audit)
            return routine

        return self._idempotent(user, idempotency_key, "routines.create", data, RoutineRead, action)

    @translate_repository_errors
    def get(self, user: CurrentUser, routine_id: UUID) -> RoutineRead:
        routine = self._repo.get(user.id, routine_id)
        if routine is None:
            raise not_found("Rotina")
        return routine

    @translate_repository_errors
    def list(
        self, user: CurrentUser, active: bool | None, limit: int, offset: int
    ) -> Page[RoutineRead]:
        items, total = self._repo.list(user.id, active, limit, offset)
        return Page[RoutineRead](items=items, limit=limit, offset=offset, total=total)

    @translate_repository_errors
    def update(
        self,
        user: CurrentUser,
        routine_id: UUID,
        data: RoutineUpdate,
        idempotency_key: str | None = None,
    ) -> RoutineRead:
        def action() -> RoutineRead:
            current = self.get(user, routine_id)
            updated = current.model_copy(update=data.model_dump(exclude_unset=True))
            # model_dump converte a regra em dict; restaura o modelo validado.
            if data.recurrence_rule is not None:
                updated = updated.model_copy(update={"recurrence_rule": data.recurrence_rule})
            if updated == current:
                return current
            now = self._clock()
            updated = updated.model_copy(update={"updated_at": now})
            audit = build_audit(
                user,
                ROUTINE,
                current.id,
                "routine.updated",
                now,
                before=current,
                after=updated,
                fields=("title", "recurrence_rule"),
            )
            self._repo.update(updated, audit)
            return updated

        return self._idempotent(
            user, idempotency_key, f"routines.update:{routine_id}", data, RoutineRead, action
        )

    @translate_repository_errors
    def deactivate(
        self, user: CurrentUser, routine_id: UUID, idempotency_key: str | None = None
    ) -> RoutineRead:
        return self._set_active(user, routine_id, False, idempotency_key)

    @translate_repository_errors
    def activate(
        self, user: CurrentUser, routine_id: UUID, idempotency_key: str | None = None
    ) -> RoutineRead:
        return self._set_active(user, routine_id, True, idempotency_key)

    def _set_active(
        self, user: CurrentUser, routine_id: UUID, active: bool, key: str | None
    ) -> RoutineRead:
        verb = "activated" if active else "deactivated"

        def action() -> RoutineRead:
            current = self.get(user, routine_id)
            if current.active == active:
                return current
            now = self._clock()
            updated = current.model_copy(update={"active": active, "updated_at": now})
            audit = build_audit(
                user,
                ROUTINE,
                current.id,
                f"routine.{verb}",
                now,
                before=current,
                after=updated,
                fields=("active",),
            )
            self._repo.update(updated, audit)
            return updated

        return self._idempotent(
            user, key, f"routines.{verb}:{routine_id}", NoPayload(), RoutineRead, action
        )

    # -- ocorrências -----------------------------------------------------------------------

    @translate_repository_errors
    def generate_occurrences(
        self, user: CurrentUser, routine_id: UUID, window: OccurrenceWindow
    ) -> OccurrenceGeneration:
        """Materializa ocorrências `pending` da janela. Idempotente (reexecutar não duplica)."""
        routine = self.get(user, routine_id)
        if not routine.active:
            raise conflict("Rotina desativada não gera novas ocorrências.")
        instants = generate_occurrences(
            routine.recurrence_rule, window.window_start, window.window_end
        )
        candidates = [
            OccurrenceRead(
                id=uuid4(),
                routine_id=routine.id,
                user_id=user.id,
                scheduled_for=instant,
                status=OccurrenceStatus.PENDING,
            )
            for instant in instants
        ]
        created = self._repo.add_occurrences(candidates)
        flt = OccurrenceFilter(window.window_start, window.window_end)
        items, _ = self._repo.list_occurrences(
            user.id, routine.id, flt, limit=len(instants) or 1, offset=0
        )
        return OccurrenceGeneration(created=created, occurrences=items)

    @translate_repository_errors
    def list_occurrences(
        self, user: CurrentUser, routine_id: UUID, flt: OccurrenceFilter, limit: int, offset: int
    ) -> Page[OccurrenceRead]:
        self.get(user, routine_id)
        if flt.scheduled_from and flt.scheduled_to and flt.scheduled_from >= flt.scheduled_to:
            raise invalid("query.scheduled_to", "scheduled_to deve ser posterior a scheduled_from.")
        items, total = self._repo.list_occurrences(user.id, routine_id, flt, limit, offset)
        return Page[OccurrenceRead](items=items, limit=limit, offset=offset, total=total)

    @translate_repository_errors
    def complete_occurrence(
        self,
        user: CurrentUser,
        routine_id: UUID,
        occurrence_id: UUID,
        data: OccurrenceComplete | None = None,
        idempotency_key: str | None = None,
    ) -> OccurrenceRead:
        data = data or OccurrenceComplete()
        return self._transition(
            user,
            routine_id,
            occurrence_id,
            OccurrenceStatus.COMPLETED,
            "complete",
            idempotency_key,
            data,
        )

    @translate_repository_errors
    def skip_occurrence(
        self,
        user: CurrentUser,
        routine_id: UUID,
        occurrence_id: UUID,
        idempotency_key: str | None = None,
    ) -> OccurrenceRead:
        return self._transition(
            user, routine_id, occurrence_id, OccurrenceStatus.SKIPPED, "skip", idempotency_key
        )

    @translate_repository_errors
    def reopen_occurrence(
        self,
        user: CurrentUser,
        routine_id: UUID,
        occurrence_id: UUID,
        idempotency_key: str | None = None,
    ) -> OccurrenceRead:
        return self._transition(
            user, routine_id, occurrence_id, OccurrenceStatus.PENDING, "reopen", idempotency_key
        )

    def _transition(
        self,
        user: CurrentUser,
        routine_id: UUID,
        occurrence_id: UUID,
        target: OccurrenceStatus,
        verb: str,
        key: str | None,
        data: OccurrenceComplete | None = None,
    ) -> OccurrenceRead:
        def action() -> OccurrenceRead:
            current = self._repo.get_occurrence(user.id, routine_id, occurrence_id)
            if current is None:
                raise not_found("Ocorrência")
            if current.status == target:
                return current
            now = self._clock()
            completed_at = None
            if target == OccurrenceStatus.COMPLETED:
                completed_at = (data.completed_at if data else None) or now
                if completed_at > now + CLOCK_SKEW:
                    raise invalid("body.completed_at", "completed_at não pode estar no futuro.")
            updated = current.model_copy(update={"status": target, "completed_at": completed_at})
            audit = build_audit(
                user,
                OCCURRENCE,
                current.id,
                f"routine_occurrence.{verb}",
                now,
                before=current,
                after=updated,
                fields=("status", "completed_at"),
                extra={"routine_id": str(routine_id)},
            )
            self._repo.update_occurrence(updated, audit)
            return updated

        payload = data or NoPayload()
        return self._idempotent(
            user,
            key,
            f"routines.occurrence.{verb}:{routine_id}:{occurrence_id}",
            payload,
            OccurrenceRead,
            action,
        )

    def _idempotent[T: BaseModel](
        self,
        user: CurrentUser,
        key: str | None,
        scope: str,
        data: BaseModel,
        model: type[T],
        action,  # noqa: ANN001
    ) -> T:
        return run_idempotent(
            self._idem,
            user,
            key,
            scope,
            data.model_dump(mode="json", exclude_unset=True),
            model,
            self._clock(),
            action,
        )
