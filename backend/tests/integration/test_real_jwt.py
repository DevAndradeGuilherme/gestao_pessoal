"""JWT real do Supabase Auth + PostgreSQL real, sem `dependency_overrides`.

Exige: SUPABASE_URL, DATABASE_URL, SUPABASE_PUBLISHABLE_KEY (chave pública) e as credenciais de
duas contas de teste (E2E_USER_A_EMAIL/PASSWORD, E2E_USER_B_EMAIL/PASSWORD) do projeto de
desenvolvimento. Nenhum token ou senha é impresso ou registrado.
"""

import base64
import json
import os
import time

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

NEEDED = (
    "SUPABASE_URL",
    "DATABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "E2E_USER_A_EMAIL",
    "E2E_USER_A_PASSWORD",
    "E2E_USER_B_EMAIL",
    "E2E_USER_B_PASSWORD",
)


def _login(prefix: str) -> str:
    res = httpx.post(
        f"{os.environ['SUPABASE_URL'].rstrip('/')}/auth/v1/token?grant_type=password",
        headers={"apikey": os.environ["SUPABASE_PUBLISHABLE_KEY"]},
        json={
            "email": os.environ[f"{prefix}_EMAIL"],
            "password": os.environ[f"{prefix}_PASSWORD"],
        },
        timeout=20,
    )
    assert res.status_code == 200, f"login failed with HTTP {res.status_code}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def tokens():
    if any(not os.getenv(name) for name in NEEDED):
        pytest.skip("Requires Supabase dev project and two test accounts")
    return _login("E2E_USER_A"), _login("E2E_USER_B")


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings), raise_server_exceptions=False)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_real_token_is_accepted_and_isolated(client, tokens):
    a, b = tokens
    title = f"f1int-real-{time.time_ns()}"
    created = client.post(
        "/api/v1/tasks",
        json={"title": title},
        headers={**_auth(a), "Idempotency-Key": f"f1int-{time.time_ns()}"},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    sub = jwt.decode(a, options={"verify_signature": False})["sub"]
    assert created.json()["user_id"] == sub  # identidade vem do token
    try:
        assert client.get(f"/api/v1/tasks/{task_id}", headers=_auth(a)).status_code == 200
        assert client.get(f"/api/v1/tasks/{task_id}", headers=_auth(b)).status_code == 404
        assert task_id not in [
            t["id"] for t in client.get("/api/v1/tasks", headers=_auth(b)).json()["items"]
        ]
        assert client.post(f"/api/v1/tasks/{task_id}/complete", headers=_auth(b)).status_code == 404
    finally:
        _cleanup(task_id, sub)


def _cleanup(task_id: str, sub: str) -> None:
    from uuid import UUID

    from app.auth.models import CurrentUser
    from app.db.session import user_transaction

    with user_transaction(CurrentUser(id=UUID(sub), channel="web")) as conn:
        conn.execute("delete from public.tasks where id = %s and user_id = %s", (task_id, sub))
        conn.execute(
            "delete from public.activity_log where entity_id = %s and user_id = %s", (task_id, sub)
        )


def test_invalid_tokens_are_rejected(client, tokens):
    a, _ = tokens
    head, payload, sig = a.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    forged = dict(claims, sub="00000000-0000-0000-0000-000000000001")
    forged_payload = base64.urlsafe_b64encode(json.dumps(forged).encode()).rstrip(b"=").decode()
    expired = dict(claims, exp=int(time.time()) - 3600)
    expired_payload = base64.urlsafe_b64encode(json.dumps(expired).encode()).rstrip(b"=").decode()
    for bad in (
        f"{head}.{forged_payload}.{sig}",  # payload adulterado, assinatura antiga
        f"{head}.{expired_payload}.{sig}",  # expirado (e assinatura inválida)
        "not-a-jwt",
        a[:-4] + "AAAA",  # assinatura corrompida
    ):
        res = client.get("/api/v1/tasks", headers=_auth(bad))
        assert res.status_code == 401, bad[:10]
        assert res.json()["error"]["code"] == "unauthenticated"
    assert client.get("/api/v1/tasks").status_code == 401


def test_hs256_token_signed_with_unknown_secret_is_rejected(client):
    if not os.getenv("SUPABASE_URL"):
        pytest.skip("Requires SUPABASE_URL")
    forged = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "aud": "authenticated",
            "role": "authenticated",
            "iss": os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1",
            "exp": int(time.time()) + 600,
        },
        "attacker-secret-attacker-secret-32b",
        algorithm="HS256",
    )
    assert client.get("/api/v1/tasks", headers=_auth(forged)).status_code == 401
