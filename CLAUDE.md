# CLAUDE.md — Claude Code

Leia primeiro `CONTEXTO.md`, `AGENTS.md` e a tarefa correspondente em `docs/TAREFAS.md`. Este arquivo complementa, mas não substitui, as regras compartilhadas.

## Papel preferencial

Claude Code atua preferencialmente em fundação arquitetural, implementação transversal da API, integração WhatsApp/IA, reconciliação de contratos e migração financeira de maior complexidade. A atribuição real é definida por tarefa, não por exclusividade de ferramenta.

## Antes de qualquer implementação

1. Informe a **ação manual necessária** (ou nenhuma).
2. Indique o **modelo recomendado** e uma justificativa curta de custo/risco.
3. Informe dependências, branch/worktree e pastas que pode alterar.
4. Resuma em poucas linhas o objetivo e os critérios de aceite.

## Durante a execução

- Planeje brevemente e execute, evitando grandes debates ou reanálises sem necessidade.
- Respeite decisões do `CONTEXTO.md` mesmo quando houver alternativas atraentes.
- Não modifique contratos compartilhados unilateralmente: sinalize ao integrador e registre a mudança antes de prosseguir.
- Valide alterações localmente com testes objetivos; nunca invente resultados.
- Se uma credencial externa for necessária, preparar adaptação por interface/mock e registrar bloqueio da validação real.

## Saída esperada de cada tarefa

- O que foi entregue e onde.
- Testes/comandos executados e resultados.
- Ações manuais ainda necessárias.
- Alterações documentais e contratos afetados.
- Riscos, limitações, próximos desbloqueios e status proposto em `docs/TAREFAS.md`.

## Modelos

Use **Sonnet** como padrão inicial de custo/qualidade para tarefas intermediárias e **Opus** seletivamente para arquitetura complexa, análise sistêmica ou migração delicada. Verificar nomes e disponibilidade reais no ambiente do Claude Code antes de fixar um identificador de versão. Para Codex, usar esforço **medium** por padrão, elevando a **high** apenas quando necessário.
