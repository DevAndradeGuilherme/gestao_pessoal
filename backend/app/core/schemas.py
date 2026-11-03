"""Schemas compartilhados por todos os módulos (contrato em `docs/CONTRATOS.md`)."""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200


class PageParams(BaseModel):
    limit: int = Field(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    offset: int = Field(0, ge=0)


PageParamsQuery = Annotated[PageParams, Query()]


class Page[T](BaseModel):
    """Envelope de listagem paginada por `limit`/`offset`."""

    items: list[T]
    limit: int
    offset: int
    total: int
