from uuid import uuid4

import pytest

from app.modules.appointments.repository import InMemoryAppointmentRepository
from app.modules.common.deps import Stores
from app.modules.common.errors import RepositoryError
from app.modules.common.memory import InMemoryAudit, InMemoryIdempotency
from app.modules.routines.repository import InMemoryRoutineRepository
from app.modules.tasks.repository import InMemoryTaskRepository

APPT = "/api/v1/appointments"
TASK = "/api/v1/tasks"
ROUTINE = "/api/v1/routines"
BODY = {"title": "Reunião com Ana", "starts_at": "2026-11-04T14:00:00-03:00"}


def key(value: str = "k1") -> dict[str, str]:
    return {"Idempotency-Key": value}


# -- idempotência --------------------------------------------------------------------------


def test_same_key_same_payload_replays_without_new_mutation(api):
    first = api.client.post(APPT, json=BODY, headers=key())
    second = api.client.post(APPT, json=BODY, headers=key())
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert api.client.get(APPT).json()["total"] == 1
    assert api.audit_actions(first.json()["id"]) == ["appointment.created"]


def test_same_key_different_payload_conflicts(api):
    api.client.post(APPT, json=BODY, headers=key())
    r = api.client.post(APPT, json={**BODY, "title": "Outra"}, headers=key())
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "idempotency_conflict"
    assert api.client.get(APPT).json()["total"] == 1


def test_same_key_on_different_operation_conflicts(api):
    created = api.client.post(APPT, json=BODY, headers=key()).json()
    r = api.client.post(f"{APPT}/{created['id']}/cancel", headers=key())
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_conflict"


def test_keys_are_scoped_per_user(api, user_b):
    mine = api.client.post(APPT, json=BODY, headers=key()).json()
    api.as_user(user_b)
    theirs = api.client.post(APPT, json={**BODY, "title": "Outra"}, headers=key())
    assert theirs.status_code == 201 and theirs.json()["id"] != mine["id"]


def test_without_key_each_post_creates(api):
    api.client.post(APPT, json=BODY)
    api.client.post(APPT, json=BODY)
    assert api.client.get(APPT).json()["total"] == 2


def test_invalid_key_length_rejected(api):
    assert api.client.post(APPT, json=BODY, headers=key("x" * 129)).status_code == 422
    assert api.client.post(APPT, json=BODY, headers=key("x" * 128)).status_code == 201
    assert api.client.post(APPT, json=BODY, headers=key(" ")).status_code == 422


def test_failed_request_does_not_consume_key(api):
    invalid = api.client.post(APPT, json={"title": ""}, headers=key())
    assert invalid.status_code == 422
    assert api.client.post(APPT, json=BODY, headers=key()).status_code == 201


def test_business_error_is_not_memorized(api):
    task = api.client.post(TASK, json={"title": "t"}).json()
    api.client.post(f"{TASK}/{task['id']}/cancel")
    assert api.client.post(f"{TASK}/{task['id']}/complete", headers=key()).status_code == 409
    api.client.post(f"{TASK}/{task['id']}/reopen")  # continua cancelada
    assert api.client.post(f"{TASK}/{task['id']}/complete", headers=key()).status_code == 409


def test_whatsapp_channel_replay_and_audit_channel(api):
    from tests.modules.conftest import make_user  # noqa: PLC0415

    api.as_user(make_user("whatsapp"))
    h = key("wa-provider-msg-1")
    first = api.client.post(TASK, json={"title": "Pagar internet"}, headers=h).json()
    again = api.client.post(TASK, json={"title": "Pagar internet"}, headers=h).json()
    assert first["id"] == again["id"]
    assert [e.channel for e in api.audit.entries] == ["whatsapp"]


def test_idempotent_actions_replay_for_tasks_and_routines(api):
    task = api.client.post(TASK, json={"title": "t"}).json()
    a = api.client.post(f"{TASK}/{task['id']}/complete", headers=key("c1")).json()
    api.clock.advance(hours=3)
    b = api.client.post(f"{TASK}/{task['id']}/complete", headers=key("c1")).json()
    assert a == b

    rule = {"frequency": "daily", "time": "08:00", "timezone": "UTC", "start_date": "2026-11-03"}
    r1 = api.client.post(ROUTINE, json={"title": "r", "recurrence_rule": rule}, headers=key("r1"))
    r2 = api.client.post(ROUTINE, json={"title": "r", "recurrence_rule": rule}, headers=key("r1"))
    assert r1.json() == r2.json() and api.client.get(ROUTINE).json()["total"] == 1


# -- falhas de repositório -----------------------------------------------------------------


class Exploding:
    """Repositório cujo método consultado falha com o erro configurado."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def __getattr__(self, name: str):
        def fail(*_args, **_kwargs):
            raise self._error

        return fail


def broken_stores(error: Exception) -> Stores:
    audit = InMemoryAudit()
    return Stores(
        appointments=Exploding(error),
        tasks=Exploding(error),
        routines=Exploding(error),
        audit=audit,
        idempotency=InMemoryIdempotency(),
    )


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("post", APPT, BODY),
        ("get", APPT, None),
        ("get", f"{APPT}/{uuid4()}", None),
        ("post", TASK, {"title": "t"}),
        ("get", f"{TASK}/{uuid4()}", None),
        ("post", f"{TASK}/{uuid4()}/complete", None),
        ("get", ROUTINE, None),
        ("get", f"{ROUTINE}/{uuid4()}", None),
    ],
)
def test_repository_failure_returns_503_without_leaking_details(make_api, method, url, body):
    api = make_api(broken_stores(RepositoryError("senha=segredo host=db.interno")))
    r = getattr(api.client, method)(url, **({"json": body} if body else {}))
    assert r.status_code == 503
    error = r.json()["error"]
    assert error["code"] == "service_unavailable"
    assert "segredo" not in r.text and "db.interno" not in r.text
    assert error["request_id"]


def test_unexpected_repository_exception_is_generic_500(make_api):
    api = make_api(broken_stores(RuntimeError("boom interno")))
    r = api.client.get(APPT)
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert "boom" not in r.text


def test_failed_write_is_not_memorized_as_idempotent(make_api):
    audit = InMemoryAudit()
    idem = InMemoryIdempotency()
    good = InMemoryAppointmentRepository(audit)
    flaky_state = {"fail": True}

    class FlakyRepo:
        def add(self, appointment, entry):
            if flaky_state["fail"]:
                raise RepositoryError("timeout")
            good.add(appointment, entry)

        def list(self, *args):
            return good.list(*args)

    stores = Stores(
        FlakyRepo(), InMemoryTaskRepository(audit), InMemoryRoutineRepository(audit), audit, idem
    )
    api = make_api(stores)
    assert api.client.post(APPT, json=BODY, headers=key()).status_code == 503
    assert idem.records == {}
    flaky_state["fail"] = False
    assert api.client.post(APPT, json=BODY, headers=key()).status_code == 201
    assert api.client.get(APPT).json()["total"] == 1  # sem duplicidade após a nova tentativa


# -- integração ainda indisponível ---------------------------------------------------------


def test_without_persistence_wiring_domain_routes_fail_closed(app, user_a, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from app.auth.dependencies import get_current_user  # noqa: PLC0415

    app.dependency_overrides[get_current_user] = lambda: user_a
    r = TestClient(app, raise_server_exceptions=False).get(APPT)
    assert r.status_code == 503 and r.json()["error"]["code"] == "service_unavailable"


def test_without_auth_wiring_domain_routes_return_401(client):
    for url in (APPT, TASK, ROUTINE):
        r = client.get(url)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
