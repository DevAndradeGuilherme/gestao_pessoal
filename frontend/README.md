# Frontend — Next.js

Painel web do Sistema de Gestão Pessoal (Next.js 16, TypeScript, Tailwind CSS 4).
Ownership: **GP-05** (ver `docs/CONTRATOS.md`, seção 8).

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
