"""Regra de recorrência flexível e geração (pura) de ocorrências — proposta para ADR-003.

Esta camada é **determinística e sem I/O**: dada uma regra e uma janela, devolve os instantes
(UTC) esperados. A execução assíncrona periódica (Celery, GP-09) só chama estas funções.

Formato (JSON em `routines.recurrence_rule`):

    {"frequency": "weekly", "interval": 1, "by_weekday": ["mon", "tue"],
     "time": "19:00", "timezone": "America/Sao_Paulo",
     "start_date": "2026-11-03", "end_date": null, "count": null}

- `frequency`: `daily` | `weekly` | `monthly`; `interval` = a cada N dias/semanas/meses,
  contados a partir de `start_date` (semanas começam na segunda-feira).
- `weekly` exige `by_weekday`; `monthly` exige `by_month_day` (1..31 ou -1 = último dia do mês).
  Dia positivo inexistente no mês (ex.: 31 em abril) é **pulado** naquele mês (como RFC 5545).
- `time` é horário de relógio local (sem segundos) no `timezone` IANA da regra. Em lacuna de
  horário de verão a ocorrência cai no instante resultante do offset anterior; em horário
  repetido vale a primeira ocorrência (`fold=0`).
- `end_date` (inclusiva) e `count` (total de ocorrências desde `start_date`) são opcionais.
"""

import calendar
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from enum import StrEnum
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_WEEKDAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
LAST_DAY = -1


class Frequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class RecurrenceRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frequency: Frequency
    interval: int = Field(1, ge=1, le=365)
    by_weekday: list[Weekday] | None = None
    by_month_day: list[int] | None = None
    time: dtime
    timezone: str
    start_date: date
    end_date: date | None = None
    count: int | None = Field(None, ge=1, le=10000)

    @field_validator("time")
    @classmethod
    def _naive_minutes(cls, value: dtime) -> dtime:
        if value.tzinfo is not None:
            raise ValueError("time deve ser horário local, sem offset.")
        if value.second or value.microsecond:
            raise ValueError("time deve ter precisão de minutos (HH:MM).")
        return value

    @field_validator("timezone")
    @classmethod
    def _iana(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError("timezone deve ser um identificador IANA válido.") from exc
        return value

    @model_validator(mode="after")
    def _consistency(self) -> "RecurrenceRule":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date não pode ser anterior a start_date.")
        weekly, monthly = self.frequency == Frequency.WEEKLY, self.frequency == Frequency.MONTHLY
        if weekly:
            if not self.by_weekday:
                raise ValueError("by_weekday é obrigatório para frequência semanal.")
            if len(set(self.by_weekday)) != len(self.by_weekday):
                raise ValueError("by_weekday não pode ter dias repetidos.")
        elif self.by_weekday is not None:
            raise ValueError("by_weekday só se aplica à frequência semanal.")
        if monthly:
            if not self.by_month_day:
                raise ValueError("by_month_day é obrigatório para frequência mensal.")
            if len(set(self.by_month_day)) != len(self.by_month_day):
                raise ValueError("by_month_day não pode ter dias repetidos.")
            if any(not (1 <= d <= 31 or d == LAST_DAY) for d in self.by_month_day):
                raise ValueError("by_month_day aceita 1..31 ou -1 (último dia do mês).")
        elif self.by_month_day is not None:
            raise ValueError("by_month_day só se aplica à frequência mensal.")
        return self


def _matches(rule: RecurrenceRule, day: date) -> bool:
    """A data (local) pertence ao padrão? Ignora `count` e `end_date`."""
    if day < rule.start_date:
        return False
    if rule.frequency == Frequency.DAILY:
        return (day - rule.start_date).days % rule.interval == 0
    if rule.frequency == Frequency.WEEKLY:
        monday = day - timedelta(days=day.weekday())
        start_monday = rule.start_date - timedelta(days=rule.start_date.weekday())
        weeks = (monday - start_monday).days // 7
        return weeks % rule.interval == 0 and day.weekday() in {
            _WEEKDAY_INDEX[w] for w in rule.by_weekday or []
        }
    months = (day.year - rule.start_date.year) * 12 + day.month - rule.start_date.month
    if months % rule.interval != 0:
        return False
    last = calendar.monthrange(day.year, day.month)[1]
    return any(day.day == (last if d == LAST_DAY else d) for d in rule.by_month_day or [])


def generate_occurrences(
    rule: RecurrenceRule, window_start: datetime, window_end: datetime
) -> list[datetime]:
    """Instantes UTC das ocorrências em `[window_start, window_end)`, em ordem crescente."""
    if window_start.tzinfo is None or window_end.tzinfo is None:
        raise ValueError("A janela deve usar datetimes com offset.")
    if window_end <= window_start:
        return []
    tz = ZoneInfo(rule.timezone)
    window_first = window_start.astimezone(tz).date() - timedelta(days=1)
    last = window_end.astimezone(tz).date() + timedelta(days=1)
    if rule.end_date is not None:
        last = min(last, rule.end_date)
    # Com `count` é preciso contar desde o início da série.
    day = rule.start_date if rule.count else max(rule.start_date, window_first)
    result: list[datetime] = []
    seen = 0
    while day <= last:
        if _matches(rule, day):
            seen += 1
            if rule.count and seen > rule.count:
                break
            instant = datetime.combine(day, rule.time, tzinfo=tz).astimezone(UTC)
            if window_start <= instant < window_end:
                result.append(instant)
        day += timedelta(days=1)
    return result
