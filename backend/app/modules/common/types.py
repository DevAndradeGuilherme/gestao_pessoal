"""Tipos Pydantic reutilizáveis nos schemas de domínio."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, StringConstraints


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


# Entrada exige offset (ISO 8601); valor normalizado para UTC (serializa com `Z`).
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]

Clock = Callable[[], datetime]

# Tolerância para `completed_at` informado pelo cliente (relógios dessincronizados).
CLOCK_SKEW = timedelta(minutes=5)

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
