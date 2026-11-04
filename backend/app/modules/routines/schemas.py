"""Contratos de entrada e saída de rotinas e ocorrências."""

from datetime import timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.modules.common.types import Title, UtcDatetime
from app.modules.routines.recurrence import RecurrenceRule

MAX_GENERATION_WINDOW = timedelta(days=366)


class OccurrenceStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"  # usuário sinalizou que não realizou


class RoutineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    recurrence_rule: RecurrenceRule


class RoutineUpdate(BaseModel):
    """PATCH: ausente = não alterar. `recurrence_rule` substitui a regra inteira."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    recurrence_rule: RecurrenceRule | None = None

    @model_validator(mode="after")
    def _not_null(self) -> "RoutineUpdate":
        for name in ("title", "recurrence_rule"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} não pode ser nulo.")
        return self


class RoutineRead(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    recurrence_rule: RecurrenceRule
    active: bool
    created_at: UtcDatetime
    updated_at: UtcDatetime


class OccurrenceWindow(BaseModel):
    """Janela `[window_start, window_end)` para materializar ocorrências (máx. 366 dias)."""

    model_config = ConfigDict(extra="forbid")

    window_start: UtcDatetime
    window_end: UtcDatetime

    @model_validator(mode="after")
    def _range(self) -> "OccurrenceWindow":
        if self.window_end <= self.window_start:
            raise ValueError("window_end deve ser posterior a window_start.")
        if self.window_end - self.window_start > MAX_GENERATION_WINDOW:
            raise ValueError("A janela não pode exceder 366 dias.")
        return self


class OccurrenceComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_at: UtcDatetime | None = None


class OccurrenceRead(BaseModel):
    id: UUID
    routine_id: UUID
    user_id: UUID
    scheduled_for: UtcDatetime
    status: OccurrenceStatus
    completed_at: UtcDatetime | None = None


class OccurrenceGeneration(BaseModel):
    created: int
    occurrences: list[OccurrenceRead]
