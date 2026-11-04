"""Regras de domínio de compromissos. Usado por web e WhatsApp (mesmo serviço)."""

from uuid import UUID, uuid4

from app.auth.models import CurrentUser
from app.core.schemas import Page
from app.modules.appointments.repository import AppointmentFilter, AppointmentRepository
from app.modules.appointments.schemas import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentRead,
    AppointmentReschedule,
    AppointmentStatus,
    AppointmentUpdate,
    SyncStatus,
)
from app.modules.common.audit import build_audit
from app.modules.common.errors import (
    conflict,
    invalid,
    not_found,
    translate_repository_errors,
)
from app.modules.common.idempotency import IdempotencyStore, run_idempotent
from app.modules.common.types import Clock

ENTITY = "appointment"
_EDITABLE = ("title", "description", "location")


class AppointmentService:
    def __init__(
        self,
        repo: AppointmentRepository,
        idempotency: IdempotencyStore,
        clock: Clock,
    ) -> None:
        self._repo = repo
        self._idem = idempotency
        self._clock = clock

    @translate_repository_errors
    def create(
        self, user: CurrentUser, data: AppointmentCreate, idempotency_key: str | None = None
    ) -> AppointmentRead:
        def action() -> AppointmentRead:
            now = self._clock()
            appointment = AppointmentRead(
                id=uuid4(),
                user_id=user.id,
                **data.model_dump(),
                status=AppointmentStatus.SCHEDULED,
                # Registro local primeiro; GP-06 sincroniza e ajusta o estado.
                sync_status=SyncStatus.PENDING,
                created_at=now,
                updated_at=now,
            )
            audit = build_audit(
                user,
                ENTITY,
                appointment.id,
                "appointment.created",
                now,
                after=appointment,
                fields=("title", "starts_at", "ends_at", "description", "location"),
            )
            self._repo.add(appointment, audit)
            return appointment

        return run_idempotent(
            self._idem,
            user,
            idempotency_key,
            "appointments.create",
            data.model_dump(mode="json", exclude_unset=True),
            AppointmentRead,
            self._clock(),
            action,
        )

    @translate_repository_errors
    def get(self, user: CurrentUser, appointment_id: UUID) -> AppointmentRead:
        appointment = self._repo.get(user.id, appointment_id)
        if appointment is None:
            raise not_found("Compromisso")
        return appointment

    @translate_repository_errors
    def list(
        self, user: CurrentUser, flt: AppointmentFilter, limit: int, offset: int
    ) -> Page[AppointmentRead]:
        if flt.starts_from and flt.starts_to and flt.starts_from >= flt.starts_to:
            raise invalid("query.starts_at_to", "starts_at_to deve ser posterior a starts_at_from.")
        items, total = self._repo.list(user.id, flt, limit, offset)
        return Page[AppointmentRead](items=items, limit=limit, offset=offset, total=total)

    @translate_repository_errors
    def update(
        self,
        user: CurrentUser,
        appointment_id: UUID,
        data: AppointmentUpdate,
        idempotency_key: str | None = None,
    ) -> AppointmentRead:
        def action() -> AppointmentRead:
            current = self._active(user, appointment_id)
            changes = data.model_dump(exclude_unset=True)
            updated = current.model_copy(update=changes)
            if updated == current:
                return current
            now = self._clock()
            updated = self._touch(updated, current, now)
            audit = build_audit(
                user,
                ENTITY,
                current.id,
                "appointment.updated",
                now,
                before=current,
                after=updated,
                fields=_EDITABLE,
            )
            self._repo.update(updated, audit)
            return updated

        return self._idempotent(
            user, idempotency_key, f"appointments.update:{appointment_id}", data, action
        )

    @translate_repository_errors
    def reschedule(
        self,
        user: CurrentUser,
        appointment_id: UUID,
        data: AppointmentReschedule,
        idempotency_key: str | None = None,
    ) -> AppointmentRead:
        def action() -> AppointmentRead:
            current = self._active(user, appointment_id)
            now = self._clock()
            updated = current.model_copy(
                update={"starts_at": data.starts_at, "ends_at": data.ends_at}
            )
            updated = self._touch(updated, current, now)
            audit = build_audit(
                user,
                ENTITY,
                current.id,
                "appointment.rescheduled",
                now,
                before=current,
                after=updated,
                fields=("starts_at", "ends_at"),
            )
            self._repo.update(updated, audit)
            return updated

        return self._idempotent(
            user, idempotency_key, f"appointments.reschedule:{appointment_id}", data, action
        )

    @translate_repository_errors
    def cancel(
        self,
        user: CurrentUser,
        appointment_id: UUID,
        data: AppointmentCancel | None = None,
        idempotency_key: str | None = None,
    ) -> AppointmentRead:
        data = data or AppointmentCancel()

        def action() -> AppointmentRead:
            current = self.get(user, appointment_id)
            if current.status == AppointmentStatus.CANCELLED:
                return current  # já cancelado: sem nova mutação nem auditoria
            now = self._clock()
            updated = current.model_copy(update={"status": AppointmentStatus.CANCELLED})
            updated = self._touch(updated, current, now)
            audit = build_audit(
                user,
                ENTITY,
                current.id,
                "appointment.cancelled",
                now,
                before=current,
                after=updated,
                fields=("status", "sync_status"),
                extra={"reason": data.reason} if data.reason else None,
            )
            self._repo.update(updated, audit)
            return updated

        return self._idempotent(
            user, idempotency_key, f"appointments.cancel:{appointment_id}", data, action
        )

    # -- helpers ---------------------------------------------------------------------------

    def _active(self, user: CurrentUser, appointment_id: UUID) -> AppointmentRead:
        appointment = self._repo.get(user.id, appointment_id)
        if appointment is None:
            raise not_found("Compromisso")
        if appointment.status == AppointmentStatus.CANCELLED:
            raise conflict("Compromisso cancelado não pode ser alterado.")
        return appointment

    @staticmethod
    def _touch(updated: AppointmentRead, current: AppointmentRead, now) -> AppointmentRead:  # noqa: ANN001
        """Atualiza `updated_at` e marca re-sincronização se o item já participa do sync."""
        sync = current.sync_status
        if sync != SyncStatus.NOT_APPLICABLE:
            sync = SyncStatus.PENDING
        return updated.model_copy(update={"updated_at": now, "sync_status": sync})

    def _idempotent(self, user, key, scope, data, action):  # noqa: ANN001, ANN202
        return run_idempotent(
            self._idem,
            user,
            key,
            scope,
            data.model_dump(mode="json", exclude_unset=True),
            AppointmentRead,
            self._clock(),
            action,
        )
