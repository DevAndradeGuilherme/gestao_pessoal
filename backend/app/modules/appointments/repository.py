"""Persistência de compromissos atrás de interface (GP-03 implementa a versão real).

Contrato: toda consulta filtra por `user_id`; `add`/`update` gravam a entidade **e** a entrada
de auditoria na mesma transação; falhas levantam `RepositoryError`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.appointments.schemas import AppointmentRead, AppointmentStatus
from app.modules.common.audit import AuditEntry
from app.modules.common.memory import InMemoryAudit


@dataclass(frozen=True)
class AppointmentFilter:
    starts_from: datetime | None = None  # inclusivo
    starts_to: datetime | None = None  # exclusivo
    status: AppointmentStatus | None = None


class AppointmentRepository(Protocol):
    def add(self, appointment: AppointmentRead, audit: AuditEntry) -> None: ...

    def get(self, user_id: UUID, appointment_id: UUID) -> AppointmentRead | None: ...

    def list(
        self, user_id: UUID, flt: AppointmentFilter, limit: int, offset: int
    ) -> tuple[list[AppointmentRead], int]:
        """Ordenação: `starts_at` ascendente, desempate por `id`."""
        ...

    def update(self, appointment: AppointmentRead, audit: AuditEntry) -> None: ...


class InMemoryAppointmentRepository:
    def __init__(self, audit: InMemoryAudit) -> None:
        self._rows: dict[UUID, AppointmentRead] = {}
        self._audit = audit

    def add(self, appointment: AppointmentRead, audit: AuditEntry) -> None:
        self._rows[appointment.id] = appointment
        self._audit.entries.append(audit)

    def get(self, user_id: UUID, appointment_id: UUID) -> AppointmentRead | None:
        row = self._rows.get(appointment_id)
        return row if row is not None and row.user_id == user_id else None

    def list(
        self, user_id: UUID, flt: AppointmentFilter, limit: int, offset: int
    ) -> tuple[list[AppointmentRead], int]:
        rows = [r for r in self._rows.values() if r.user_id == user_id]
        if flt.starts_from is not None:
            rows = [r for r in rows if r.starts_at >= flt.starts_from]
        if flt.starts_to is not None:
            rows = [r for r in rows if r.starts_at < flt.starts_to]
        if flt.status is not None:
            rows = [r for r in rows if r.status == flt.status]
        rows.sort(key=lambda r: (r.starts_at, r.id))
        return rows[offset : offset + limit], len(rows)

    def update(self, appointment: AppointmentRead, audit: AuditEntry) -> None:
        self._rows[appointment.id] = appointment
        self._audit.entries.append(audit)
