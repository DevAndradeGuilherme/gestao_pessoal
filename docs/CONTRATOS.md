# Contratos técnicos compartilhados

**Estado:** contrato de responsabilidade e semântica definido; formatos e endpoints concretos **a estabelecer em GP-02**. Este arquivo **não descreve API já implementada**.

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

## 4. Contratos concretos a aprovar em GP-02

- [ ] Convenção de nomes/versão dos endpoints (rotas **não definidas ainda**).
- [ ] Schemas de request/response, paginação, filtros, erros e validação.
- [ ] Contrato de identidade entre Supabase Auth e FastAPI.
- [ ] Estratégia de migrations e schemas com isolamento por usuário.
- [ ] Comandos/eventos de integração, outbox ou mecanismo equivalente, idempotência e sync status.
- [ ] Schemas de interpretação de IA, estados de conversação e desambiguação.
- [ ] Representação de recorrência e semântica de fuso/DST.
- [ ] Formato de payloads internos dos workers e política de retries.
- [ ] Limites de edição por pasta, responsáveis e política de versionamento de contratos.

## 5. Política de alteração

O agente que necessitar alterar um contrato registra **proposta, impacto, testes e consumidores afetados**, solicita coordenação ao integrador e só depois edita a implementação. Não permitir alterações independentes de schema por múltiplos agentes no mesmo intervalo.
