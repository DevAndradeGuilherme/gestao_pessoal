# Tarefas de desenvolvimento — quadro mestre

**Status possíveis:** `não iniciada`, `em execução`, `bloqueada`, `em revisão`, `concluída`.  
**Situação:** GP-01 e GP-02 `em revisão`; GP-03, GP-04 e GP-05 `em revisão` (integradas em `integrate/f1-core`; JWT real e E2E manual aprovados; aguardam CI e revisão do PR); demais `não iniciada`.  
**Regra:** os itens abaixo são escopos para futuros prompts, **não prompts de implementação**.

| ID    | Fase | Entrega agrupada                                              | Agente / modelo recomendado               | Dependências              | Ação manual antes                                                     | Status       |
| ----- | ---- | ------------------------------------------------------------- | ----------------------------------------- | ------------------------- | --------------------------------------------------------------------- | ------------ |
| GP-01 | F0   | Bootstrap Git, estrutura e regras dos agentes                 | Claude Code / Sonnet                      | —                         | Confirmar clone e acesso de escrita                                   | em revisão   |
| GP-02 | F0   | Contratos, skeletons, ferramentas de teste e CI mínimo        | Claude Code / Sonnet                      | GP-01                     | Nenhuma, salvo escolha de runner CI                                   | em revisão   |
| GP-03 | F1   | Schema, migrations, RLS e autenticação                        | Codex / medium                            | GP-02                     | Provisionar Supabase e configurar segredos localmente                 | em revisão   |
| GP-04 | F1   | Backend de domínio + CRUD de compromissos, tarefas e rotinas  | Claude Code / Sonnet                      | GP-02 e contratos GP-03   | Nenhuma para mocks; acesso DB para integração real                    | em revisão   |
| GP-05 | F1   | Frontend de agenda, tarefas, rotinas e perfil                 | Codex / medium                            | GP-02; contratos GP-03/04 | Nenhuma para implementação local                                      | em revisão   |
| GP-06 | F2   | Integração Google Calendar, OAuth, sync e reconciliação       | Codex / medium                            | GP-03/04                  | Criar/configurar OAuth no Google Cloud                                | não iniciada |
| GP-07 | F2   | Canal WhatsApp, webhook seguro, autorização e respostas       | Claude Code / Sonnet                      | GP-03/04                  | Disponibilizar Evolution API e emparelhar WhatsApp                    | não iniciada |
| GP-08 | F2   | Interpretador OpenAI estruturado, ambiguidades e orquestração | Codex / medium                            | GP-04/07 (interface)      | Configurar API key OpenAI e limite de gasto                           | não iniciada |
| GP-09 | F3   | Celery/Redis, agendamentos, lembretes, resumos e recorrência  | Codex / medium                            | GP-03/04/07               | Nenhuma para testes locais; Redis no ambiente de execução             | não iniciada |
| GP-10 | F3   | Migração financeira progressiva + testes de regressão         | Claude Code / Sonnet (Opus se necessário) | GP-04                     | Acesso leitura ao repositório financeiro; aprovar migrações com risco | em revisão   |
| GP-11 | F4   | Integração ponta a ponta, QA, segurança, RLS e falhas         | Codex / high quando necessário            | GP-05 a GP-10             | Disponibilizar contas/ambiente de homologação                         | não iniciada |
| GP-12 | F4   | Infra, deploy VPS, backups, observabilidade e aceite final    | Claude Code / Sonnet                      | GP-11                     | VPS, DNS, segredos e aprovação explícita do deploy                    | não iniciada |

## Escopo e critério de aceite por tarefa

### GP-01 — Fundação do repositório

- Entregar layout inicial sem lógica de negócio, regras de contribuição, scripts base compatíveis com a estrutura criada.
- Aceite: repositório clonável, documentação indexada, sem segredos, branch de trabalho pronta.

### GP-02 — Contratos, skeletons e CI

- Estabelecer contrato inicial entre web/API, organização dos módulos, contratos de autenticação/erros e estrutura mínima de testes e CI.
- Aceite: contratos registrados em `docs/CONTRATOS.md`, checks básicos executáveis; nenhum endpoint fictício apresentado como implementado.
- Registro (GP-01 + GP-02 consolidadas): Claude Code, branch `lobster`, 03/11/2026. Entregues skeletons `frontend/` e `backend/`, contratos `docs/CONTRATOS.md` §4–10, `docs/openapi.json`, CI `.github/workflows/ci.yml` e ADR-002. Evidência: pytest 15/15, Ruff ok, OpenAPI `--check` ok, ESLint/Prettier/tsc ok, Vitest 4/4, `next build` ok, smoke local de `/health` e `/healthz`. Pendente: primeira execução do CI no GitHub e aprovação do integrador.

### GP-03 — Banco e autenticação

- Modelar usuários, compromissos, tarefas, rotinas, ocorrências, lembretes, eventos recebidos e auditoria conforme contexto; Supabase Auth e isolamento.
- Aceite: migrations reproduzíveis, testes RLS/autorização e configuração segura de segredos.

### GP-F1-INT — Integração da Fase 1 (branch `integrate/f1-core`, 03/11/2026, Claude Code)

