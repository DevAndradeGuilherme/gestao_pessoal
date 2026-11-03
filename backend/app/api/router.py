"""Agregador das rotas versionadas `/api/v1`.

Cada módulo de domínio expõe um `APIRouter` próprio e é registrado aqui
(ownership: GP-04). Nenhuma rota de negócio existe ainda.
"""

from typing import Any

from fastapi import APIRouter

from app.core.errors import ErrorResponse

API_V1_PREFIX = "/api/v1"

# Documenta no OpenAPI o envelope de erro comum a todas as rotas `/api/v1`.
COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Não autenticado"},
    403: {"model": ErrorResponse, "description": "Sem permissão"},
    404: {"model": ErrorResponse, "description": "Recurso não encontrado"},
    422: {"model": ErrorResponse, "description": "Erro de validação"},
}

api_router = APIRouter(prefix=API_V1_PREFIX, responses=COMMON_ERROR_RESPONSES)
