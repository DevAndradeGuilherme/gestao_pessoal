from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.auth.models import CurrentUser
from app.core.errors import AppError, ErrorCode
from app.db.idempotency import execute_once, request_hash


@pytest.fixture
def user():
    return CurrentUser(id=uuid4(), channel="web")


def test_hash_uses_route_and_canonical_json():
    assert request_hash("post", "/tasks", {"b": 2, "a": 1}) == request_hash(
        "POST", "/tasks", {"a": 1, "b": 2}
    )
    assert request_hash("POST", "/tasks", {}) != request_hash("POST", "/appointments", {})


def test_first_request_stores_response(user):
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = {"key": "k"}
    operation = Mock(return_value=(201, {"id": "new"}))
    result = execute_once(conn, user=user, key="k", digest="a" * 64, operation=operation)
    assert result.status == 201 and not result.replayed
    operation.assert_called_once_with(conn)
    assert conn.execute.call_count == 2


def test_replay_does_not_mutate(user):
    conn = Mock()
    conn.execute.side_effect = [
        Mock(fetchone=Mock(return_value=None)),
        Mock(
            fetchone=Mock(
                return_value={
                    "request_hash": "a" * 64,
                    "status": "completed",
                    "response_status": 201,
                    "response_body": {"id": "old"},
                }
            )
        ),
    ]
    operation = Mock()
    result = execute_once(conn, user=user, key="k", digest="a" * 64, operation=operation)
    assert result.replayed and result.body == {"id": "old"}
    operation.assert_not_called()


def test_conflicting_payload_returns_409(user):
    conn = Mock()
    conn.execute.side_effect = [
        Mock(fetchone=Mock(return_value=None)),
        Mock(fetchone=Mock(return_value={"request_hash": "b" * 64})),
    ]
    with pytest.raises(AppError) as exc:
        execute_once(conn, user=user, key="k", digest="a" * 64, operation=Mock())
    assert exc.value.status_code == 409
    assert exc.value.code == ErrorCode.IDEMPOTENCY_CONFLICT