- Entregue: merge sem conflitos de GP-03, GP-04 e GP-05; adaptadores PostgreSQL (`backend/app/db/repos/`) ligados por `get_stores` (transação por requisição, RLS, auditoria e idempotência atômicas, fail-closed); frontend consumindo a API (`src/lib/api/domain.ts`, `src/components/live-views.tsx`); `docs/CONTRATOS.md`, ADR-003/ADR-004 parcial, `docs/openapi.json`.
- Testes automatizados (04/11/2026): backend 147 passed/0 skipped, incluindo PostgreSQL real e `tests/integration/test_real_jwt.py` (4/4: token real aceito, isolamento A/B, token adulterado/expirado/corrompido, HS256 e `alg=none` rejeitados com 401); frontend: ESLint, Prettier, tsc, Vitest 33/33 e `next build`.
- Validação manual E2E (executada pelo usuário no navegador, com contas reais; **não automatizada**): 9/9 aprovados. (1) login Supabase; (2) criar compromisso; (3) persistência após recarregar; (4) reagendar e cancelar; (5) criar e editar tarefa; (6) concluir e reabrir tarefa; (7) criar e acompanhar rotina; (8) painel Hoje com dados persistidos; (9) logout e proteção das páginas. Não há suíte E2E de navegador automatizada.
- **Status da Fase 1:** funcionalmente completa e validada; `em revisão` até CI verde e aprovação do PR.
- Limitações conhecidas: sem endpoints de perfil/preferências (tela de configurações informativa); listas do frontend limitadas a 200 itens; chaves de idempotência sem expiração; latência de ~0,8 s/requisição ao banco remoto (RTT ≈ 265 ms; pool aplicado; API na mesma região em GP-12); alterar horário/fuso de rotina reposiciona o horário de ocorrências já materializadas; sem E2E de navegador automatizado.
- **Pendência obrigatória antes de novas migrations:** reconciliar o histórico `supabase_migrations` (`supabase migration repair --status applied 202611030001`, ver `supabase/README.md`). Não executar `supabase db push`. Primeira execução do CI no GitHub: ver PR.

### GP-04 — Domínio e API

- Criar/consultar/editar/cancelar compromissos; criar/concluir/reabrir tarefas; definir/consultar rotinas; regras de validação, timezone e auditoria.
- Aceite: testes de domínio e integração local, autorização por usuário, API compartilhável por web/WhatsApp, sem duração padrão de produto.

### GP-05 — Frontend

- Dashboard Hoje, agenda, tarefas/rotinas, configurações, estados de sync e autenticação.
- Aceite: navegação funcional, erros e loading, acessibilidade básica, ações persistidas via API, responsividade mínima.

### GP-06 — Google Agenda

- OAuth 2.0, proteção de tokens, criação/alteração/cancelamento de eventos, estados de sync e retentativas sem duplicar eventos.
- Aceite: teste de integração real quando autorizado; sync somente sistema → Google; tarefas apenas com opção explícita.

### GP-07 — WhatsApp

- Instância pessoal Evolution API, validação de webhook, deduplicação, remetente autorizado, envio/recebimento e respostas.
- Aceite: mensagem duplicada não duplica operação; confirmação apenas após persistência; reconexões e falhas cobertas.

### GP-08 — IA híbrida

- Interpretação estruturada de mensagens, intenções, desambiguação, validação final FastAPI e testes com exemplos em português.
- Aceite: nenhuma ação direta da IA no DB; ambiguidades pedem esclarecimento; rastreamento de qualidade/custo básico.

### GP-09 — Automações

- Persistir agendamentos, executar via Celery/Redis, retries, idempotência, horários de silêncio, recorrência flexível, resumos 07h/23h configuráveis.
- Aceite: restart não perde jobs; não duplica lembrete; mudanças/cancelamentos revogam agendamentos; status não muda sozinho.

### GP-10 — Finanças

- **Primeiro** inventariar capacidades/testes do Django real, definir ordem e contrato de migração; depois migrar o primeiro conjunto aprovado e preparar continuidade.
- Aceite: capacidade migrada com testes de regressão, uma só implementação ativa por regra, rollback documentado; escopo remanescente explicitado. Se exceder um prompt, dividir sem sacrificar regressão.

### GP-11 — Validação final

- E2E para fluxos da seção 9 do contexto, auth/RLS, idempotência, falhas externas, concorrência e auditoria.
- Aceite: matriz de cobertura ligada a cada critério, erros impeditivos corrigidos e limitações documentadas.

### GP-12 — Deploy

- Containers/serviços, proxy TLS, logs, reinício, backup, variáveis seguras, health checks e publicação controlada.
- Aceite: ambiente real funcional, restore/backups testados quando viável, observabilidade mínima e checklist de aceite aprovado pelo usuário.

## Regras de atualização

- Ao iniciar: registrar responsável, branch e data da atualização neste arquivo (ou no PR correspondente).
- Ao finalizar: incluir evidência de testes/PR/commit e atualizar status.
- Ao bloquear: descrever o bloqueio e a ação humana necessária.
- Não marcar como concluída com credenciais falsas, mocks usados como prova externa ou funcionalidades apenas descritas.
