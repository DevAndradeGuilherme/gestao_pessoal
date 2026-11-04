"""Fakes em memória das interfaces de armazenamento comuns (testes e desenvolvimento).

Não são usados na aplicação real: sem GP-03 a API responde 503 (ver `deps.get_stores`).
"""

from uuid import UUID

from app.modules.common.audit import AuditEntry
from app.modules.common.idempotency import IdempotencyRecord


class InMemoryAudit:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def list_for_entity(self, user_id: UUID, entity_type: str, entity_id: UUID) -> list[AuditEntry]:
        return [
            e
            for e in self.entries
            if e.user_id == user_id and e.entity_type == entity_type and e.entity_id == entity_id
        ]


class InMemoryIdempotency:
    def __init__(self) -> None:
        self.records: dict[tuple[UUID, str], IdempotencyRecord] = {}

    def get(self, user_id: UUID, key: str) -> IdempotencyRecord | None:
        return self.records.get((user_id, key))

    def save(self, record: IdempotencyRecord) -> bool:
        k = (record.user_id, record.key)
        if k in self.records:
            return False
        self.records[k] = record
        return True
