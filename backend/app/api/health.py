"""Health check de liveness: indica apenas que o processo da API responde.

Não consulta banco nem integrações externas. Readiness com dependências reais
(Supabase, Redis, Evolution) será adicionada pelas tarefas que as introduzirem.
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse, summary="Liveness da API")
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
    )
