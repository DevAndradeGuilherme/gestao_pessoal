"""Contratos de entrada e saída de tarefas."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.common.types import Title, UtcDatetime, blank_to_none


class TaskStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    """Valores propostos (CONTEXTO §2.3 não os enumera); GP-03 confirma no schema."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: str | None = Field(None, max_length=5000)
    due_at: UtcDatetime | None = None
    priority: TaskPriority | None = None
    category: str | None = Field(None, max_length=100)
    # Intenção de domínio: a sincronização efetiva é feita por GP-06, nunca inferida de due_at.
    sync_to_calendar: bool = False

    _blank = field_validator("description", "category")(blank_to_none)


class TaskUpdate(BaseModel):
    """PATCH: ausente = não alterar; `null` limpa os campos anuláveis."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: str | None = Field(None, max_length=5000)
    due_at: UtcDatetime | None = None
    priority: TaskPriority | None = None
    category: str | None = Field(None, max_length=100)
    sync_to_calendar: bool | None = None

    _blank = field_validator("description", "category")(blank_to_none)

    @model_validator(mode="after")
    def _not_nullable(self) -> "TaskUpdate":
        for name in ("title", "sync_to_calendar"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} não pode ser nulo.")
        return self


class TaskComplete(BaseModel):
    """`completed_at` opcional (ex.: "concluí ontem às 18h"); padrão: instante do comando."""

    model_config = ConfigDict(extra="forbid")

    completed_at: UtcDatetime | None = None


class TaskRead(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: str | None = None
    due_at: UtcDatetime | None = None
    priority: TaskPriority | None = None
    category: str | None = None
    status: TaskStatus
    completed_at: UtcDatetime | None = None
    sync_to_calendar: bool
    google_event_id: str | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime
