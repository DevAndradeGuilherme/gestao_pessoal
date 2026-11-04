"""Persistência de rotinas e ocorrências atrás de interface (GP-03 implementa a versão real).

Contrato: filtro por `user_id`; entidade + auditoria na mesma transação; `RepositoryError` em
falhas; `add_occurrences` ignora duplicatas de (`routine_id`, `scheduled_for`) — a unicidade
deve ser garantida pelo banco, tornando a geração idempotente e segura sob concorrência.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.common.audit import AuditEntry
from app.modules.common.memory import InMemoryAudit
from app.modules.routines.schemas import OccurrenceRead, OccurrenceStatus, RoutineRead


@dataclass(frozen=True)
class OccurrenceFilter:
    scheduled_from: datetime | None = None  # inclusivo
    scheduled_to: datetime | None = None  # exclusivo
    status: OccurrenceStatus | None = None


class RoutineRepository(Protocol):
    def add(self, routine: RoutineRead, audit: AuditEntry) -> None: ...

    def get(self, user_id: UUID, routine_id: UUID) -> RoutineRead | None: ...

    def list(
        self, user_id: UUID, active: bool | None, limit: int, offset: int
    ) -> tuple[list[RoutineRead], int]:
        """Ordenação: `created_at` descendente, desempate por `id`."""
        ...

    def update(self, routine: RoutineRead, audit: AuditEntry) -> None: ...

    def add_occurrences(self, occurrences: list[OccurrenceRead]) -> int:
        """Insere as inexistentes; devolve quantas foram criadas."""
        ...

    def list_occurrences(
        self, user_id: UUID, routine_id: UUID, flt: OccurrenceFilter, limit: int, offset: int
    ) -> tuple[list[OccurrenceRead], int]:
        """Ordenação: `scheduled_for` ascendente."""
        ...

    def get_occurrence(
        self, user_id: UUID, routine_id: UUID, occurrence_id: UUID
    ) -> OccurrenceRead | None: ...

    def update_occurrence(self, occurrence: OccurrenceRead, audit: AuditEntry) -> None: ...


class InMemoryRoutineRepository:
    def __init__(self, audit: InMemoryAudit) -> None:
        self._routines: dict[UUID, RoutineRead] = {}
        self._occurrences: dict[UUID, OccurrenceRead] = {}
        self._audit = audit

    def add(self, routine: RoutineRead, audit: AuditEntry) -> None:
        self._routines[routine.id] = routine
        self._audit.entries.append(audit)

    def get(self, user_id: UUID, routine_id: UUID) -> RoutineRead | None:
        row = self._routines.get(routine_id)
        return row if row is not None and row.user_id == user_id else None

    def list(
        self, user_id: UUID, active: bool | None, limit: int, offset: int
    ) -> tuple[list[RoutineRead], int]:
        rows = [r for r in self._routines.values() if r.user_id == user_id]
        if active is not None:
            rows = [r for r in rows if r.active == active]
        rows.sort(key=lambda r: (-r.created_at.timestamp(), r.id))
        return rows[offset : offset + limit], len(rows)

    def update(self, routine: RoutineRead, audit: AuditEntry) -> None:
        self._routines[routine.id] = routine
        self._audit.entries.append(audit)

    def add_occurrences(self, occurrences: list[OccurrenceRead]) -> int:
        taken = {(o.routine_id, o.scheduled_for) for o in self._occurrences.values()}
        created = 0
        for occ in occurrences:
            if (occ.routine_id, occ.scheduled_for) in taken:
                continue
            self._occurrences[occ.id] = occ
            taken.add((occ.routine_id, occ.scheduled_for))
            created += 1
        return created

    def list_occurrences(
        self, user_id: UUID, routine_id: UUID, flt: OccurrenceFilter, limit: int, offset: int
    ) -> tuple[list[OccurrenceRead], int]:
        rows = [
            o
            for o in self._occurrences.values()
            if o.user_id == user_id and o.routine_id == routine_id
        ]
        if flt.scheduled_from is not None:
            rows = [o for o in rows if o.scheduled_for >= flt.scheduled_from]
        if flt.scheduled_to is not None:
            rows = [o for o in rows if o.scheduled_for < flt.scheduled_to]
        if flt.status is not None:
            rows = [o for o in rows if o.status == flt.status]
        rows.sort(key=lambda o: (o.scheduled_for, o.id))
        return rows[offset : offset + limit], len(rows)

    def get_occurrence(
        self, user_id: UUID, routine_id: UUID, occurrence_id: UUID
    ) -> OccurrenceRead | None:
        row = self._occurrences.get(occurrence_id)
        if row is None or row.user_id != user_id or row.routine_id != routine_id:
            return None
        return row

    def update_occurrence(self, occurrence: OccurrenceRead, audit: AuditEntry) -> None:
        self._occurrences[occurrence.id] = occurrence
        self._audit.entries.append(audit)
