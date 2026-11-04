# Registro de decisões — ADR leve

Este documento registra escolhas técnicas e revisões durante a implementação. **Decisões de produto já aprovadas** permanecem em `CONTEXTO.md` v0.2, seção 10, que prevalece.

## Convenção

Para nova decisão, usar:

```text
### ADR-XXX — Título
- Data: AAAA-MM-DD
- Estado: proposta | aprovada | substituída
- Contexto:
- Decisão:
- Alternativas consideradas:
- Consequências / riscos:
- Evidência / testes:
- Documentos e módulos afetados:
```

## Decisões de produto incorporadas por referência

| Referência | Tema | Definição aprovada (não rediscutir sem mudança explícita de escopo) |
|---|---|---|
| CONTEXTO §10 | Stack | Next.js + TypeScript + Tailwind; FastAPI + Python |
| CONTEXTO §10 | Banco/Auth | Supabase gerenciado, vínculo por usuário e isolamento |
| CONTEXTO §10 | WhatsApp | Uma instância pessoal Evolution API/Baileys |
| CONTEXTO §10 | IA | OpenAI híbrida, backend valida/autoriza/executa |
| CONTEXTO §10 | Agenda | Sincronização sistema → Google no MVP |
| CONTEXTO §10 | Tarefas | Sync Google somente por escolha explícita |
| CONTEXTO §10 | Duração | Sem duração presumida pelo produto |
| CONTEXTO §10 | Recorrência | Flexível, incluindo último dia do mês |
| CONTEXTO §10 | Notificações | 07h, 23h, silêncio 00h–07h; configuráveis |
| CONTEXTO §10 | Jobs | Celery/Redis; persistência durável no PostgreSQL |
| CONTEXTO §10 | Finanças | Migração progressiva do Django para backend principal |

## ADR-001 — Estratégia de execução com agentes

- Data: 2026-11-03
- Estado: proposta operacional, aguardando primeira execução
- Contexto: necessidade de acelerar o MVP reduzindo consumo de tokens e conflitos de código.
- Decisão: cinco fases, doze tarefas agrupadas, até três agentes de implementação simultâneos; um integrador controla mudanças de contratos, migrations e raiz.
- Alternativas consideradas: 38 prompts granulares; implementação sequencial por um único agente.
- Consequências / riscos: tarefas maiores exigem aceite claro e eventual divisão de GP-10 caso migração financeira exceda um ciclo seguro.
- Evidência / testes: avaliar retrabalho e tempo após a Fase 1.
- Documentos e módulos afetados: `docs/PLANO_DESENVOLVIMENTO.md`, `docs/TAREFAS.md`, `AGENTS.md`.

## ADR-002 — Convenções de monorepo, dependências e CI

- Data: 2026-11-03
- Estado: proposta (GP-01/GP-02), aguardando aprovação do integrador
- Contexto: GP-03, GP-04 e GP-05 precisam iniciar em paralelo sobre uma base executável, com contratos e fronteiras claros e sem dependências excessivas.
- Decisão:
  - Monorepo com projetos independentes em `frontend/` e `backend/`; sem gerenciador de workspace na raiz.
  - Frontend: Next.js 16.4.5 (gerado por `create-next-app`, App Router, `src/`), TypeScript estrito, Tailwind CSS 4, ESLint (`eslint-config-next`), Prettier e Vitest. npm com `package-lock.json` versionado; Node >= 22.
  - Backend: FastAPI + Pydantic 2 + pydantic-settings + Uvicorn; dev com pytest, httpx (TestClient) e Ruff (lint + formatação). Python >= 3.12 (CI em 3.12; validado localmente em 3.13). Dependências declaradas com faixas em `pyproject.toml`, instalação por `pip`.
  - Estrutura modular do backend: `core` (transversal), `api` (health + agregador `/api/v1`), `auth`, `db`, `modules/<capacidade>` (`router`/`schemas`/`service`/`repository`) e `integrations/<provedor>` atrás de `Protocol`.
  - Envelope de erro único `{"error": {code, message, details, request_id}}` com códigos estáveis; `X-Request-ID` em toda resposta; recurso de outro usuário responde `404`.
  - Schemas compartilháveis: Pydantic como fonte, `docs/openapi.json` exportado e verificado no CI; tipos comuns espelhados no frontend.
  - CI GitHub Actions (`.github/workflows/ci.yml`) em PRs e push na `main`: lint, formatação, testes, typecheck/build e checagem do OpenAPI.
  - `get_current_user` falha fechada (401) até GP-03.
