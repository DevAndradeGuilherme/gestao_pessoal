import pytest

from app.auth.dependencies import get_current_user
from app.core.errors import AppError, ErrorCode


def test_missing_bearer_token_is_401():
    with pytest.raises(AppError) as exc:
        get_current_user(None)
    assert exc.value.status_code == 401
    assert exc.value.code == ErrorCode.UNAUTHENTICATED
