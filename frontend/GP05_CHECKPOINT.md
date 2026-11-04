# GP-05 — checkpoint antes da reinicialização

Data: 03/11/2026 (America/Sao_Paulo). Branch: `feat/gp-05-frontend`. Worktree: `C:\gestao-gp05`.

## Funcionalidades já implementadas em código

- Rotas de Hoje, Agenda, Tarefas, Rotinas, Configurações e Login.
- Acesso protegido no cliente: sessão Supabase quando configurado; demonstração local explícita quando não configurado.
- Interface responsiva em português com estados vazios, carregamento e feedback local.
- Demonstração isolada em `src/lib/demo/**`, persistida em `localStorage`: criação/edição/cancelamento de compromissos; tarefas com filtros, conclusão e reabertura; rotinas com recorrências diária, semanal, por intervalo e último dia do mês, marcação explícita e histórico breve; preferências locais.
- Formulários de compromisso sem fim ou duração presumidos; tarefa sem horário permitido; solicitação de Google em tarefa desmarcada por padrão.
- `authenticatedApiFetch` preparado para obter o token do cliente oficial do Supabase e encaminhá-lo ao cliente HTTP existente.

## Pendente

- Concluir a instalação das dependências e registrar `@supabase/supabase-js` no `package.json` e `package-lock.json`. A tentativa de `npm install` foi interrompida para a reinicialização; não houve alteração nesses dois arquivos.
- Ler a documentação local de Next 16 em `node_modules/next/dist/docs/` após a instalação, conforme `frontend/AGENTS.md`.
- Executar e corrigir ESLint, Prettier, typecheck, Vitest e build de produção. O código ainda não foi compilado nem testado nesta sessão.
- Revisar acessibilidade de diálogos e navegação por teclado; testar layout em navegador desktop e mobile.
- Conectar as telas à API real somente após publicação dos contratos GP-04 e validação do Auth GP-03. Hoje a conta Supabase autenticada mostra apenas estado de integração pendente; os dados da demonstração nunca são mostrados como dados da conta.
- Revisar horários de eventos reais com timezone IANA, quando os schemas com instantes UTC estiverem disponíveis.

## Arquivos principais

- `src/components/workspace.tsx`, `workspace-views.tsx`, `login.tsx`: navegação, telas e formulários.
- `src/lib/auth.ts`, `auth.test.ts`: cliente Supabase e wrapper HTTP autenticado.
- `src/lib/demo/{types,store,dates,validation}.ts`, `demo.test.ts`: modelo e dados exclusivos da demonstração.
- `src/app/{page.tsx,globals.css,agenda,tarefas,rotinas,configuracoes,login}`: rotas e estilos.
- `README.md`, `.gitignore`: estado de integração e cache npm local ignorado.

## Verificações e bloqueios

- `git status --short --branch`: branch correta, somente arquivos `frontend/**` alterados.
- `git diff --check`: sem erros nas alterações rastreadas antes deste checkpoint.
- Busca de padrões de credenciais nos arquivos alterados: nenhum encontrado. Conferir novamente antes de publicar.
- `npm ci`/`npm install`: tentativas não concluídas; npm demorou no download/extração de pacotes e foi interrompido com Ctrl+C para pausar com segurança. `node_modules/` e `.npm-cache/` são diretórios ignorados e podem estar incompletos.
- ESLint, Prettier, typecheck, Vitest e build: **não executados**. Testes `src/lib/demo/demo.test.ts` e `src/lib/auth.test.ts` foram escritos, mas não executados.
- Não foi verificada conexão real com Supabase, FastAPI, Google ou WhatsApp.

## Dependências externas ao escopo

- GP-03: JWT Supabase aceito pelo FastAPI; perfis, timezone e preferências, além de RLS/autorização.
- GP-04: rotas e schemas OpenAPI para compromissos, tarefas, rotinas e ocorrências; filtros/paginação, ações de conclusão/reabertura/cancelamento, recorrência e estados de sincronização. Hoje `docs/openapi.json` só publica `/health`.
- GP-06/07: conectividade Google Agenda e WhatsApp; as telas exibem estado não configurado.

## Retomada exata

1. Abrir a worktree `C:\gestao-gp05` na branch `feat/gp-05-frontend` e conferir `git status` e este arquivo.
2. Adicionar ao PATH da sessão PowerShell o Node existente: `$env:Path = 'C:\Users\Guilherme Andrade\AppData\Local\nvm\v22.23.2;' + $env:Path`.
3. Em `frontend/`, executar `npm.cmd install @supabase/supabase-js@2.118.0 --save --no-audit --no-fund` e conferir `package.json`/lockfile. Se o cache npm incompleto atrapalhar, diagnosticar antes de removê-lo.
4. Ler `frontend/node_modules/next/dist/docs/` para as regras de Client Components, rotas e links usadas aqui.
5. Executar `npm.cmd run format`, `npm.cmd run lint`, `npm.cmd run format:check`, `npm.cmd run typecheck`, `npm.cmd test` e `npm.cmd run build`; corrigir falhas e reforçar testes de interação dos formulários.
6. Revisar a interface em navegador desktop/mobile e verificar a proteção das rotas, foco dos diálogos e avisos de demonstração.
7. Quando GP-03/04 publicarem contratos, criar adaptador tipado em `src/lib/api/`, usar `authenticatedApiFetch` e `ApiError`, testar integração real e atualizar a documentação. Não inventar rotas até lá.

Não houve push, merge, rebase, deploy ou alteração fora de `frontend/**`.
