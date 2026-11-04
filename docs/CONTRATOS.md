# Contratos técnicos compartilhados

**Estado:** contratos iniciais aprovados em GP-02 (03/11/2026). Seções 1–3 definem semântica; seções 4–10 definem formatos e fronteiras técnicas.
**Implementado (integração F1, branch `integrate/f1-core`):** health checks, envelope de erro, `X-Request-ID`, autenticação por JWT Supabase (JWKS), persistência PostgreSQL com RLS, idempotência, auditoria e as rotas de compromissos, tarefas e rotinas listadas na seção 9. Perfil, preferências e integrações **não** têm endpoints.

## 1. Responsabilidades dos canais

- Web e WhatsApp enviam comandos/consultas para a mesma API FastAPI.
- O backend identifica o usuário autenticado/autorizado, valida entradas, efetua transações e informa resultado.
- Modelos OpenAI somente devolvem proposta estruturada de intenção e parâmetros, sem permissões para mutação.
- Mensagens de confirmação devem separar “registrado localmente” de “sincronizado externamente”.

## 2. Conceitos de domínio

| Conceito | Regras essenciais |
|---|---|
| Compromisso | `starts_at` obrigatório quando com hora; `ends_at` não presumido; sync Google vinculada à conexão |
| Tarefa | pode ter `due_at`; conclusão explícita com instante; sincronização Google opcional e explícita |
| Rotina | regra de recorrência flexível e validável; ocorrências possuem status independente |
| Lembrete | agendado em DB, vinculado ao item e ao usuário; chave de idempotência |
| Evento de mensagem | deduplicação por identificador do provedor e identificação do remetente |
| Preferências | timezone do usuário, resumo matinal 07:00, revisão 23:00, silêncio 00:00–07:00, defaults configuráveis |

## 3. Contratos de comportamento

- Criar compromisso: persistir no Supabase, produzir status de sincronização, tentar sincronizar no Google, evitar duplicidades.
- Reagendar/cancelar: registrar alteração; invalidar lembretes antigos e atualizar integração externa com retry seguro.
- Concluir tarefa/rotina: marcar somente por comando humano válido, com histórico.
- Resumo matinal/noturno: compor com dados persistidos e registrar envio único por usuário/período.
- Mensagem ambígua: perguntar antes de persistir operação irreversível.
- Falha externa: manter registro local, expor falha/pendência e reconciliar.

## 4. Convenções da API HTTP

- **Base versionada:** `/api/v1`. Mudança incompatível exige `/api/v2` ou janela de transição registrada em `docs/DECISOES.md`. Health checks ficam fora da versão (`/health`).
- **Recursos:** substantivos em inglês, plural, `kebab-case`, alinhados aos nomes do `CONTEXTO.md` §5 (ex.: `/api/v1/appointments`, `/api/v1/tasks/{task_id}`). Rotas concretas são definidas por GP-04.
- **Ações de estado** que não são edição simples usam sub-recurso verbal: `POST /api/v1/tasks/{task_id}/complete`, `.../reopen`, `.../cancel` (exemplos; GP-04 confirma). Cancelamento é transição de estado com histórico, **não** exclusão física.
- **Métodos:** `GET` leitura, `POST` criação/ação, `PATCH` atualização parcial, `DELETE` apenas quando a exclusão real for permitida pelo domínio.
- **JSON:** campos em `snake_case` em request e response (o frontend não converte para camelCase).
- **Identificadores:** UUID em string. Identificadores externos (`google_event_id`, `provider_message_id`) nunca substituem o `id` interno.
- **Instantes:** ISO 8601 **com offset** na entrada (ex.: `2026-11-03T14:00:00-03:00`); horários sem offset são rejeitados com `422`. Persistência em UTC; respostas em UTC (`Z`). O cliente exibe no fuso IANA do perfil (ex.: `America/Sao_Paulo`).
- **Datas sem hora:** `YYYY-MM-DD`, interpretadas no fuso do usuário.
- **Duração:** `ends_at` é opcional e `null` quando não informado. **Nenhuma camada preenche fim ou duração por padrão**; restrições do Google são tratadas apenas no adaptador da integração (GP-06), sem alterar o registro de domínio.
- **Nulos em `PATCH`:** campo ausente = não alterar; `null` explícito = limpar (quando o campo for anulável).
- **Valores monetários (GP-10):** decimal serializado como string (ex.: `"123.45"`), nunca float.
- **Idempotência:** `POST` de criação/ação aceita o header `Idempotency-Key` (string de até 128 caracteres). Mesma chave + mesmo payload ⇒ mesma resposta, sem nova mutação; mesma chave + payload diferente ⇒ `409 idempotency_conflict`. Obrigatório para operações originadas no WhatsApp (chave derivada do `provider_message_id`). Armazenamento: GP-03; aplicação: GP-04.
- **Correlação:** todo request aceita `X-Request-ID` (`[A-Za-z0-9._-]{1,128}`); o backend gera UUID4 quando ausente/inválido e devolve o header em toda resposta. *(implementado)*

