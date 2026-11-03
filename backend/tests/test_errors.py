from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.auth import CurrentUserDep
from app.core.errors import AppError, ErrorCode


class _Payload(BaseModel):
    title: str


def _register_probe_routes(app: FastAPI) -> None:
    @app.post("/_probe/validation")
    def validation(payload: _Payload) -> _Payload:
        return payload

    @app.get("/_probe/app-error")
    def app_error() -> None:
        raise AppError(409, ErrorCode.CONFLICT, "Conflito de teste.")

    @app.get("/_probe/crash")
    def crash() -> None:
        raise RuntimeError("segredo interno")

    @app.get("/_probe/protected")
    def protected(user: CurrentUserDep) -> dict[str, str]:
        return {"id": str(user.id)}


def _assert_envelope(response, status: int, code: str) -> dict:
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert isinstance(error["details"], list)
    assert error["request_id"] == response.headers["X-Request-ID"]
    return error


def test_not_found_uses_envelope(client: TestClient) -> None:
    _assert_envelope(client.get("/does-not-exist"), 404, "not_found")


def test_method_not_allowed_uses_envelope(client: TestClient) -> None:
    _assert_envelope(client.delete("/health"), 405, "method_not_allowed")


def test_validation_error_lists_fields(app: FastAPI, client: TestClient) -> None:
    _register_probe_routes(app)

    error = _assert_envelope(client.post("/_probe/validation", json={}), 422, "validation_error")

    assert error["details"][0]["field"] == "body.title"
    assert error["details"][0]["type"] == "missing"


def test_app_error_uses_envelope(app: FastAPI, client: TestClient) -> None:
    _register_probe_routes(app)

    error = _assert_envelope(client.get("/_probe/app-error"), 409, "conflict")

    assert error["message"] == "Conflito de teste."


def test_unhandled_error_hides_internal_message(app: FastAPI, client: TestClient) -> None:
    _register_probe_routes(app)

    error = _assert_envelope(client.get("/_probe/crash"), 500, "internal_error")

    assert "segredo" not in error["message"]


def test_current_user_fails_closed_until_auth_is_implemented(
    app: FastAPI, client: TestClient
) -> None:
    _register_probe_routes(app)

    _assert_envelope(client.get("/_probe/protected"), 401, "unauthenticated")
