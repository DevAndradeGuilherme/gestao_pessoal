# AGENTS.md — Instruções comuns para agentes

## Hierarquia de referência

1. `CONTEXTO.md`: fonte de verdade de requisitos e decisões consolidadas.
2. `docs/DECISOES.md`: registro de decisões técnicas, subordinado ao contexto.
3. `docs/CONTRATOS.md`: interfaces combinadas e decisões ainda em aberto.
4. `docs/TAREFAS.md` e `docs/PLANO_DESENVOLVIMENTO.md`: escopo, dependências e aceites de cada entrega.

Em divergências, **interromper a alteração conflitante** e relatar a incompatibilidade. Não alterar requisitos implicitamente.

## Procedimento obrigatório por tarefa

- Identificar ID da tarefa e ler requisitos relacionados antes de editar.
- Informar antes de executar: **ação manual necessária**, **ferramenta/agente**, **modelo**, **risco**, **dependências**, **arquivos sob responsabilidade** e **critério de aceite**. Se nenhuma ação manual for necessária, registrar “nenhuma”.
- Verificar existência real de arquivos, bibliotecas, configurações e endpoints; não inventar implementação.
- Preferir mudanças pequenas dentro de uma entrega completa, sem fragmentar artificialmente em múltiplos prompts.
- Implementar testes proporcionais e registrar comandos executados e resultados.
- Não declarar integração externa validada sem verificação real.
- Entregar resumo objetivo: arquivos alterados, testes, pendências, riscos e mudanças de contrato.

## Regras de domínio não negociáveis

- Web e WhatsApp chamam **o mesmo serviço de domínio** no backend FastAPI.
- Supabase/PostgreSQL é a fonte de verdade; Google Agenda é cópia sincronizada de compromissos.
- Sincronização com Google Agenda é sistema → Google no MVP; tarefas só sincronizam por opção explícita.
- Não presumir duração de compromisso no domínio. Restrições técnicas do Google devem ser tratadas explicitamente na integração.
- Não interpretar passagem do tempo como conclusão de tarefa, rotina ou compromisso.
- OpenAI classifica/extrai dados estruturados; **não** acessa banco nem faz mutações diretamente.
- Jobs futuros persistem no PostgreSQL; Celery/Redis executam, não são fonte de verdade.
- Implementar deduplicação de webhooks, lembretes e reconciliação de sync externa.
- Toda informação privada deve ser vinculada ao usuário com autorização e isolamento.
- O domínio financeiro é migrado do Django por capacidade, preservando invariantes e testes, sem duplicar regras ativas.

## Colaboração de agentes

- Até **3 agentes de implementação simultâneos** por padrão. Usar um quarto somente quando uma frente isolada justificar.
- Cada agente trabalha em branch/worktree separada, com escopo exclusivo de escrita sempre que possível.
- Nome sugerido: `task/<ID>-<descricao-curta>`.
- Alterações em arquivos compartilhados (`CONTEXTO.md`, `docs/CONTRATOS.md`, migrations, lockfiles, configuração raiz) são coordenadas por um único integrador.
- Bloquear trabalho dependente de contrato até ele estar registrado, ou utilizar mocks alinhados a contratos aprovados.
- Não fazer commits diretamente na branch principal sem revisão/integração.
- Não executar deploy, migração destrutiva, criação de custos ou alteração de credenciais externas sem aprovação humana.

## Eficiência de contexto e tokens

- Ler primeiro os arquivos de referência e apenas o código necessário à tarefa.
- Evitar análises gerais repetidas de todo o repositório, múltiplas reescritas e refatorações fora de escopo.
- Usar modelo de custo intermediário por padrão; escalar para modelo forte diante de arquitetura transversal, segurança delicada, bugs difíceis ou migração financeira crítica.
- Fazer revisão cruzada apenas em fronteiras críticas: auth/RLS, pagamentos/finanças, sincronização, WhatsApp e deploy.
- Não imprimir segredos, logs integrais, arquivos extensos ou diffs irrelevantes.

## Conclusão

Uma tarefa é concluída quando: entregáveis existem, aceites verificáveis estão satisfeitos, testes disponíveis passaram, riscos e pendências estão registrados e o integrador aprovou a junção. Caso falte credencial ou serviço externo, informar **parcial/bloqueada**, não concluída.
