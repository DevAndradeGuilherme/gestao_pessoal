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

## Decisões técnicas ainda a registrar

- [ ] ADR-002 — Convenções de monorepo, dependências e CI.
- [ ] ADR-003 — Formato de recorrência e tratamento de timezone.
- [ ] ADR-004 — Persistência/claim de jobs, retry/backoff e idempotência.
- [ ] ADR-005 — Proteção e rotação de tokens OAuth Google.
- [ ] ADR-006 — Sequência de migração financeira e desligamento do legado.
- [ ] ADR-007 — Topologia real de deploy, backup e monitoramento.

As entradas acima são **pendências técnicas**, não decisões tomadas.
