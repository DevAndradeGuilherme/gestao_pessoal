"""Per-request PostgreSQL transaction with database-enforced user isolation."""

import atexit
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection, sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.auth.models import CurrentUser


class DatabaseNotConfiguredError(RuntimeError):
    """`DATABASE_URL` ausente: a API deve falhar fechada (503) em vez de simular persistência."""


# Abrir conexão com o Supabase custa ~3 RTTs (TCP + TLS + autenticação; ~0,8 s a 265 ms de RTT).
# O pool a reaproveita; o isolamento não depende dela (papel e claim são `SET LOCAL` por transação).
_pools: dict[str, ConnectionPool] = {}
_lock = threading.Lock()


def _pool(dsn: str) -> ConnectionPool:
    with _lock:
        pool = _pools.get(dsn)
        if pool is None:
            pool = ConnectionPool(
                dsn,
                min_size=1,
                max_size=int(os.environ.get("DATABASE_POOL_MAX", "5")),
                timeout=10,
                max_idle=240,
                check=ConnectionPool.check_connection,
                kwargs={"row_factory": dict_row},
                open=False,
            )
            pool.open()
            _pools[dsn] = pool
        return pool


def close_pools() -> None:
    with _lock:
        for pool in _pools.values():
            pool.close()
        _pools.clear()


atexit.register(close_pools)


@contextmanager
def user_transaction(user: CurrentUser) -> Iterator[Connection]:
    """Use only after JWT/webhook identity validation; never accept a client user_id.

    A privileged login may connect, but every statement runs as app_backend with RLS.
    Transaction-local claims prevent identity leakage through pooled connections.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise DatabaseNotConfiguredError("DATABASE_URL is not configured")
    with _pool(dsn).connection() as conn:
        with conn.transaction():
            # Um único round-trip; o UUID validado entra como literal escapado pelo driver.
            conn.execute(
                sql.SQL(
                    "set local role app_backend; "
                    "select set_config('request.jwt.claim.sub', {}, true)"
                ).format(sql.Literal(str(user.id)))
            )
            yield conn
