import uuid

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "gestao-pessoal-api"
    assert set(body) == {"status", "service", "version", "environment"}


def test_request_id_is_generated(client: TestClient) -> None:
    response = client.get("/health")

    uuid.UUID(response.headers["X-Request-ID"])


def test_valid_request_id_is_propagated(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "web-abc.123"})

    assert response.headers["X-Request-ID"] == "web-abc.123"


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "bad id\nwith spaces"})

    assert response.headers["X-Request-ID"] != "bad id\nwith spaces"
    uuid.UUID(response.headers["X-Request-ID"])


def test_cors_preflight_allows_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers
