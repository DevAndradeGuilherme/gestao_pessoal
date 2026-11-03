import pytest

from app.core.config import Settings
from app.core.schemas import Page, PageParams


def test_cors_origins_accept_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000, https://app.example")

    settings = Settings(_env_file=None)

    assert settings.cors_allowed_origins == ["http://localhost:3000", "https://app.example"]


def test_page_params_enforce_limits() -> None:
    assert PageParams().limit == 50
    with pytest.raises(ValueError):
        PageParams(limit=201)
    with pytest.raises(ValueError):
        PageParams(offset=-1)


def test_page_serializes_generic_items() -> None:
    page = Page[int](items=[1, 2], limit=2, offset=0, total=5)

    assert page.model_dump() == {"items": [1, 2], "limit": 2, "offset": 0, "total": 5}
