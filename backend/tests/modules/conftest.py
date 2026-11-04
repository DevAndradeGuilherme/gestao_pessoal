from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import CurrentUser
from app.modules.appointments.repository import InMemoryAppointmentRepository
from app.modules.common.deps import Stores, get_clock, get_stores
from app.modules.common.memory import InMemoryAudit, InMemoryIdempotency
from app.modules.routines.repository import InMemoryRoutineRepository
from app.modules.tasks.repository import InMemoryTaskRepository

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@dataclass
class Api:
    client: TestClient
    app: FastAPI
    stores: Stores
    audit: InMemoryAudit
    clock: FakeClock
    user: CurrentUser

    def as_user(self, user: CurrentUser) -> None:
        self.user = user

    def audit_actions(self, entity_id: str) -> list[str]:
        return [e.action for e in self.audit.entries if str(e.entity_id) == entity_id]


def make_user(channel: str = "web") -> CurrentUser:
    return CurrentUser(id=uuid4(), channel=channel)  # type: ignore[arg-type]


@pytest.fixture
def user_a() -> CurrentUser:
    return make_user()


@pytest.fixture
def user_b() -> CurrentUser:
    return make_user()


@pytest.fixture
def make_api(app: FastAPI, user_a: CurrentUser):
    """Fábrica permitindo trocar os `Stores` (ex.: repositório com falha)."""

    def factory(stores: Stores | None = None, audit: InMemoryAudit | None = None) -> Api:
        audit = audit or InMemoryAudit()
        stores = stores or Stores(
            appointments=InMemoryAppointmentRepository(audit),
            tasks=InMemoryTaskRepository(audit),
            routines=InMemoryRoutineRepository(audit),
            audit=audit,
            idempotency=InMemoryIdempotency(),
        )
        clock = FakeClock()
        api = Api(TestClient(app, raise_server_exceptions=False), app, stores, audit, clock, user_a)
        app.dependency_overrides[get_stores] = lambda: stores
        app.dependency_overrides[get_clock] = lambda: clock
        app.dependency_overrides[get_current_user] = lambda: api.user
        return api

    return factory


@pytest.fixture
def api(make_api) -> Api:
    return make_api()


def uuid_str() -> str:
    return str(UUID(int=0x1234))
