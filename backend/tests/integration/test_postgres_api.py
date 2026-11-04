"""API ponta a ponta sobre PostgreSQL real (banco de desenvolvimento isolado).

Exige `GP03_TEST_DATABASE_URL`, `GP03_TEST_USER_A` e `GP03_TEST_USER_B` (migration aplicada e dois
usuários Supabase Auth). A identidade é injetada via `dependency_overrides[get_current_user]`;
a validação do JWT real é coberta em `tests/integration/test_real_jwt.py`. Os dados criados usam o
prefixo `f1int-` e são removidos ao final.
"""

import os
import threading
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import CurrentUser
from app.db.session import user_transaction
from app.main import create_app

PREFIX = "f1int-"


@pytest.fixture(scope="module")
def users():
    dsn = os.getenv("GP03_TEST_DATABASE_URL")
    a, b = os.getenv("GP03_TEST_USER_A"), os.getenv("GP03_TEST_USER_B")
    if not (dsn and a and b):
        pytest.skip("Requires isolated Supabase DB and two provisioned Auth users")
    os.environ["DATABASE_URL"] = dsn
    return CurrentUser(id=UUID(a), channel="web"), CurrentUser(id=UUID(b), channel="web")


@pytest.fixture
def ctx(users, settings):
    """Cliente HTTP com identidade trocável e limpeza dos dados criados."""
    app = create_app(settings)
    state = {"user": users[0]}
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    client = TestClient(app, raise_server_exceptions=False)
    yield client, state, users
    for user in users:
        with user_transaction(user) as conn:
            for table in ("appointments", "tasks", "routines"):
                conn.execute(
                    f"delete from public.{table} where user_id = %s and title like %s",  # noqa: S608
                    (user.id, f"{PREFIX}%"),
                )
            conn.execute(
                "delete from public.activity_log where user_id = %s and entity_id not in "
                "(select id from public.appointments where user_id = %s "
                "union select id from public.tasks where user_id = %s "
                "union select id from public.routines where user_id = %s "
                "union select id from public.routine_occurrences where user_id = %s)",
                (user.id, user.id, user.id, user.id, user.id),
            )
            conn.execute(
                "delete from public.idempotency_keys where user_id = %s and key like %s",
                (user.id, f"{PREFIX}%"),
            )


def _appt(title: str = "x", **extra):
    return {"title": f"{PREFIX}{title}", "starts_at": "2030-01-10T14:00:00-03:00", **extra}


def _audit_actions(user: CurrentUser, entity_id: str) -> list[str]:
    with user_transaction(user) as conn:
        rows = conn.execute(
            "select action from public.activity_log where user_id = %s and entity_id = %s "
            "order by created_at, id",
            (user.id, entity_id),
        ).fetchall()
    return [r["action"] for r in rows]


def test_appointment_lifecycle_persists_and_audits(ctx):
    client, _, (a, _b) = ctx
    created = client.post("/api/v1/appointments", json=_appt("life", description="  d  "))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["user_id"] == str(a.id)
    assert body["ends_at"] is None  # nenhuma duração presumida
    assert body["sync_status"] == "pending"
    appt_id = body["id"]

    # Requisição nova = conexão nova: o dado precisa ter sido confirmado no banco.
    got = client.get(f"/api/v1/appointments/{appt_id}")
    assert got.status_code == 200 and got.json()["description"] == "d"

    resched = client.post(
        f"/api/v1/appointments/{appt_id}/reschedule",
        json={"starts_at": "2030-01-11T09:00:00-03:00"},
    )
    assert resched.status_code == 200
    assert resched.json()["starts_at"] == "2030-01-11T12:00:00Z"
    assert resched.json()["ends_at"] is None

    cancelled = client.post(f"/api/v1/appointments/{appt_id}/cancel", json={"reason": "teste"})
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert client.patch(f"/api/v1/appointments/{appt_id}", json={"title": "z"}).status_code == 409

    listed = client.get(
        "/api/v1/appointments",
        params={"starts_at_from": "2030-01-11T00:00:00Z", "starts_at_to": "2030-01-12T00:00:00Z"},
    )
    assert [i["id"] for i in listed.json()["items"]] == [appt_id]
    assert listed.json()["total"] == 1

    assert _audit_actions(a, appt_id) == [
        "appointment.created",
        "appointment.rescheduled",
        "appointment.cancelled",
    ]


def test_users_are_isolated(ctx):
    client, state, (a, b) = ctx
    appt = client.post("/api/v1/appointments", json=_appt("iso")).json()["id"]
    task = client.post("/api/v1/tasks", json={"title": f"{PREFIX}iso"}).json()["id"]
    state["user"] = b
    assert client.get(f"/api/v1/appointments/{appt}").status_code == 404
    assert client.post(f"/api/v1/appointments/{appt}/cancel").status_code == 404
    assert client.post(f"/api/v1/tasks/{task}/complete").status_code == 404
    assert client.get("/api/v1/appointments").json()["items"] == []
    assert client.get("/api/v1/tasks").json()["items"] == []
    state["user"] = a
    assert client.get(f"/api/v1/appointments/{appt}").json()["status"] == "scheduled"
    assert client.get(f"/api/v1/tasks/{task}").json()["status"] == "pending"


def test_body_user_id_is_rejected(ctx):
    client, _, _ = ctx
    res = client.post("/api/v1/appointments", json=_appt("spoof", user_id=str(uuid4())))
    assert res.status_code == 422


