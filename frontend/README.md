# Frontend — GP-05

Painel web do Sistema de Gestão Pessoal (Next.js 16, TypeScript, Tailwind CSS 4).
Ownership: **GP-05** (ver `docs/CONTRATOS.md`, seção 8).

## Estado atual

- `/`, `/agenda`, `/tarefas`, `/rotinas` e `/configuracoes` exigem acesso. `/login` usa o cliente oficial `@supabase/supabase-js` quando `NEXT_PUBLIC_SUPABASE_URL` e `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` estão configuradas.
- Sem configuração Supabase, `/login` oferece uma demonstração local explícita. Os registros ficam em `localStorage` e são isolados em `src/lib/demo/**`; não são enviados à API nem representam schemas Pydantic. Não use dados privados reais nesse modo.
- Com uma sessão Supabase válida, as telas autenticadas mostram a pendência da API de domínio, sem misturar os dados locais da demonstração com a conta real.
- `src/lib/auth.ts` prepara chamadas autenticadas via `apiFetch` com `Authorization: Bearer <access_token>`. O cliente HTTP mantém o envelope `ApiError` de GP-02.

## Contratos para conectar GP-05

GP-04 deve publicar no OpenAPI as rotas, schemas, filtros e ações de estado de compromissos, tarefas, rotinas e ocorrências. A interface requer criar, listar por intervalo/paginação, editar, cancelar compromisso, concluir/reabrir tarefa e registrar realização/não realização de ocorrência. `ends_at` deve continuar opcional; a opção de sincronização de tarefa deve ser explícita. Confirmar estados de `sync_status`, forma de recorrência e histórico. GP-03 deve confirmar o JWT aceito pela API e schemas de perfil, timezone e preferências. Integrações Google/WhatsApp dependem de tarefas posteriores.

Ao publicar os contratos, criar um adaptador de domínio em `src/lib/api/` usando os tipos reais do OpenAPI, `authenticatedApiFetch` e `ApiError`; conectar as telas a ele e executar testes com a API. Nenhuma rota de domínio é assumida nesta branch.

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
├── app/            # rotas (App Router); healthz/route.ts
└── lib/api/        # cliente HTTP e tipos do contrato da API
```

- Toda chamada à API passa por `apiFetch` (`src/lib/api/client.ts`), que envia o JWT
  do Supabase como `Authorization: Bearer` e converte erros no envelope `ApiError`.
- Tipos em `src/lib/api/types.ts` espelham `docs/openapi.json`; não duplicar regras de domínio.
- Next.js 16 tem APIs diferentes das versões anteriores: consultar `node_modules/next/dist/docs/`
  (ver `AGENTS.md` desta pasta).
