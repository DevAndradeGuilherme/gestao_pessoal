"""Compromissos em PostgreSQL (`public.appointments`)."""

from uuid import UUID

from psycopg import Connection

from app.db.repos.common import insert_audit, pg_guard
from app.modules.appointments.repository import AppointmentFilter
from app.modules.appointments.schemas import AppointmentRead
from app.modules.common.audit import AuditEntry
from app.modules.common.errors import RepositoryError

_COLUMNS = (
    "id, user_id, title, starts_at, ends_at, description, location, status, "
    "google_event_id, google_calendar_id, sync_status, created_at, updated_at"
)


class PgAppointmentRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    @pg_guard
    def add(self, appointment: AppointmentRead, audit: AuditEntry) -> None:
        self._conn.execute(
            f"""insert into public.appointments ({_COLUMNS})
                values (%(id)s, %(user_id)s, %(title)s, %(starts_at)s, %(ends_at)s,
                        %(description)s, %(location)s, %(status)s, %(google_event_id)s,
                        %(google_calendar_id)s, %(sync_status)s, %(created_at)s, %(updated_at)s)""",
            appointment.model_dump(),
        )
        insert_audit(self._conn, audit)

    @pg_guard
    def get(self, user_id: UUID, appointment_id: UUID) -> AppointmentRead | None:
        row = self._conn.execute(
            f"select {_COLUMNS} from public.appointments where id = %s and user_id = %s",
            (appointment_id, user_id),
        ).fetchone()
        return AppointmentRead.model_validate(row) if row else None

    @pg_guard
    def list(
        self, user_id: UUID, flt: AppointmentFilter, limit: int, offset: int
    ) -> tuple[list[AppointmentRead], int]:
        where, params = ["user_id = %s"], [user_id]
        if flt.starts_from is not None:
            where.append("starts_at >= %s")
            params.append(flt.starts_from)
        if flt.starts_to is not None:
            where.append("starts_at < %s")
            params.append(flt.starts_to)
        if flt.status is not None:
            where.append("status = %s")
            params.append(flt.status.value)
        clause = " and ".join(where)
        total = self._conn.execute(
            f"select count(*) as n from public.appointments where {clause}",
            params,
        ).fetchone()["n"]
        rows = self._conn.execute(
            f"select {_COLUMNS} from public.appointments where {clause} "
            "order by starts_at, id limit %s offset %s",
            [*params, limit, offset],
        ).fetchall()
        return [AppointmentRead.model_validate(r) for r in rows], total

    @pg_guard
    def update(self, appointment: AppointmentRead, audit: AuditEntry) -> None:
        cur = self._conn.execute(
            """update public.appointments set title = %(title)s, description = %(description)s,
                   location = %(location)s, starts_at = %(starts_at)s, ends_at = %(ends_at)s,
                   status = %(status)s, sync_status = %(sync_status)s,
                   updated_at = %(updated_at)s
               where id = %(id)s and user_id = %(user_id)s""",
            appointment.model_dump(),
        )
        if cur.rowcount != 1:
            raise RepositoryError("appointment update affected no row")
        insert_audit(self._conn, audit)
