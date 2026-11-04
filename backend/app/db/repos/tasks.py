"""Tarefas em PostgreSQL (`public.tasks`)."""

from uuid import UUID

from psycopg import Connection

from app.db.repos.common import insert_audit, pg_guard
from app.modules.common.audit import AuditEntry
from app.modules.common.errors import RepositoryError
from app.modules.tasks.repository import TaskFilter
from app.modules.tasks.schemas import TaskRead

_COLUMNS = (
    "id, user_id, title, description, due_at, priority, category, status, completed_at, "
    "sync_to_calendar, google_event_id, created_at, updated_at"
)


class PgTaskRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    @pg_guard
    def add(self, task: TaskRead, audit: AuditEntry) -> None:
        # `sync_status` não faz parte do contrato de domínio: sem opt-in explícito vale
        # `not_applicable`; com opt-in a sincronização (GP-06) ainda está pendente.
        self._conn.execute(
            f"""insert into public.tasks ({_COLUMNS}, sync_status)
                values (%(id)s, %(user_id)s, %(title)s, %(description)s, %(due_at)s,
                        %(priority)s, %(category)s, %(status)s, %(completed_at)s,
                        %(sync_to_calendar)s, %(google_event_id)s, %(created_at)s,
                        %(updated_at)s,
                        case when %(sync_to_calendar)s then 'pending' else 'not_applicable' end)""",
            task.model_dump(),
        )
        insert_audit(self._conn, audit)

    @pg_guard
    def get(self, user_id: UUID, task_id: UUID) -> TaskRead | None:
        row = self._conn.execute(
            f"select {_COLUMNS} from public.tasks where id = %s and user_id = %s",
            (task_id, user_id),
        ).fetchone()
        return TaskRead.model_validate(row) if row else None

    @pg_guard
    def list(
        self, user_id: UUID, flt: TaskFilter, limit: int, offset: int
    ) -> tuple[list[TaskRead], int]:
        where, params = ["user_id = %s"], [user_id]
        if flt.status is not None:
            where.append("status = %s")
            params.append(flt.status.value)
        if flt.priority is not None:
            where.append("priority = %s")
            params.append(flt.priority.value)
        if flt.category is not None:
            where.append("category = %s")
            params.append(flt.category)
        if flt.due_from is not None:
            where.append("due_at >= %s")
            params.append(flt.due_from)
        if flt.due_to is not None:
            where.append("due_at < %s")
            params.append(flt.due_to)
        if flt.overdue_before is not None:
            where.append("status = 'pending' and due_at < %s")
            params.append(flt.overdue_before)
        clause = " and ".join(where)
        total = self._conn.execute(
            f"select count(*) as n from public.tasks where {clause}",
            params,
        ).fetchone()["n"]
        rows = self._conn.execute(
            f"select {_COLUMNS} from public.tasks where {clause} "
            "order by due_at asc nulls last, created_at, id limit %s offset %s",
            [*params, limit, offset],
        ).fetchall()
        return [TaskRead.model_validate(r) for r in rows], total

    @pg_guard
    def update(self, task: TaskRead, audit: AuditEntry) -> None:
        cur = self._conn.execute(
            """update public.tasks set title = %(title)s, description = %(description)s,
                   due_at = %(due_at)s, priority = %(priority)s, category = %(category)s,
                   status = %(status)s, completed_at = %(completed_at)s,
                   sync_to_calendar = %(sync_to_calendar)s,
                   sync_status = case
                       when not %(sync_to_calendar)s then 'not_applicable'
                       when sync_status = 'not_applicable' then 'pending'
                       else sync_status end,
                   updated_at = %(updated_at)s
               where id = %(id)s and user_id = %(user_id)s""",
            task.model_dump(),
        )
        if cur.rowcount != 1:
            raise RepositoryError("task update affected no row")
        insert_audit(self._conn, audit)
