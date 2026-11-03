from typing import Annotated

from fastapi import Depends

from app.auth.models import CurrentUser
from app.core.errors import AppError, ErrorCode


def get_current_user() -> CurrentUser:
    """Resolve o usuário autenticado a partir de `Authorization: Bearer <JWT Supabase>`.

    Ainda sem validação de JWT (GP-03): falha fechada com 401 para qualquer chamada.
    Testes de domínio (GP-04) substituem esta dependência via `app.dependency_overrides`.
    """
    raise AppError(401, ErrorCode.UNAUTHENTICATED, "Autenticação ainda não configurada.")


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
