# GP-03 schema e autenticação

## Status para integração

Migration aplicada no projeto exclusivo de desenvolvimento; testes reais de PostgreSQL, RLS e idempotência: 18 aprovados, 0 falhos, 0 ignorados. Pendências: validar um JWT real emitido pelo Supabase e reconciliar o histórico da migration em `supabase_migrations` antes de qualquer `supabase db push`. O integrador deve registrar `PyJWT[crypto]` e `psycopg[binary]` nas dependências Python do backend.

## Aplicação e reversão

Migration versionada: `migrations/202611030001_gp03_core.sql`. Aplicar em um projeto Supabase **novo ou isolado** com Supabase CLI (`supabase db push`) após revisar o diff de migração. Para testes, provisionar um projeto local/descartável, aplicar a migration e criar dois usuários via Supabase Auth. A migration cria tabelas, papel `app_backend`, políticas RLS e trigger de perfil. Não existe seed de usuário nem alteração no domínio financeiro.

No projeto de desenvolvimento validado em 03/11/2026, esta migration foi aplicada diretamente em uma transação PostgreSQL porque a Supabase CLI não estava instalada. Esse método não criou `supabase_migrations.schema_migrations`; antes de usar `supabase db push` nesse projeto, reconciliar o histórico de migrations com o schema já aplicado para evitar uma segunda execução.

Reversão: preferir restaurar snapshot anterior do projeto de teste. Em ambiente com dados, gerar migration compensatória revisada pelo integrador; `DROP TABLE ... CASCADE` perderia dados e não é fornecido como rollback automático. Não executar reversão destrutiva em ambiente compartilhado.

## Configuração do backend

- `SUPABASE_URL`: origem HTTPS do projeto, sem caminho; define o issuer e o endpoint JWKS.
- `DATABASE_URL`: string PostgreSQL **somente no backend**, para papel `postgres` autorizado a `SET ROLE app_backend`. Nunca enviar ao frontend. A função `user_transaction(CurrentUser)` executa `SET LOCAL ROLE app_backend` e injeta `request.jwt.claim.sub` na transação.
- Para os testes de RLS: `GP03_TEST_DATABASE_URL`, `GP03_TEST_USER_A` e `GP03_TEST_USER_B`, apontando exclusivamente para banco descartável com migration aplicada e dois usuários Supabase Auth existentes.

O backend aceita apenas JWTs Supabase Auth assimétricos `RS256` ou `ES256`. O JWKS do projeto de desenvolvimento foi consultado em 03/11/2026 e a chave ativa `ES256` foi interpretada pelo PyJWT com `cryptography`. A validação ponta a ponta de um token emitido pelo Supabase ainda não foi executada. Projetos legados `HS256` exigem decisão do integrador: migrar para chaves assimétricas ou aprovar outro verificador seguro. Sem configuração, a API devolve 401.

## Contrato de persistência para GP-04 e GP-05

- `profiles.id = auth.users.id`; trigger cria perfil e preferências ao criar usuário. Timezone IANA em `profiles.timezone` (default `America/Sao_Paulo`).
- `appointments`: `starts_at` obrigatório, `ends_at` anulável, `status` = `scheduled|cancelled|completed`, `sync_status` = `not_applicable|pending|synced|failed` (default `pending`). Não há duração padrão.
- `tasks`: `due_at` anulável, `status` = `pending|completed|cancelled`, `completed_at` somente quando concluída, `sync_to_calendar=false` e `sync_status=not_applicable` por padrão. Google depende de escolha explícita.
- `routines.recurrence_rule` é JSON objeto não vazio; sintaxe e validação semântica pertencem a GP-04/GP-09. `routine_occurrences.scheduled_for` é data local; status `pending|completed|skipped`.
- `reminders` referencia exatamente um item por FK composta com `user_id`; chave única `(user_id,idempotency_key)`. `message_events` deduplica `(provider,provider_message_id,direction)`.
- `integrations` guarda só `credential_ref`, nunca token OAuth em texto. A escolha de cofre/criptografia cabe à GP-06.
- `idempotency_keys` usa PK `(user_id,key)`, hash SHA-256 de método+caminho+payload e resposta JSON; `execute_once` deve rodar dentro de `user_transaction` e recebe uma operação que usa a mesma conexão.
- `backend/app/auth/dependencies.py`: `get_current_user`/`CurrentUserDep` fornecem `CurrentUser(id: UUID, channel='web')`; 401 para token ausente/inválido. Web e WhatsApp usam o mesmo serviço de domínio; GP-07 resolverá identidade WhatsApp separadamente.
- `backend/app/db/session.py`: `user_transaction(CurrentUser)` é o contexto transacional para repositórios GP-04. Repositórios ainda devem filtrar `user_id` em toda consulta/mutação; retornar 404 se o registro for invisível.