## 5. Autenticação e identidade

**Web (Supabase Auth → FastAPI)**

1. O frontend autentica com Supabase Auth (cliente oficial, GP-05) e mantém a sessão/refresh no navegador.
2. Toda chamada à API envia `Authorization: Bearer <access_token do Supabase>`.
3. O backend valida o JWT localmente: assinatura (chaves de assinatura/JWKS do projeto Supabase — mecanismo exato confirmado em GP-03), `exp`, `aud = "authenticated"` e `iss = <SUPABASE_URL>/auth/v1`.
4. `sub` vira `CurrentUser.id` (`backend/app/auth/models.py`). **`user_id` nunca é aceito do corpo, query ou path** para fins de autorização.
5. O backend não emite tokens próprios nem guarda refresh tokens do usuário.

**WhatsApp (GP-07)**

- O webhook da Evolution API não usa JWT de usuário. A origem é validada por segredo/mecanismo do provedor; o remetente (E.164 normalizado) é mapeado para o perfil autorizado e convertido em `CurrentUser(channel="whatsapp")`. Remetente desconhecido não gera operação de domínio.

**Regras comuns**

- Serviços de domínio recebem `CurrentUser` explicitamente; não leem headers nem conhecem detalhes do canal.
- Repositórios filtram por `user_id` **mesmo com RLS ativo** (defesa em profundidade). Chave `service_role` só no backend, nunca no frontend nem em logs.
- Semântica de erro: sem credencial/credencial inválida ⇒ `401 unauthenticated`; autenticado sem permissão para a ação ⇒ `403 forbidden`; recurso de outro usuário ⇒ `404 not_found` (não revela existência).
- **Implementado:** `get_current_user` (`backend/app/auth/dependencies.py`) valida o JWT com `PyJWT[crypto]`: assinatura **RS256/ES256 via JWKS** (`<SUPABASE_URL>/auth/v1/.well-known/jwks.json`, cache 10 min), `exp`, `aud="authenticated"`, `iss=<SUPABASE_URL>/auth/v1`, `role="authenticated"`, `sub` UUID. Tokens `HS256`/assinatura inválida ⇒ 401. Sem `SUPABASE_URL` ⇒ 401 (fail-closed). Testes unitários usam `app.dependency_overrides[get_current_user]`.
- **Persistência:** `get_stores` (`modules/common/deps.py`) abre **uma transação PostgreSQL por requisição** (`app/db/session.py`: `SET LOCAL ROLE app_backend` + `request.jwt.claim.sub`, RLS `FORCE`). Entidade, `activity_log` (auditoria) e `idempotency_keys` são confirmados **juntos** antes da resposta (`Depends(..., scope="function")`). Banco ausente/indisponível ou falha de commit ⇒ `503 service_unavailable` sem detalhes do driver; nada é gravado em memória (os fakes `InMemory*` existem apenas em testes). Adaptadores: `backend/app/db/repos/`.
- **Idempotência (implementado):** `Idempotency-Key` em `POST`/`PATCH` de compromissos, tarefas e rotinas e nas ações de ocorrência. Chave por `(user_id, key)` com hash de escopo+payload; requisições concorrentes com a mesma chave são serializadas por `pg_advisory_xact_lock`; só respostas de sucesso são armazenadas. `POST .../occurrences/generate` é idempotente por natureza (unicidade `(routine_id, scheduled_for)`).

## 6. Respostas, paginação e erros

**Sucesso**

| Situação | Status | Corpo |
|---|---|---|
| Leitura de recurso / atualização | `200` | recurso (`<Recurso>Read`), sem envelope |
| Criação | `201` | recurso criado |
| Ação sem conteúdo | `204` | vazio |
| Listagem | `200` | `Page<T>` |

