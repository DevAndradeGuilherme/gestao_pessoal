"""`Idempotency-Key` (docs/CONTRATOS.md §4).

Mesma chave + mesmo payload => mesma resposta, sem nova mutação.
Mesma chave + payload diferente => 409 `idempotency_conflict`.
O armazenamento real é definido por GP-03; aqui só existe a interface e um fake em memória.
"""

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel

from app.auth.models import CurrentUser
from app.core.errors import AppError, ErrorCode

MAX_KEY_LENGTH = 128


class NoPayload(BaseModel):
    """Payload vazio para ações sem corpo (reopen, cancel...)."""


class IdempotencyRecord(BaseModel):
    user_id: UUID
    key: str
    request_hash: str
    response: dict[str, Any]
    created_at: datetime


class IdempotencyStore(Protocol):
    def get(self, user_id: UUID, key: str) -> IdempotencyRecord | None: ...

    def save(self, record: IdempotencyRecord) -> bool:
        """Grava se a chave ainda não existe para o usuário. `False` se já existia."""
        ...


def request_hash(scope: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps({"scope": scope, "payload": payload}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def run_idempotent[T: BaseModel](
    store: IdempotencyStore,
    user: CurrentUser,
    key: str | None,
    scope: str,
    payload: dict[str, Any],
    model: type[T],
    now: datetime,
    action: Callable[[], T],
) -> T:
    """Executa `action` no máximo uma vez por (usuário, chave); só sucessos são memorizados."""
    if key is None:
        return action()
    if not key.strip() or len(key) > MAX_KEY_LENGTH:
        raise AppError(
            422, ErrorCode.VALIDATION_ERROR, "Idempotency-Key deve ter de 1 a 128 caracteres."
        )
    digest = request_hash(scope, payload)
    existing = store.get(user.id, key)
    if existing is not None:
        if existing.request_hash != digest:
            raise AppError(
                409,
                ErrorCode.IDEMPOTENCY_CONFLICT,
                "Idempotency-Key já utilizada com um payload diferente.",
            )
        return model.model_validate(existing.response)
    result = action()
    store.save(
        IdempotencyRecord(
            user_id=user.id,
            key=key,
            request_hash=digest,
            response=result.model_dump(mode="json"),
            created_at=now,
        )
    )
    return result
