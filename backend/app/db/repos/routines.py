"""Rotinas e ocorrências em PostgreSQL (`public.routines`, `public.routine_occurrences`).

Representação de ocorrências (ADR-003): o domínio expõe `scheduled_for` como instante UTC; a
tabela guarda a **data local** da ocorrência (`date`) no fuso da regra. Como a regra tem um único
horário por dia, `(routine_id, scheduled_for)` identifica a ocorrência. O instante é reconstruído
com a mesma fórmula do gerador (`recurrence.generate_occurrences`): data local + `time` no
`timezone` da regra. Alterar horário/fuso de uma regra reposiciona as ocorrências já materializadas.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg import Connection
from psycopg.types.json import Jsonb

from app.db.repos.common import insert_audit, pg_guard
from app.modules.common.audit import AuditEntry
from app.modules.common.errors import RepositoryError
from app.modules.routines.recurrence import RecurrenceRule
from app.modules.routines.repository import OccurrenceFilter
from app.modules.routines.schemas import OccurrenceRead, RoutineRead

_ROUTINE_COLUMNS = "id, user_id, title, recurrence_rule, active, created_at, updated_at"
_OCCURRENCE_SELECT = """select o.id, o.routine_id, o.user_id, o.scheduled_for, o.status,
           o.completed_at, r.recurrence_rule
       from public.routine_occurrences o
       join public.routines r on r.id = o.routine_id and r.user_id = o.user_id"""


def _instant(local_day, rule: RecurrenceRule) -> datetime:  # noqa: ANN001
    return datetime.combine(local_day, rule.time, tzinfo=ZoneInfo(rule.timezone)).astimezone(UTC)


def _occurrence(row: dict) -> OccurrenceRead:
    rule = RecurrenceRule.model_validate(row["recurrence_rule"])
    return OccurrenceRead(
        id=row["id"],
        routine_id=row["routine_id"],
        user_id=row["user_id"],
        scheduled_for=_instant(row["scheduled_for"], rule),
        status=row["status"],
        completed_at=row["completed_at"],
    )


def _json(rule: RecurrenceRule) -> Jsonb:
    return Jsonb(rule.model_dump(mode="json"))


class PgRoutineRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    # -- rotinas ---------------------------------------------------------------------------

    @pg_guard
    def add(self, routine: RoutineRead, audit: AuditEntry) -> None:
        self._conn.execute(
            f"""insert into public.routines ({_ROUTINE_COLUMNS})
                values (%s, %s, %s, %s, %s, %s, %s)""",
            (
                routine.id,
                routine.user_id,
                routine.title,
                _json(routine.recurrence_rule),
                routine.active,
                routine.created_at,
                routine.updated_at,
            ),
        )
        insert_audit(self._conn, audit)

    @pg_guard
    def get(self, user_id: UUID, routine_id: UUID) -> RoutineRead | None:
        row = self._conn.execute(
            f"select {_ROUTINE_COLUMNS} from public.routines where id = %s and user_id = %s",
            (routine_id, user_id),
        ).fetchone()
        return RoutineRead.model_validate(row) if row else None

    @pg_guard
    def list(
        self, user_id: UUID, active: bool | None, limit: int, offset: int
    ) -> tuple[list[RoutineRead], int]:
        where, params = ["user_id = %s"], [user_id]
        if active is not None:
            where.append("active = %s")
            params.append(active)
        clause = " and ".join(where)
        total = self._conn.execute(
            f"select count(*) as n from public.routines where {clause}",
            params,
        ).fetchone()["n"]
        rows = self._conn.execute(
            f"select {_ROUTINE_COLUMNS} from public.routines where {clause} "
            "order by created_at desc, id limit %s offset %s",
            [*params, limit, offset],
        ).fetchall()
        return [RoutineRead.model_validate(r) for r in rows], total

    @pg_guard
    def update(self, routine: RoutineRead, audit: AuditEntry) -> None:
        cur = self._conn.execute(
            """update public.routines set title = %s, recurrence_rule = %s, active = %s,
                   updated_at = %s
               where id = %s and user_id = %s""",
            (
                routine.title,
                _json(routine.recurrence_rule),
                routine.active,
                routine.updated_at,
                routine.id,
                routine.user_id,
            ),
        )
        if cur.rowcount != 1:
            raise RepositoryError("routine update affected no row")
        insert_audit(self._conn, audit)

    # -- ocorrências -----------------------------------------------------------------------

    @pg_guard
    def add_occurrences(self, occurrences: list[OccurrenceRead]) -> int:
        created = 0
        rules: dict[UUID, RecurrenceRule] = {}
        for occ in occurrences:
            if occ.routine_id not in rules:
                row = self._conn.execute(
                    "select recurrence_rule from public.routines where id = %s and user_id = %s",
                    (occ.routine_id, occ.user_id),
                ).fetchone()
                if row is None:
                    raise RepositoryError("routine not found for occurrence")
                rules[occ.routine_id] = RecurrenceRule.model_validate(row["recurrence_rule"])
            local_day = occ.scheduled_for.astimezone(
                ZoneInfo(rules[occ.routine_id].timezone)
            ).date()
            cur = self._conn.execute(
                """insert into public.routine_occurrences
                       (id, user_id, routine_id, scheduled_for, status, completed_at)
                   values (%s, %s, %s, %s, %s, %s)
                   on conflict (routine_id, scheduled_for) do nothing""",
                (
                    occ.id,
                    occ.user_id,
                    occ.routine_id,
                    local_day,
                    occ.status.value,
                    occ.completed_at,
                ),
            )
            created += cur.rowcount
        return created

    @pg_guard
    def list_occurrences(
        self, user_id: UUID, routine_id: UUID, flt: OccurrenceFilter, limit: int, offset: int
    ) -> tuple[list[OccurrenceRead], int]:
        where, params = ["o.user_id = %s", "o.routine_id = %s"], [user_id, routine_id]
        if flt.status is not None:
            where.append("o.status = %s")
            params.append(flt.status.value)
        rule_row = self._conn.execute(
            "select recurrence_rule from public.routines where id = %s and user_id = %s",
            (routine_id, user_id),
        ).fetchone()
        if rule_row is None:
            return [], 0
        tz = ZoneInfo(RecurrenceRule.model_validate(rule_row["recurrence_rule"]).timezone)
        # Datas locais com folga de um dia; o corte exato é feito sobre o instante reconstruído.
        if flt.scheduled_from is not None:
            where.append("o.scheduled_for >= %s")
            params.append(flt.scheduled_from.astimezone(tz).date() - timedelta(days=1))
        if flt.scheduled_to is not None:
            where.append("o.scheduled_for <= %s")
            params.append(flt.scheduled_to.astimezone(tz).date() + timedelta(days=1))
        rows = self._conn.execute(
            f"{_OCCURRENCE_SELECT} where {' and '.join(where)} order by o.scheduled_for, o.id",
            params,
        ).fetchall()
        items = [_occurrence(r) for r in rows]
        if flt.scheduled_from is not None:
            items = [o for o in items if o.scheduled_for >= flt.scheduled_from]
        if flt.scheduled_to is not None:
            items = [o for o in items if o.scheduled_for < flt.scheduled_to]
        return items[offset : offset + limit], len(items)

    @pg_guard
    def get_occurrence(
        self, user_id: UUID, routine_id: UUID, occurrence_id: UUID
    ) -> OccurrenceRead | None:
        row = self._conn.execute(
            f"{_OCCURRENCE_SELECT} where o.id = %s and o.routine_id = %s and o.user_id = %s",
            (occurrence_id, routine_id, user_id),
        ).fetchone()
        return _occurrence(row) if row else None

    @pg_guard
    def update_occurrence(self, occurrence: OccurrenceRead, audit: AuditEntry) -> None:
        cur = self._conn.execute(
            """update public.routine_occurrences set status = %s, completed_at = %s
               where id = %s and routine_id = %s and user_id = %s""",
            (
                occurrence.status.value,
                occurrence.completed_at,
                occurrence.id,
                occurrence.routine_id,
                occurrence.user_id,
            ),
        )
        if cur.rowcount != 1:
            raise RepositoryError("occurrence update affected no row")
        insert_audit(self._conn, audit)
