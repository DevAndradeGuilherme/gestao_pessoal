"""Cryptographic JWT tests; requires PyJWT[crypto]."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.auth.dependencies import verify_access_token
from app.core.errors import AppError

cryptography = pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402


@pytest.fixture
def keys(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class Key:
        key = private.public_key()

    class Client:
        def get_signing_key_from_jwt(self, _token):
            return Key()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr("app.auth.dependencies._jwk_client", lambda _issuer: Client())
    return private, other


def token(key, **overrides):
    claims = {
        "sub": str(uuid4()),
        "role": "authenticated",
        "aud": "authenticated",
        "iss": "https://example.supabase.co/auth/v1",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"}), claims


def test_valid_token(keys):
    encoded, claims = token(keys[0])
    assert str(verify_access_token(encoded).id) == claims["sub"]


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
        {"iss": "https://other.supabase.co/auth/v1"},
        {"aud": "anon"},
        {"sub": "not-a-uuid"},
        {"role": "service_role"},
        {"exp": None},
    ],
)
def test_bad_claims_rejected(keys, changes):
    encoded, _ = token(keys[0], **changes)
    with pytest.raises(AppError) as exc:
        verify_access_token(encoded)
    assert exc.value.status_code == 401


def test_wrong_signature_rejected(keys):
    encoded, _ = token(keys[1])
    with pytest.raises(AppError) as exc:
        verify_access_token(encoded)
    assert exc.value.status_code == 401


def test_malformed_token_rejected(keys):
    with pytest.raises(AppError) as exc:
        verify_access_token("not-a-jwt")
    assert exc.value.status_code == 401


def test_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    with pytest.raises(AppError) as exc:
        verify_access_token("anything")
    assert exc.value.status_code == 401
