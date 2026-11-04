"""Utilitários comuns: tradução de erros do driver, auditoria e idempotência em PostgreSQL."""

import json
from collections.abc import Callable
from functools import wraps
from typing import Any
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.types.json import Jsonb

from app.modules.common.audit import AuditEntry
from app.modules.common.errors import RepositoryError
from app.modules.common.idempotency import IdempotencyRecord

__all__ = ["PgAudit", "PgIdempotency", "insert_audit", "pg_guard"]


def pg_guard[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Converte erros do driver em `RepositoryError` (vira 503 sem vazar detalhes do driver)."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> R:
        try:
            return fn(*args, **kwargs)
        except psycopg.Error as exc:
            raise RepositoryError(type(exc).__name__) from exc

    return wrapper  # type: ignore[return-value]


def _dumps(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


def insert_audit(conn: Connection, audit: AuditEntry) -> None:
    """Grava a auditoria na mesma transação (e conexão) da mutação."""
    conn.execute(
        """insert into public.activity_log
               (id, user_id, entity_type, entity_id, action, details, created_at)
           values (%s, %s, %s, %s, %s, %s, %s)""",
        (
            audit.id,
            audit.user_id,
            audit.entity_type,
            audit.entity_id,
            audit.action,
            Jsonb({"channel": audit.channel, "changes": audit.changes}, dumps=_dumps),
            audit.created_at,
        ),
    )


class PgAudit:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    @pg_guard
    def list_for_entity(self, user_id: UUID, entity_type: str, entity_id: UUID) -> list[AuditEntry]:
        rows = self._conn.execute(
            """select id, user_id, entity_type, entity_id, action, details, created_at
               from public.activity_log
               where user_id = %s and entity_type = %s and entity_id = %s
               order by created_at, id""",
            (user_id, entity_type, entity_id),
        ).fetchall()
        return [
            AuditEntry(
                id=r["id"],
                user_id=r["user_id"],
                entity_type=r["entity_type"],
                entity_id=r["entity_id"],
                action=r["action"],
                channel=(r["details"] or {}).get("channel", ""),
                changes=(r["details"] or {}).get("changes", {}),
                created_at=r["created_at"],
            )
            for r in rows
        ]


class PgIdempotency:
    """`public.idempotency_keys` na transação da requisição.

    `get` toma um advisory lock transacional por (usuário, chave): requisições concorrentes com a
    mesma chave se serializam até o commit da primeira, que então é reproduzida pela segunda
    (a mutação e o registro da chave são confirmados juntos).
    """

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    @pg_guard
    def get(self, user_id: UUID, key: str) -> IdempotencyRecord | None:
        self._conn.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"idem:{user_id}:{key}",)
        )
        row = self._conn.execute(
            """select request_hash, response_body, created_at from public.idempotency_keys
               where user_id = %s and key = %s and status = 'completed'""",
            (user_id, key),
        ).fetchone()
        if row is None:
            return None
        return IdempotencyRecord(
            user_id=user_id,
            key=key,
            request_hash=row["request_hash"],
            response=row["response_body"],
            created_at=row["created_at"],
        )

    @pg_guard
    def save(self, record: IdempotencyRecord) -> bool:
        row = self._conn.execute(
            """insert into public.idempotency_keys
                   (user_id, key, request_hash, status, response_status, response_body,
                    created_at, completed_at)
               values (%s, %s, %s, 'completed', 200, %s, %s, %s)
               on conflict do nothing returning key""",
            (
                record.user_id,
                record.key,
                record.request_hash,
                Jsonb(record.response, dumps=_dumps),
                record.created_at,
                record.created_at,
            ),
        ).fetchone()
        return row is not None
