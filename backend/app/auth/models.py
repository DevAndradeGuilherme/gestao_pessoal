from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CurrentUser(BaseModel):
    """Usuário autenticado entregue aos serviços de domínio.

    `id` corresponde ao `auth.users.id` do Supabase (claim `sub` do JWT) e é a única
    fonte de `user_id` para autorização; nunca usar `user_id` vindo do corpo da requisição.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    channel: Literal["web", "whatsapp"]
