"""Adaptadores PostgreSQL das interfaces de repositório do domínio (GP-04).

Todos operam sobre a conexão de `user_transaction` (papel `app_backend`, RLS ativa) e
filtram por `user_id` também no SQL (defesa em profundidade, CONTRATOS §5).
"""
