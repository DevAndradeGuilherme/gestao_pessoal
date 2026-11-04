"""Run against a disposable, migrated Supabase DB with two test auth users."""

import os
from uuid import UUID, uuid4

import psycopg
import pytest

from app.auth.models import CurrentUser
from app.core.errors import AppError, ErrorCode
from app.db.idempotency import execute_once, request_hash
from app.db.session import user_transaction


@pytest.fixture
def users(monkeypatch):
    dsn = os.getenv("GP03_TEST_DATABASE_URL")
    a = os.getenv("GP03_TEST_USER_A")
    b = os.getenv("GP03_TEST_USER_B")
    if not (dsn and a and b):
        pytest.skip("Requires isolated Supabase DB and two provisioned Auth users")
    monkeypatch.setenv("DATABASE_URL", dsn)
    return CurrentUser(id=UUID(a), channel="web"), CurrentUser(id=UUID(b), channel="web")


def test_rls_and_privileged_connection(users):
    a, b = users
    marker = f"gp03-{uuid4()}"
    with user_transaction(a) as conn:
        row = conn.execute(
            "insert into public.tasks(user_id, title) values (%s, %s) returning id",
            (str(a.id), marker),
        ).fetchone()
        task_id = row["id"]
    try:
        with user_transaction(b) as conn:
            assert (
                conn.execute("select id from public.tasks where id = %s", (task_id,)).fetchone()
                is None
            )
            assert (
                conn.execute(
                    "update public.tasks set title = 'intrusion' where id = %s returning id",
                    (task_id,),
                ).fetchone()
                is None
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with user_transaction(b) as conn:
                conn.execute(
                    "insert into public.tasks(user_id, title) values (%s, 'intrusion')",
                    (str(a.id),),
                )
        # A privileged login can bypass RLS; code must always SET LOCAL ROLE.
        with psycopg.connect(os.environ["DATABASE_URL"]) as privileged:
            assert (
                privileged.execute(
                    "select id from public.tasks where id = %s", (task_id,)
                ).fetchone()
                is not None
            )
    finally:
        with user_transaction(a) as conn:
            conn.execute("delete from public.tasks where id = %s and user_id = %s", (task_id, a.id))


def test_cross_owner_foreign_key(users):
    a, b = users
    with user_transaction(a) as conn:
        routine_id = conn.execute(
            "insert into public.routines(user_id, title, recurrence_rule) "
            "values (%s, 'test', '{\"frequency\":\"daily\"}') returning id",
            (a.id,),
        ).fetchone()["id"]
    try:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with user_transaction(b) as conn:
                conn.execute(
                    "insert into public.routine_occurrences(user_id, routine_id, scheduled_for) "
                    "values (%s, %s, current_date)",
                    (b.id, routine_id),
                )
    finally:
        with user_transaction(a) as conn:
            conn.execute(
                "delete from public.routines where id = %s and user_id = %s", (routine_id, a.id)
            )


def test_idempotency_replay_and_conflict(users):
    a, _ = users
    key = f"gp03-{uuid4()}"
    digest = request_hash("POST", "/tasks", {"title": "test"})
    calls = 0

    def operation(_conn):
        nonlocal calls
        calls += 1
        return 201, {"ok": True}

    try:
        with user_transaction(a) as conn:
            first = execute_once(conn, user=a, key=key, digest=digest, operation=operation)
        with user_transaction(a) as conn:
            second = execute_once(conn, user=a, key=key, digest=digest, operation=operation)
        assert not first.replayed and second.replayed and calls == 1
        with pytest.raises(AppError) as exc:
            with user_transaction(a) as conn:
                execute_once(conn, user=a, key=key, digest="b" * 64, operation=operation)
        assert exc.value.code == ErrorCode.IDEMPOTENCY_CONFLICT
    finally:
        with user_transaction(a) as conn:
            conn.execute(
                "delete from public.idempotency_keys where user_id = %s and key = %s",
                (a.id, key),
            )
