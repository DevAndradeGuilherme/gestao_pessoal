"""Auditoria de mudanças relevantes (`activity_log`, CONTEXTO §5)."""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.auth.models import CurrentUser


class AuditEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    channel: str
    changes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AuditRepository(Protocol):
    def list_for_entity(
        self, user_id: UUID, entity_type: str, entity_id: UUID
    ) -> list[AuditEntry]: ...


def build_audit(
    user: CurrentUser,
    entity_type: str,
    entity_id: UUID,
    action: str,
    now: datetime,
    *,
    before: BaseModel | None = None,
    after: BaseModel | None = None,
    fields: tuple[str, ...] = (),
    extra: dict[str, Any] | None = None,
) -> AuditEntry:
    """Monta a entrada de auditoria. `changes` guarda `{campo: {"from": x, "to": y}}`."""
    changes: dict[str, Any] = {}
    if after is not None:
        new = after.model_dump(mode="json")
        old = before.model_dump(mode="json") if before is not None else {}
        for name in fields:
            if old.get(name) != new.get(name):
                changes[name] = {"from": old.get(name), "to": new.get(name)}
    if extra:
        changes.update(extra)
    return AuditEntry(
        user_id=user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        channel=user.channel,
        changes=changes,
        created_at=now,
    )
