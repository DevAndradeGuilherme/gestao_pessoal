# Backend — FastAPI

API central do Sistema de Gestão Pessoal. Web e WhatsApp chamam os **mesmos serviços de domínio**.

## Comandos

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload      # http://localhost:8000  (docs em /docs)
pytest                             # testes
ruff check . && ruff format --check .
python scripts/export_openapi.py   # regrava docs/openapi.json (use --check no CI)
```

Liveness: `GET /health`. Requer Python >= 3.12.

## Estrutura

```text
app/
├── main.py            # create_app(): middlewares, handlers, routers   (integrador)
├── core/              # config, erros, request id, schemas comuns       (integrador)
├── api/
│   ├── health.py      # GET /health
│   └── router.py      # agregador /api/v1                                (GP-04 registra módulos)
├── auth/              # CurrentUser e get_current_user                   (GP-03)
├── db/                # sessão, modelos de persistência                  (GP-03, a criar)
├── modules/           # domínio: um pacote por capacidade                (GP-04+)
└── integrations/      # adaptadores externos atrás de Protocol           (GP-06/07/08)
tests/                 # espelha app/: tests/modules/<mod>/, tests/auth/ ...
scripts/               # utilitários de desenvolvimento
```

### Convenção de módulo de domínio (`app/modules/<nome>/`)

| Arquivo | Responsabilidade |
|---|---|
| `router.py` | `APIRouter` fino: valida entrada, resolve `CurrentUserDep`, chama o serviço |
| `schemas.py` | Pydantic de request/response (`<Recurso>Create`, `<Recurso>Update`, `<Recurso>Read`) |
| `service.py` | Regras de negócio; recebe `CurrentUser` explícito; usado por web **e** WhatsApp |
| `repository.py` | Acesso a dados, sempre filtrado por `user_id` |

Regras:
- Serviços não importam FastAPI nem conhecem o canal de origem além de `CurrentUser.channel`.
- Falhas de negócio levantam `AppError` (`app/core/errors.py`); nunca montar resposta de erro manual.
- Integrações externas são injetadas como `Protocol` (`app/integrations/<provedor>/`), com fake em testes.
  O registro local é persistido **antes** de qualquer chamada externa.
- Nenhuma dependência nova sem registrar em `docs/DECISOES.md` (alteração de `pyproject.toml` é do integrador).
