"""Contratos de entrada e saída de compromissos (`snake_case`, instantes em UTC)."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.common.types import Title, UtcDatetime, blank_to_none


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class SyncStatus(StrEnum):
    """Proposta de CONTRATOS §7; GP-03 confirma. Google OAuth/sync é feito em GP-06."""

    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


def _check_range(starts_at, ends_at):  # noqa: ANN001, ANN202
    if ends_at is not None and ends_at <= starts_at:
        raise ValueError("ends_at deve ser posterior a starts_at.")


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    starts_at: UtcDatetime
    ends_at: UtcDatetime | None = None  # opcional; nenhuma duração é presumida
    description: str | None = Field(None, max_length=5000)
    location: str | None = Field(None, max_length=500)

    _blank = field_validator("description", "location")(blank_to_none)

    @model_validator(mode="after")
    def _range(self) -> "AppointmentCreate":
        _check_range(self.starts_at, self.ends_at)
        return self


class AppointmentUpdate(BaseModel):
    """PATCH: ausente = não alterar; `null` limpa description/location. Horários: use reschedule."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: str | None = Field(None, max_length=5000)
    location: str | None = Field(None, max_length=500)

    _blank = field_validator("description", "location")(blank_to_none)

    @model_validator(mode="after")
    def _title_not_null(self) -> "AppointmentUpdate":
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title não pode ser nulo.")
        return self


class AppointmentReschedule(BaseModel):
    """`ends_at` ausente/nulo limpa o fim anterior: o domínio nunca presume duração."""

    model_config = ConfigDict(extra="forbid")

    starts_at: UtcDatetime
    ends_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _range(self) -> "AppointmentReschedule":
        _check_range(self.starts_at, self.ends_at)
        return self


class AppointmentCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(None, max_length=500)

    _blank = field_validator("reason")(blank_to_none)


class AppointmentRead(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    starts_at: UtcDatetime
    ends_at: UtcDatetime | None = None
    description: str | None = None
    location: str | None = None
    status: AppointmentStatus
    google_event_id: str | None = None
    google_calendar_id: str | None = None
    sync_status: SyncStatus
    created_at: UtcDatetime
    updated_at: UtcDatetime
