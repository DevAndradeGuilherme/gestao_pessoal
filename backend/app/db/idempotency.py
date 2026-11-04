"""Atomic request deduplication for domain services."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from psycopg import Connection

from app.auth.models import CurrentUser
from app.core.errors import AppError, ErrorCode


@dataclass(frozen=True)
class StoredResponse:
    status: int
    body: Any
    replayed: bool


def request_hash(method: str, path: str, payload: Any) -> str:
    """Hash a normalized operation, including route, to detect key misuse."""
    canonical = json.dumps(
        [method.upper(), path, payload], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def execute_once(
    conn: Connection,
    *,
    user: CurrentUser,
    key: str,
    digest: str,
    operation: Callable[[Connection], tuple[int, Any]],
) -> StoredResponse:
    """Call inside user_transaction; operation and saved response commit together.

    PostgreSQL's unique key serializes concurrent attempts. The loser waits for the
    first transaction and then replays or returns 409 for a different payload.
    """
    if not 1 <= len(key) <= 128 or len(digest) != 64:
        raise ValueError("Invalid idempotency key or digest")
    user_id = str(user.id)
    inserted = conn.execute(
        """insert into public.idempotency_keys(user_id, key, request_hash)
           values (%s, %s, %s) on conflict do nothing returning key""",
        (user_id, key, digest),
    ).fetchone()
    if not inserted:
        row = conn.execute(
            """select request_hash, status, response_status, response_body
               from public.idempotency_keys where user_id = %s and key = %s for update""",
            (user_id, key),
        ).fetchone()
        if row is None or row["request_hash"] != digest:
            raise AppError(
                409, ErrorCode.IDEMPOTENCY_CONFLICT, "Chave de idempotência reutilizada."
            )
        if row["status"] != "completed":
            raise AppError(409, ErrorCode.CONFLICT, "Operação com esta chave ainda em andamento.")
        return StoredResponse(row["response_status"], row["response_body"], True)
    status, body = operation(conn)
    if not 200 <= status <= 299:
        raise ValueError("Only successful responses can be stored")
    conn.execute(
        """update public.idempotency_keys set status = 'completed',
           response_status = %s, response_body = %s::jsonb, completed_at = now()
           where user_id = %s and key = %s""",
        (status, json.dumps(body), user_id, key),
    )
    return StoredResponse(status, body, False)
