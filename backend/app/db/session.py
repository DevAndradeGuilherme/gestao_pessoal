"""Per-request PostgreSQL transaction with database-enforced user isolation."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection, sql
from psycopg.rows import dict_row

from app.auth.models import CurrentUser


class DatabaseNotConfiguredError(RuntimeError):
    """`DATABASE_URL` ausente: a API deve falhar fechada (503) em vez de simular persistência."""


@contextmanager
def user_transaction(user: CurrentUser) -> Iterator[Connection]:
    """Use only after JWT/webhook identity validation; never accept a client user_id.

    A privileged login may connect, but every statement runs as app_backend with RLS.
    Transaction-local claims prevent identity leakage through pooled connections.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise DatabaseNotConfiguredError("DATABASE_URL is not configured")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.transaction():
            # Um único round-trip; o UUID validado entra como literal escapado pelo driver.
            conn.execute(
                sql.SQL(
                    "set local role app_backend; "
                    "select set_config('request.jwt.claim.sub', {}, true)"
                ).format(sql.Literal(str(user.id)))
            )
            yield conn
