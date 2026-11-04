# Frontend — GP-05

Painel web do Sistema de Gestão Pessoal (Next.js 16, TypeScript, Tailwind CSS 4).
Ownership: **GP-05** (ver `docs/CONTRATOS.md`, seção 8).

## Estado atual (integração F1)

- `/`, `/agenda`, `/tarefas`, `/rotinas` e `/configuracoes` exigem acesso. `/login` usa `@supabase/supabase-js` quando `NEXT_PUBLIC_SUPABASE_URL` e `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` estão configuradas.
- **Com sessão Supabase**, as telas usam a API FastAPI real: `src/lib/api/domain.ts` (adaptadores tipados sobre `authenticatedApiFetch`/`ApiError`, `Idempotency-Key` em toda mutação) e `src/components/live-views.tsx` (Hoje, Agenda, Tarefas, Rotinas, Configurações) com loading, estado vazio e erro com nova tentativa. Dados persistem no PostgreSQL e reaparecem ao recarregar.
- **Sem configuração Supabase**, `/login` oferece uma demonstração local explícita, isolada em `src/lib/demo/**` e `workspace-views.tsx` (dados em `localStorage`, banner "Modo de demonstração", nunca enviados à API nem misturados com a conta real).
- Horários: formulários usam o fuso do navegador (`src/lib/time.ts`) e enviam instantes UTC. Prazo de tarefa exige data **e** horário (sem horário presumido); compromisso não tem duração presumida.
- Lacunas documentadas: a API não tem endpoints de perfil nem de preferências de notificação; `LiveSettingsView` informa isso e não salva nada. Integrações Google/WhatsApp indisponíveis.
- Tailwind CSS 4 via `@tailwindcss/postcss`.

## Validação local da GP-05

Em 03/11/2026, com Node 22, os executáveis locais passaram: ESLint sem erros, Prettier `--check`, `next typegen` + `tsc --noEmit`, Vitest (5 arquivos, 16 testes) e `next build` com Turbopack. O smoke de `next start` retornou HTTP 200 em `/healthz`, `/`, `/agenda`, `/tarefas`, `/rotinas`, `/configuracoes` e `/login`. O CSS produzido contém as regras móveis e as classes Tailwind usadas no layout.

No Windows desta sessão, a instalação local precisou omitir pacotes opcionais e depois instalar os binários Windows no `node_modules` sem salvar novas dependências. `node_modules` não é versionado; em outro ambiente, executar `npm ci` normalmente. A revisão visual em navegador e a integração com serviços externos ainda dependem de ambiente apropriado.

## Comandos

```bash
npm ci                    # instalar dependências (Node >= 22)
cp .env.example .env.local
npm run dev               # http://localhost:3000
npm run lint              # ESLint (eslint-config-next)
npm run format:check      # Prettier (npm run format para corrigir)
npm run typecheck         # next typegen + tsc
npm test                  # Vitest
npm run build && npm start
```

Liveness: `GET /healthz`.

## Estrutura

```text
src/
├── app/            # páginas e healthz/route.ts
├── components/     # telas, formulários e testes de interação
└── lib/
    ├── api/        # cliente HTTP e tipos do contrato da API
    └── demo/       # modelo e armazenamento exclusivamente locais
```

- Chamadas autenticadas passam por `authenticatedApiFetch` (`src/lib/auth.ts`), que obtém o JWT da sessão e usa `apiFetch` (`src/lib/api/client.ts`). Respostas de erro seguem `ApiError`.
- Tipos em `src/lib/api/types.ts` espelham `docs/openapi.json`; não duplicar regras de domínio.
- Next.js 16 tem APIs diferentes das versões anteriores: consultar `node_modules/next/dist/docs/`
  (ver `AGENTS.md` desta pasta).

## Roteiro de validação manual (E2E com conta real)

Pré-requisitos: `backend/.env` preenchido; `uvicorn app.main:app --env-file .env` em `backend/` (porta 8000); `npm run dev` em `frontend/` com `.env.local`.

1. Acessar `/agenda` sem sessão: deve mostrar o acesso negado/link para `/login` (sem dados).
2. Entrar em `/login` com a conta A: redireciona para `/` e mostra "Carregando…" e depois o painel.
3. Agenda → "+ Novo compromisso" (título, data, horário; **sem** fim): aparece na lista. Recarregar (F5): continua lá.
4. Editar o horário (reagendar) e depois "Cancelar compromisso": some da agenda.
5. Tarefas → criar com prazo (data **e** horário), editar prioridade, concluir e reabrir; recarregar e conferir.
6. Rotinas → criar (ex.: seg/qua 19:00), marcar "realizada" no dia de hoje; recarregar e conferir o histórico.
7. Parar o backend e recarregar `/tarefas`: deve aparecer a mensagem de erro com "Tentar novamente"; religar e tentar de novo.
8. "Sair": volta a `/login`; voltar ao navegador/abrir `/tarefas` não mostra dados.
9. Entrar com a conta B: nenhum dado da conta A aparece.