**Paginação** (`backend/app/core/schemas.py`): query `limit` (1–200, padrão 50) e `offset` (≥ 0); resposta `{"items": [...], "limit": 50, "offset": 0, "total": 123}`. Filtros em query `snake_case`; intervalos usam `<campo>_from` / `<campo>_to`, semiaberto `[from, to)`. Ordenação padrão definida por recurso e documentada no OpenAPI.

**Erros** (`backend/app/core/errors.py`) — toda resposta não-2xx da API usa:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Os dados enviados são inválidos.",
    "details": [{ "field": "body.starts_at", "message": "Field required", "type": "missing" }],
    "request_id": "9cda3bc1-40f8-42e0-8920-78f67d7bbcdb"
  }
}
```

| `code` | HTTP | Uso |
|---|---|---|
| `validation_error` | 422 | Schema/valor inválido; `details[]` por campo (`field` = caminho pontuado `body.x`, `query.y`) |
| `bad_request` | 400 | Requisição malformada fora da validação de schema |
| `unauthenticated` | 401 | Token ausente, inválido ou expirado |
| `forbidden` | 403 | Autenticado sem permissão |
| `not_found` | 404 | Rota ou recurso inexistente/inacessível |
| `method_not_allowed` | 405 | Método não suportado |
| `conflict` | 409 | Conflito de estado (ex.: concluir tarefa cancelada) |
| `idempotency_conflict` | 409 | `Idempotency-Key` reutilizada com payload diferente |
| `rate_limited` | 429 | Limite de taxa |
| `external_service_error` | 502 | Falha de integração que impede a operação solicitada |
| `service_unavailable` | 503 | Dependência obrigatória indisponível |
| `internal_error` | 500 | Erro inesperado; mensagem genérica, detalhes só no log |

- Clientes decidem pelo `code`, **nunca** pelo texto de `message` (texto em pt-BR, voltado a humanos).
- Novos códigos exigem atualização desta tabela, de `ErrorCode` no backend e de `frontend/src/lib/api/types.ts`.
- Falha de sincronização externa **não** é erro da operação local: o recurso é salvo e retornado com `sync_status` indicando pendência/falha (CONTEXTO §7.2).
- **Validação:** Pydantic no backend é a autoridade. O frontend pode validar para UX, mas não substitui nem diverge da validação do servidor.

## 7. Schemas compartilháveis

- **Fonte de verdade:** modelos Pydantic no backend.
- **Artefato publicado:** `docs/openapi.json`, gerado por `python backend/scripts/export_openapi.py`. O CI falha se o arquivo estiver desatualizado (`--check`). Contém hoje `HealthResponse`, `ErrorResponse`, `ErrorBody`, `ErrorDetail` e `ErrorCode`.
- **Frontend:** `frontend/src/lib/api/types.ts` espelha manualmente os schemas comuns (`ErrorResponse`, `ErrorCode`, `Page<T>`, `HealthResponse`). GP-05 pode adotar geração automática a partir de `docs/openapi.json` (ex.: `openapi-typescript`) registrando a dependência em `docs/DECISOES.md`.
- **Enum de sincronização (proposta, GP-03 confirma no schema):** `sync_status ∈ {not_applicable, pending, synced, failed}`.
- Nomes de schema: `<Recurso>Create`, `<Recurso>Update`, `<Recurso>Read`; listas como `Page[<Recurso>Read]`.

## 8. Fronteiras e ownership de arquivos (F1)

Escrita exclusiva por tarefa; arquivos de outro dono só mudam por pedido ao integrador.

| Área | Dono | Caminhos |
|---|---|---|
| Integrador (raiz e contratos) | integrador | `CONTEXTO.md`, `docs/CONTRATOS.md`, `docs/DECISOES.md`, `docs/openapi.json`, `.github/**`, `README.md`, `backend/pyproject.toml`, `backend/README.md`, `backend/app/main.py`, `backend/app/core/**`, `backend/app/api/health.py`, `backend/scripts/**`, `backend/.env.example` |
| GP-03 — dados/auth | GP-03 | `supabase/**` (migrations, RLS, seeds), `backend/app/db/**`, `backend/app/auth/**`, `backend/tests/db/**`, `backend/tests/auth/**` |
| GP-04 — domínio/API | GP-04 | `backend/app/modules/**`, `backend/app/api/router.py` (registro de routers), `backend/tests/modules/**` |
| GP-05 — frontend | GP-05 | `frontend/**` (inclui `package.json`, lockfile e `frontend/.env.example`) |

Regras de coordenação:

- GP-04 começa com repositórios atrás de interfaces e fakes em memória, e `get_current_user` sobrescrito em testes; conecta ao schema real quando GP-03 publicar as migrations.
- GP-05 começa com mocks tipados a partir desta seção e do OpenAPI; não inventa campos ausentes do contrato.
- Novas dependências Python, variáveis de ambiente ou códigos de erro: a tarefa propõe, o integrador aplica em `pyproject.toml`/`.env.example`/`core`.
- Schema de banco: somente GP-03 cria migrations em F1. Necessidade de campo por GP-04 é pedida a GP-03 via integrador.
- Toda mudança de rota/schema exposto regenera `docs/openapi.json` no mesmo PR.

## 9. Endpoints implementados

Liveness: `GET /health` (API; não consulta banco) e `GET /healthz` (Web). Rotas de domínio exigem `Authorization: Bearer <JWT Supabase>`; schemas completos em `docs/openapi.json`.

| Método e rota | Descrição |
|---|---|
| `POST /api/v1/appointments`, `GET /api/v1/appointments` | Criar; listar (`starts_at_from`, `starts_at_to` semiaberto, `status`, `limit`, `offset`) |
| `GET/PATCH /api/v1/appointments/{id}` | Ler; editar título/descrição/local |
| `POST /api/v1/appointments/{id}/reschedule` | Reagendar (`starts_at`, `ends_at?`; fim ausente limpa o anterior) |
| `POST /api/v1/appointments/{id}/cancel` | Cancelar (transição de estado, `reason?`) |
| `POST/GET /api/v1/tasks` | Criar; listar (filtros em `openapi.json`) |
| `GET/PATCH /api/v1/tasks/{id}` | Ler; editar |
| `POST /api/v1/tasks/{id}/complete`, `/reopen`, `/cancel` | Concluir (`completed_at?`), reabrir, cancelar |
| `POST/GET /api/v1/routines`, `GET/PATCH /api/v1/routines/{id}` | Criar; listar (`active`); ler; editar título/regra |
| `POST /api/v1/routines/{id}/activate`, `/deactivate` | Ativar/desativar |
| `POST /api/v1/routines/{id}/occurrences/generate` | Materializa ocorrências `pending` em `[window_start, window_end)` (até 366 dias) |
| `GET /api/v1/routines/{id}/occurrences` | Lista (`scheduled_for_from/to`, `status`) |
| `POST /api/v1/routines/{id}/occurrences/{oid}/complete`, `/skip`, `/reopen` | Registro explícito do resultado |

**Representação de ocorrências:** `scheduled_for` é instante UTC na API e **data local** (`date`) no banco; ver ADR-003. `sync_status` de compromisso é `pending` ao criar (Google ainda não implementado); `sync_to_calendar` de tarefa só é verdadeiro por escolha explícita.

**Lacunas:** não há endpoints de perfil (`profiles`), `notification_preferences` nem `integrations`; o frontend exibe o fuso detectado no navegador e informa a indisponibilidade. Não há endpoint de leitura da auditoria (gravada em `activity_log`).

## 10. Contratos ainda abertos

- [x] JWT Supabase (JWKS assimétrico RS256/ES256) e papel `app_backend` com RLS (validação com token real: ver `docs/TAREFAS.md`).
- [x] Migrations, RLS e idempotência (reconciliação do histórico de migrations pendente: `supabase/README.md`).
- [x] Rotas, schemas e filtros de compromissos, tarefas e rotinas (seção 9).
- [x] Representação de recorrência (ADR-003). Semântica de DST na execução assíncrona: GP-09.
- [ ] Endpoints de perfil e preferências de notificação.
- [ ] Comandos/eventos de integração, outbox ou equivalente e `sync_status` final — **GP-03/GP-06**.
- [ ] Schemas de interpretação de IA, estados de conversação e desambiguação — **GP-08**.
- [ ] Payloads internos dos workers e política de retries — **GP-09** (ADR-004).
- [x] Convenções de rota/versão, respostas, paginação, erros, identidade e ownership — **GP-02**.

## 11. Política de alteração

O agente que necessitar alterar um contrato registra **proposta, impacto, testes e consumidores afetados**, solicita coordenação ao integrador e só depois edita a implementação. Não permitir alterações independentes de schema por múltiplos agentes no mesmo intervalo.

Versionamento: mudanças aditivas (novo campo opcional, novo endpoint) entram em `/api/v1` com atualização deste arquivo e do OpenAPI; mudanças incompatíveis exigem ADR e plano de transição.
