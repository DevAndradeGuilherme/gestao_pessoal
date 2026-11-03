# Gestão Pessoal

Aplicação de gestão pessoal com painel web, WhatsApp, Google Agenda e incorporação gradual do domínio financeiro existente.

> **Situação:** fundação técnica (GP-01/GP-02) entregue: skeletons web/API, contratos iniciais e CI. Funcionalidades de negócio ainda não implementadas. O arquivo [CONTEXTO.md](CONTEXTO.md) v0.2 é a fonte de verdade para requisitos e decisões do produto.

## Stack aprovada

- Web: Next.js, TypeScript e Tailwind CSS.
- API central: FastAPI e Python.
- Persistência e identidade: Supabase gerenciado (PostgreSQL e Auth).
- WhatsApp: Evolution API / Baileys, uma instância pessoal no MVP.
- Interpretação de mensagens: OpenAI para intenção e extração estruturada; a API valida e executa.
- Agenda: Google Calendar API com sincronização unidirecional sistema → Google no MVP.
- Automações: Celery e Redis, com agendamentos futuros persistidos no PostgreSQL.
- Hospedagem: VPS KVM2 Hostinger.
- Finanças: migração controlada do domínio Django existente, com regressão e sem implementação duplicada.

## Organização

```text
gestao_pessoal/
├── CONTEXTO.md            # requisitos e decisões de produto
├── README.md              # entrada do projeto
├── AGENTS.md              # regras compartilhadas para agentes
├── CLAUDE.md              # instruções específicas para Claude Code
├── .github/workflows/     # CI (lint, testes, build, OpenAPI)
├── docs/
│   ├── ARQUITETURA.md
│   ├── PLANO_DESENVOLVIMENTO.md
│   ├── TAREFAS.md
│   ├── CONTRATOS.md
│   ├── DECISOES.md
│   └── openapi.json        # schema gerado da API (não editar à mão)
├── frontend/               # Next.js + TypeScript + Tailwind (ver frontend/README.md)
├── backend/                # FastAPI (ver backend/README.md)
├── infra/                  # a implementar (GP-12)
└── supabase/               # a implementar (GP-03)
```

## Como trabalhar neste repositório

1. Ler `CONTEXTO.md`, `AGENTS.md`, `docs/PLANO_DESENVOLVIMENTO.md` e a tarefa atribuída em `docs/TAREFAS.md`.
2. Verificar se a tarefa depende de uma **ação manual** (credenciais, OAuth, configuração de serviços, aprovação de migração).
3. Executar somente o escopo da tarefa, respeitando os limites de arquivos e os contratos aprovados.
4. Rodar os testes e verificações disponíveis; declarar o que não foi testado.
5. Atualizar o status e o registro de decisões quando houver alteração relevante.
6. Submeter alterações em branch/worktree própria e integrar após revisão.

## Desenvolvimento local

Pré-requisitos: Python >= 3.12 e Node.js >= 22 com npm. Nenhum serviço externo é necessário nesta fase.

```bash
# API (terminal 1) — http://localhost:8000/health
cd backend
python -m venv .venv
.venv/Scripts/activate            # Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload

# Web (terminal 2) — http://localhost:3000 e /healthz
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Verificações (as mesmas do CI):

```bash
cd backend  && ruff check . && ruff format --check . && pytest && python scripts/export_openapi.py --check
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

**Não há deploy oficial neste estágio** (GP-12). Não assumir que Supabase, Google, Evolution API, OpenAI ou VPS já estão configurados.

## Documentação

- [Arquitetura e limites](docs/ARQUITETURA.md)
- [Plano de desenvolvimento](docs/PLANO_DESENVOLVIMENTO.md)
- [Quadro de tarefas](docs/TAREFAS.md)
- [Contratos técnicos](docs/CONTRATOS.md)
- [Registro de decisões](docs/DECISOES.md)

## Segurança

Não versionar arquivos `.env`, chaves, tokens, credenciais, sessões WhatsApp ou dados pessoais. O produto deverá aplicar autenticação, autorização por usuário, RLS quando aplicável, idempotência e registros de auditoria.