def test_idempotent_create_replays_without_second_mutation(ctx):
    client, _, (a, _b) = ctx
    key = f"{PREFIX}{uuid4()}"
    first = client.post(
        "/api/v1/appointments", json=_appt("idem"), headers={"Idempotency-Key": key}
    )
    again = client.post(
        "/api/v1/appointments", json=_appt("idem"), headers={"Idempotency-Key": key}
    )
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()
    other = client.post(
        "/api/v1/appointments", json=_appt("idem-other"), headers={"Idempotency-Key": key}
    )
    assert other.status_code == 409 and other.json()["error"]["code"] == "idempotency_conflict"
    with user_transaction(a) as conn:
        n = conn.execute(
            "select count(*) as n from public.appointments where user_id = %s and title = %s",
            (a.id, f"{PREFIX}idem"),
        ).fetchone()["n"]
    assert n == 1
    assert _audit_actions(a, first.json()["id"]) == ["appointment.created"]


def test_concurrent_requests_with_same_key_create_one_row(ctx):
    client, _, (a, _b) = ctx
    key = f"{PREFIX}{uuid4()}"
    results: list[int] = []

    def call():
        res = client.post(
            "/api/v1/tasks", json={"title": f"{PREFIX}conc"}, headers={"Idempotency-Key": key}
        )
        results.append(res.status_code)

    threads = [threading.Thread(target=call) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [201] * 4
    with user_transaction(a) as conn:
        n = conn.execute(
            "select count(*) as n from public.tasks where user_id = %s and title = %s",
            (a.id, f"{PREFIX}conc"),
        ).fetchone()["n"]
    assert n == 1


def test_task_complete_reopen_and_overdue(ctx):
    client, _, _ = ctx
    task = client.post(
        "/api/v1/tasks",
        json={"title": f"{PREFIX}t", "due_at": "2020-01-01T10:00:00Z", "priority": "high"},
    ).json()
    assert task["sync_to_calendar"] is False and task["status"] == "pending"
    done = client.post(f"/api/v1/tasks/{task['id']}/complete", json={})
    assert done.status_code == 200
    assert done.json()["status"] == "completed" and done.json()["completed_at"]
    assert client.get("/api/v1/tasks", params={"status": "completed"}).json()["total"] >= 1
    reopened = client.post(f"/api/v1/tasks/{task['id']}/reopen")
    assert reopened.json()["status"] == "pending" and reopened.json()["completed_at"] is None
    pending = client.get("/api/v1/tasks", params={"status": "pending"}).json()["items"]
    assert task["id"] in [t["id"] for t in pending]


def test_routine_occurrences_roundtrip(ctx):
    client, _, _ = ctx
    rule = {
        "frequency": "weekly",
        "by_weekday": ["mon", "wed"],
        "time": "19:00",
        "timezone": "America/Sao_Paulo",
        "start_date": "2030-01-01",
    }
    routine = client.post(
        "/api/v1/routines", json={"title": f"{PREFIX}r", "recurrence_rule": rule}
    ).json()
    window = {"window_start": "2030-01-07T00:00:00Z", "window_end": "2030-01-14T00:00:00Z"}
    gen = client.post(f"/api/v1/routines/{routine['id']}/occurrences/generate", json=window)
    assert gen.status_code in (200, 201), gen.text
    assert gen.json()["created"] == 2
    instants = [o["scheduled_for"] for o in gen.json()["occurrences"]]
    assert instants == ["2030-01-07T22:00:00Z", "2030-01-09T22:00:00Z"]
    again = client.post(f"/api/v1/routines/{routine['id']}/occurrences/generate", json=window)
    assert again.json()["created"] == 0

    first = gen.json()["occurrences"][0]["id"]
    done = client.post(f"/api/v1/routines/{routine['id']}/occurrences/{first}/complete", json={})
    assert done.status_code == 200 and done.json()["status"] == "completed"
    listed = client.get(
        f"/api/v1/routines/{routine['id']}/occurrences", params={"status": "completed"}
    ).json()
    assert [o["id"] for o in listed["items"]] == [first]
    assert listed["items"][0]["scheduled_for"] == "2030-01-07T22:00:00Z"
    assert client.get("/api/v1/routines").json()["items"][0]["id"] == routine["id"]


def test_database_failure_fails_closed_without_leaking(ctx, monkeypatch):
    client, _, _ = ctx
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:secret-pw@127.0.0.1:1/db?connect_timeout=2")
    res = client.get("/api/v1/appointments")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "service_unavailable"
    assert "secret-pw" not in res.text and "127.0.0.1" not in res.text
    post = client.post("/api/v1/appointments", json=_appt("down"))
    assert post.status_code == 503
    monkeypatch.delenv("DATABASE_URL")
    assert client.get("/api/v1/tasks").status_code == 503


def test_failed_mutation_rolls_back_everything(ctx, monkeypatch):
    """Falha ao gravar a auditoria desfaz a mutação (mesma transação)."""
    client, _, (a, _b) = ctx
    from app.db.repos import appointments as mod

    def boom(conn, audit):  # noqa: ARG001
        raise mod.RepositoryError("audit failed")

    monkeypatch.setattr(mod, "insert_audit", boom)
    res = client.post("/api/v1/appointments", json=_appt("rollback"))
    assert res.status_code == 503
    with user_transaction(a) as conn:
        n = conn.execute(
            "select count(*) as n from public.appointments where user_id = %s and title = %s",
            (a.id, f"{PREFIX}rollback"),
        ).fetchone()["n"]
    assert n == 0