Tabelas privadas não têm privilégios para `anon`/`authenticated` via Data API; o frontend usa FastAPI. Mesmo com `FORCE RLS`, `service_role` e outras conexões `BYPASSRLS` podem enxergar todos os usuários. Nunca consultar dados privados antes de `SET LOCAL ROLE app_backend`.

## Reconciliação do histórico de migrations (não executada)

**Evidência (consulta somente leitura em 03/11/2026, projeto de desenvolvimento):** o schema `supabase_migrations` **não existe**; as 11 tabelas de `public`, `FORCE RLS`, as políticas `owner_only`/`*_bootstrap`, o papel `app_backend` (sem `BYPASSRLS`) e o trigger `on_auth_user_created` estão presentes, isto é, o conteúdo de `202611030001_gp03_core.sql` já está aplicado, mas **sem registro**. Um `supabase db push` tentaria reaplicar a migration e falharia (ou, pior, duplicaria objetos parcialmente).

**Procedimento seguro (a executar por humano, com a Supabase CLI instalada e `supabase link` no projeto de dev):**

1. Não rodar `supabase db push` nem `supabase db reset` neste projeto.
2. Confirmar o estado: `supabase migration list` (remoto vazio, local com `202611030001`) e comparar `supabase db diff --linked` com o arquivo; o diff deve ser vazio para os objetos da migration.
3. Se vazio, registrar sem executar SQL: `supabase migration repair --status applied 202611030001`. Isso cria `supabase_migrations.schema_migrations` e a linha da versão.
4. Reexecutar `supabase migration list` (local e remoto iguais) e `supabase db push --dry-run` (deve informar "Remote database is up to date").
5. Se o diff não for vazio, **parar**: gerar migration compensatória revisada pelo integrador; não editar a migration já versionada.
6. Para qualquer novo projeto (staging/produção), aplicar normalmente com `supabase db push` desde o início.

## Solicitação ao integrador (atendida na integração F1)

`PyJWT[crypto]` e `psycopg[binary]` estão em `backend/pyproject.toml`; `SUPABASE_URL`/`DATABASE_URL` em `backend/.env.example`; estratégia registrada em `docs/CONTRATOS.md` §5 e `docs/DECISOES.md` (ADR-003/ADR-004 parcial). Pendente: validar o tipo de chave de assinatura no dashboard do projeto gerenciado (o JWKS de dev serve `ES256`).

### Texto original da solicitação

Adicionar `PyJWT[crypto]` e `psycopg[binary]` ao `backend/pyproject.toml`; adicionar nomes `SUPABASE_URL` e `DATABASE_URL` sem valores ao `backend/.env.example`. Registrar esta estratégia de JWT, migrations, RLS e idempotência em `docs/CONTRATOS.md` e `docs/DECISOES.md`. Confirmar o tipo de chave de assinatura no dashboard/JWKS do Supabase e validar o papel de conexão no projeto gerenciado. Publicar este resumo aos agentes GP-04 e GP-05.
