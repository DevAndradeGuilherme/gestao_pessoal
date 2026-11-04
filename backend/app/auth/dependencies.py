"""Supabase access-token verification for FastAPI endpoints."""

import os
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import CurrentUser
from app.core.errors import AppError, ErrorCode

_bearer = HTTPBearer(auto_error=False)
_ALGORITHMS = ["RS256", "ES256"]


def _issuer() -> str:
    raw = os.environ.get("SUPABASE_URL", "").rstrip("/")
    parsed = urlsplit(raw)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("SUPABASE_URL must be the HTTPS origin of the Supabase project")
    return f"{raw}/auth/v1"


@lru_cache(maxsize=4)
def _jwk_client(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", lifespan=600)


def verify_access_token(token: str) -> CurrentUser:
    """Verify an asymmetric Supabase Auth JWT. Missing configuration fails closed."""
    try:
        issuer = _issuer()
        signing_key = _jwk_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,
            audience="authenticated",
            issuer=issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
        if claims.get("role") != "authenticated":
            raise ValueError("Unexpected Supabase role")
        user_id = UUID(str(claims["sub"]))
        if user_id.int == 0:
            raise ValueError("Empty user identifier")
        return CurrentUser(id=user_id, channel="web")
    except (jwt.PyJWTError, ValueError, TypeError, KeyError, OSError) as exc:
        raise AppError(401, ErrorCode.UNAUTHENTICATED, "Credencial ausente ou inválida.") from exc


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise AppError(401, ErrorCode.UNAUTHENTICATED, "Credencial ausente ou inválida.")
    return verify_access_token(credentials.credentials)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
