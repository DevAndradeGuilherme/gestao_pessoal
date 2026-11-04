"""Per-request PostgreSQL transaction with database-enforced user isolation."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from app.auth.models import CurrentUser


@contextmanager
def user_transaction(user: CurrentUser) -> Iterator[Connection]:
    """Use only after JWT/webhook identity validation; never accept a client user_id.

    A privileged login may connect, but every statement runs as app_backend with RLS.
    Transaction-local claims prevent identity leakage through pooled connections.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not configured")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("set local role app_backend")
            conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(user.id),))
            yield conn
