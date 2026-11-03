"""Identidade do chamador (ownership: GP-03). Contrato em `docs/CONTRATOS.md`, seção 5."""

from app.auth.dependencies import CurrentUserDep, get_current_user
from app.auth.models import CurrentUser

__all__ = ["CurrentUser", "CurrentUserDep", "get_current_user"]