- Alternativas consideradas: `uv`/Poetry com lockfile Python (adiado: ferramenta ausente no ambiente atual; reavaliar em GP-12 para builds reproduzíveis); pnpm/turborepo (desnecessário para dois projetos); Jest (Vitest é mais leve para TS/ESM); envelope também em respostas de sucesso (rejeitado por verbosidade sem ganho).
- Consequências / riscos: backend sem lockfile pode variar versões transitivas entre ambientes; `npm audit` aponta 16 vulnerabilidades moderadas em dependências transitivas de desenvolvimento (cadeia do ESLint/`minimatch`), sem correção não-quebrável disponível em 03/11/2026; Starlette 1.x emite aviso recomendando `httpx2` no TestClient (aviso filtrado no pytest até avaliação).
- Evidência / testes: `pytest` (15 testes), `ruff check`, `ruff format --check`, `export_openapi.py --check`, `npm run lint`, `format:check`, `typecheck`, `npm test` (4 testes), `npm run build`; smoke de `uvicorn` (`/health`) e `next start`/`next dev` (`/healthz`).
- Documentos e módulos afetados: `docs/CONTRATOS.md` §4–10, `README.md`, `backend/**`, `frontend/**`, `.github/workflows/ci.yml`, `docs/openapi.json`.

## ADR-003 — Representação da recorrência e ocorrências

- Data: 2026-11-03
- Estado: aprovada na integração F1 (revisar em GP-09)
- Contexto: CONTEXTO §2.4/§10 exige recorrência flexível e validável (diária, semanal, mensal, intervalos, último dia do mês), sem enumeração rígida.
- Decisão:
  - `routines.recurrence_rule` (JSONB) guarda o objeto `RecurrenceRule` (`backend/app/modules/routines/recurrence.py`): `frequency` (`daily|weekly|monthly`), `interval` (a cada N), `by_weekday` (semanal), `by_month_day` (mensal; `-1` = último dia; dia inexistente no mês é pulado), `time` (HH:MM local), `timezone` (IANA), `start_date`, `end_date?`, `count?`. Validação por Pydantic; novos campos são aditivos.
  - Geração de ocorrências é função pura e determinística; a API as materializa sob demanda (`occurrences/generate`) e GP-09 passará a gerá-las periodicamente.
  - DST: horário em lacuna usa o offset anterior; horário repetido usa a primeira ocorrência (`fold=0`).
  - Persistência: `routine_occurrences.scheduled_for` é **data local** no fuso da regra; a API expõe o instante UTC reconstruído (data local + `time` + `timezone`). Uma regra tem um horário por dia, logo `(routine_id, scheduled_for)` é único.
  - O formulário web mapeia diário/semanal/intervalo/último dia do mês para essa regra; regras não representáveis no formulário (ex.: vários dias do mês) podem ser criadas via API e só têm o nome editável na web.
- Alternativas consideradas: RRULE (RFC 5545) como texto (expressivo, mas validação e “último dia” menos legíveis, dependência extra); coluna `timestamptz` em `routine_occurrences` (exigiria nova migration sobre schema aplicado sem histórico reconciliado).
- Consequências / riscos: alterar `time`/`timezone` de uma regra reposiciona o horário exibido de ocorrências já materializadas (a data não muda); regras com mais de uma ocorrência por dia não são suportadas.
- Evidência / testes: `backend/tests/modules/test_recurrence.py`, `backend/tests/integration/test_postgres_api.py::test_routine_occurrences_roundtrip`, `frontend/src/lib/recurrence.test.ts`.
- Documentos e módulos afetados: `docs/CONTRATOS.md` §9, `backend/app/db/repos/routines.py`.

## ADR-004 (parcial) — Transação por requisição e idempotência HTTP (integração F1)

- Data: 2026-11-03
- Estado: aprovada para F1; a parte de jobs/retry/backoff do ADR-004 segue pendente (GP-09)
- Decisão: uma conexão/transação PostgreSQL por requisição (`SET LOCAL ROLE app_backend` + claim `sub`), com commit antes do envio da resposta; mutação, auditoria e chave de idempotência atômicas; advisory lock por `(user, key)`. Sem pool de conexões nesta etapa (cada requisição abre uma conexão; ~0,8 s contra o projeto de dev remoto).
- Riscos: latência por conexão (avaliar `psycopg_pool`/pooler em GP-12); chaves de idempotência não expiram (política de retenção pendente).

## Decisões técnicas ainda a registrar

- [x] ADR-002 — Convenções de monorepo, dependências e CI (proposta acima).
- [x] ADR-003 — Formato de recorrência e tratamento de timezone.
- [ ] ADR-004 — Persistência/claim de jobs e retry/backoff (idempotência HTTP: ADR-004 parcial acima).
- [ ] ADR-005 — Proteção e rotação de tokens OAuth Google.
- [ ] ADR-006 — Sequência de migração financeira e desligamento do legado.
- [ ] ADR-007 — Topologia real de deploy, backup e monitoramento.

As entradas acima são **pendências técnicas**, não decisões tomadas.
