# Sistema de Gestão Pessoal — Contexto do Projeto

Documento de referência funcional e técnica para desenvolvimento por agentes de IA e desenvolvedores humanos.

Instruções de leitura:
- Trate este arquivo como fonte de verdade do projeto para requisitos e decisões já aprovadas.
- Diferencie regras definidas, decisões aprovadas e itens ainda dependentes de implementação.
- Não invente endpoints, tabelas, bibliotecas, credenciais ou comportamentos não descritos aqui.
- Quando houver conflito entre uma hipótese de implementação e este documento, prevalece este documento.
- Antes de modificar arquitetura, integrações ou regras de domínio, registre a mudança neste arquivo ou em documentação técnica específica.

**Tipo:** Documento de contexto funcional e técnico (fonte de referência para desenvolvimento e agentes de IA)  
**Versão:** 0.2 — decisões arquiteturais consolidadas  
**Estado:** Planejamento concluído para início da implementação do MVP  
**Atualizado em:** 03/11/2026  
**Idioma principal:** Português (Brasil)

## 1. Visão geral

O **Sistema de Gestão Pessoal** é uma aplicação web integrada ao **WhatsApp**, ao **Google Agenda** e a um **sistema de organização financeira já existente**.

Seu objetivo é centralizar compromissos, tarefas e rotinas para que o usuário possa registrar atividades rapidamente, receber lembretes proativos, consultar sua programação e acompanhar o que foi concluído ou ficou pendente — sem depender exclusivamente de abrir a interface web.

A experiência deverá funcionar por dois canais complementares:

- **Interface web:** visualização e organização da agenda, tarefas, rotinas, histórico e configurações.
- **WhatsApp:** registro por mensagem, consultas, confirmações de conclusão e recebimento de lembretes e resumos diários.

### 1.1 Objetivo principal

Reduzir o esquecimento de compromissos e facilitar a execução da rotina por meio de uma combinação de **captura simples**, **organização visual**, **sincronização de calendário** e **acompanhamento ativo via WhatsApp**.

### 1.2 Princípios do produto

1. **Baixo atrito:** registrar e consultar atividades deve exigir poucas ações.
2. **Informação consistente:** o que aparece na web deve corresponder ao que o assistente informa pelo WhatsApp.
3. **Proatividade com controle:** o sistema envia lembretes, mas respeita horários e preferências do usuário.
4. **Rastreabilidade:** registros e alterações importantes precisam ter histórico.
5. **Confiabilidade:** falhas temporárias no WhatsApp ou Google Agenda não podem causar perda silenciosa de dados.
6. **Privacidade:** acesso a dados pessoais e integrações deve ser autenticado, autorizado e protegido.

**Público-alvo do MVP:** uso pessoal pelo proprietário. A arquitetura, o modelo de dados e as políticas de acesso devem, porém, manter vínculo explícito por usuário (`user_id`) e isolamento adequado para permitir múltiplos usuários no futuro sem reestruturar o domínio.

## 2. Escopo funcional

### 2.1 Entidades de organização

É importante distinguir três conceitos:

- **Compromisso**
  - Significado: Evento marcado para uma data e, normalmente, um horário
  - Exemplo: Consulta médica quinta às 15h
  - Comportamento esperado: Salvo no banco e criado no Google Agenda
- **Tarefa**
  - Significado: Ação a realizar, com ou sem prazo
  - Exemplo: Entregar relatório até sexta
  - Comportamento esperado: Acompanhada como pendente/concluída; vinculação à agenda pode ser opcional
- **Rotina / hábito**
  - Significado: Atividade repetida periodicamente
  - Exemplo: Estudar inglês de segunda a sexta
  - Comportamento esperado: Gera ocorrências acompanháveis de acordo com recorrência configurada
**Regra definida:** todo compromisso criado pelo sistema deve ser registrado no banco e sincronizado com o Google Agenda do usuário, desde que a conta esteja conectada.

**Regra definida:** tarefas são orientadas principalmente a acompanhamento e lembretes pelo WhatsApp. Elas não geram automaticamente eventos no Google Agenda, mesmo quando possuem horário. A sincronização com o Google Agenda é opcional por tarefa e ocorre apenas quando solicitada pelo usuário.

### 2.2 Cadastro e gestão de compromissos

O usuário poderá:

- Criar compromissos pelo painel web ou pelo WhatsApp.
- Informar título, data, horário, duração, descrição e local (quando aplicável).
- Listar compromissos por dia, semana ou período.
- Editar, reagendar e cancelar compromissos.
- Definir lembretes personalizados, inclusive múltiplas antecedências.
- Receber uma confirmação após o cadastro.

Se faltarem dados indispensáveis, como **data** ou **horário** de um compromisso com hora marcada, o sistema deve solicitar esclarecimento antes de confirmar o registro. **Não existe duração padrão de produto para compromissos.** A duração/fim é opcional e só deve ser considerada quando o usuário a informar explicitamente. A camada de integração com o Google Agenda deverá atender aos requisitos técnicos do provedor sem transformar um valor técnico em duração presumida no domínio.

### 2.3 Gestão de tarefas

- Criar tarefas pelo web ou WhatsApp.
- Informar descrição, prazo, prioridade e categoria (opcionais).
- Consultar tarefas pendentes, vencidas ou concluídas.
- Marcar uma tarefa como concluída pelos dois canais.
- Reabrir tarefas concluídas quando necessário.
- Registrar a data/hora real de conclusão, sem presumir que um compromisso ocorrido foi necessariamente realizado.

### 2.4 Gestão de rotinas

- Configurar recorrências conforme a necessidade de cada item ou automação, incluindo padrões diários, semanais, mensais, intervalos e regras de calendário como **último dia do mês**.
- Exibir ocorrências previstas e resultados por dia.
- Permitir confirmar realização ou sinalizar que não foi realizada.
- Consultar histórico de execução.

**Regra definida de recorrência:** não limitar o MVP a uma enumeração rígida de poucos padrões. A implementação deve usar uma representação flexível e validável, capaz de atender casos como resumo diário, rotina em dias específicos, tarefa a cada N dias/semanas e automações no último dia do mês. Regras muito específicas poderão ser acrescentadas conforme surgirem casos reais.

**Fora do MVP, a avaliar:** métricas de consistência, sequências de dias (streaks), metas semanais e gráficos de hábitos.

### 2.5 Lembretes automáticos pelo WhatsApp

O sistema deverá agendar mensagens para compromissos e tarefas que tenham lembrete ativo.

- Enviar mensagens com antecedência configurável (ex.: 1 dia, 1 hora, 15 minutos).
- Permitir ativar/desativar lembretes por item.
- Respeitar fuso horário e, quando configurado, horário de silêncio.
- Evitar lembretes duplicados mesmo após reinício do serviço ou reprocessamento de jobs.
- Registrar tentativas, envios e falhas.
- Recalcular ou cancelar lembretes quando o evento for reagendado ou cancelado.

Os lembretes do **Google Agenda** e as mensagens de **WhatsApp** são mecanismos distintos; o agendamento das mensagens deve ser controlado pelo próprio sistema.

**Padrões iniciais de notificação (configuráveis):**

- Resumo matinal: **07:00**.
- Revisão noturna: **23:00**.
- Horário de silêncio: **00:00–07:00**.
- Compromissos: lembrete padrão de **1 hora antes**, podendo haver múltiplas antecedências.
- Tarefas: lembrete no horário/prazo definido pelo usuário.
- Preferências gerais podem ser substituídas por configuração específica do item.

### 2.6 Resumo matinal

Diariamente, em um horário configurável, o sistema enviará pelo WhatsApp:

- Compromissos do dia, com horários.
- Tarefas previstas para o dia, priorizando as mais importantes.
- Rotinas esperadas para o dia.
- Pendências anteriores, se relevante e conforme preferência.

Se não houver atividades, o sistema deverá informar isso de forma objetiva, sem inventar compromissos.

### 2.7 Revisão noturna

Diariamente, em um horário configurável, o sistema enviará:

- O que foi **explicitamente marcado como concluído**.
- O que permanece **pendente**.
- Itens vencidos e atividades sem confirmação, quando cabível.
- Uma pergunta ou ação simples para atualizar o status dos itens.

**Regra essencial:** não considerar uma tarefa ou rotina concluída apenas porque seu horário passou. Compromissos ocorridos também não equivalem automaticamente a atividades realizadas.

### 2.8 Interações pelo WhatsApp

O usuário deverá poder enviar mensagens como:

“Marca uma reunião com Ana amanhã às 14h, por uma hora.”  
“O que tenho para fazer hoje?”  
“Me lembra de pagar a internet na sexta às 9h.”  
“Concluí a tarefa de enviar o orçamento.”  
“Quais compromissos tenho nesta semana?”  
“Adia a reunião de amanhã para 16h.”

**Comportamento esperado:**

1. Identificar a intenção da mensagem (criar, consultar, atualizar, concluir ou cancelar).
2. Extrair os dados necessários.
3. Verificar identidade e permissão do remetente.
4. Validar datas e resolver ambiguidades por meio de perguntas quando necessário.
5. Executar a operação pelo backend do sistema.
6. Responder com confirmação apenas após a operação ter sido registrada com sucesso; informar quando a sincronização externa estiver pendente.

**Decisão definida:** usar abordagem **híbrida**. Modelos da **OpenAI** serão usados para classificação de intenção e extração estruturada de parâmetros em mensagens livres. O backend continuará responsável por validação, autorização, desambiguação e execução. A IA não acessa o banco nem executa mutações diretamente. O modelo específico deve ser configurável e escolhido por testes de qualidade, custo e latência.

## 3. Fluxos principais

### 3.1 Criação de compromisso pela web

1. O usuário preenche o formulário e confirma o cadastro.
2. O backend valida o registro e o salva no **Supabase**.
3. O compromisso recebe um estado de sincronização inicial, como `pending`.
4. Um processo de integração cria o evento na **Google Calendar API**.
5. O sistema salva o `google_event_id` e atualiza a sincronização para `synced`.
6. O agendador prepara os lembretes correspondentes.
7. A interface informa o resultado, distinguindo cadastro local de sincronização externa.

Se a integração falhar, o registro permanece no banco com estado `failed` ou `pending_retry`, para reprocessamento seguro.

### 3.2 Criação de compromisso pelo WhatsApp

1. O usuário envia uma mensagem à instância conectada.
2. A **Evolution API (Baileys)** encaminha o evento ao webhook do backend.
3. O backend valida a origem, identifica o usuário e verifica se a mensagem já foi processada.
4. O módulo de interpretação identifica intenção e parâmetros.
5. Caso faltem informações essenciais, o sistema solicita confirmação.
6. O backend utiliza o **mesmo serviço de domínio** usado pela interface web para cadastrar o compromisso.
7. O evento é sincronizado com o Google Agenda e seus lembretes são agendados.
8. O sistema responde via WhatsApp com o resultado.

### 3.3 Disparo de lembretes

1. O agendador busca lembretes vencendo no momento.
2. Um worker reserva o envio de forma segura para impedir execução duplicada.
3. A mensagem é enviada usando a Evolution API.
4. O resultado da tentativa é persistido com horário e status.
5. Em falhas transitórias, o sistema executa novas tentativas com limite e intervalo definidos.

### 3.4 Resumo da manhã e revisão da noite

1. O agendador identifica usuários cujo horário configurado foi alcançado no fuso correto.
2. Consulta compromissos, tarefas, rotinas e status relevantes no banco.
3. Monta a mensagem a partir dos **dados reais persistidos**.
4. Envia pelo WhatsApp e registra o resultado para não repetir o mesmo resumo.
5. Na revisão noturna, aceita respostas que atualizem itens específicos.

### 3.5 Marcar como concluído via WhatsApp

1. O usuário informa qual tarefa/ocorrência realizou.
2. O sistema localiza a referência correta e pede desambiguação se houver itens semelhantes.
3. Atualiza status e `completed_at` no banco.
4. Registra histórico de alteração e confirma a operação.
5. A alteração fica visível imediatamente na interface web e nos resumos seguintes.

## 4. Arquitetura proposta

Arquitetura resumida:

- Usuário acessa a interface web em Next.js e o WhatsApp.
- O WhatsApp se comunica com a Evolution API/Baileys.
- A Evolution API envia webhooks para o backend FastAPI.
- A interface web também consome o backend FastAPI.
- O FastAPI concentra regras de negócio e integrações.
- O backend usa Supabase/PostgreSQL como fonte principal de dados.
- O backend integra com Google Calendar e OpenAI.
- Redis e Celery executam processamento assíncrono.
- O domínio financeiro existente será incorporado progressivamente ao backend principal.

### 4.1 Componentes

- **Frontend web**
  - Responsabilidade: Dashboard, calendário, tarefas, rotinas e configurações
  - Tecnologia / decisão: **Next.js + TypeScript + Tailwind CSS**
- **Backend / API**
  - Responsabilidade: Regras de negócio, autenticação, webhooks e integrações
  - Tecnologia / decisão: **FastAPI + Python**
- **Banco e autenticação**
  - Responsabilidade: Persistência, usuários e controle de acesso
  - Tecnologia / decisão: **Supabase gerenciado (PostgreSQL + Supabase Auth)**
- **Conector WhatsApp**
  - Responsabilidade: Receber e enviar mensagens
  - Tecnologia / decisão: **Evolution API com Baileys**, uma única instância pessoal no MVP
- **Interpretação de linguagem**
  - Responsabilidade: Classificação de intenção e extração estruturada
  - Tecnologia / decisão: **OpenAI**, abordagem híbrida, saída estruturada
- **Calendário**
  - Responsabilidade: Criar e manter eventos sincronizados
  - Tecnologia / decisão: **Google Calendar API (OAuth 2.0)**
- **Fila / worker**
  - Responsabilidade: Processar lembretes, resumos, sincronizações e tentativas
  - Tecnologia / decisão: **Celery + Redis**, com agendamentos de longo prazo persistidos no PostgreSQL
- **Infraestrutura**
  - Responsabilidade: Hospedar interface, backend, workers, Redis e Evolution API
  - Tecnologia / decisão: **VPS KVM2 da Hostinger**
- **Finanças**
  - Responsabilidade: Incorporar o domínio financeiro existente ao novo sistema
  - Tecnologia / decisão: Migração controlada do projeto Django existente para a arquitetura principal, preservando regras e testes
**Diretriz arquitetural:** manter um backend principal único em **FastAPI** para as regras de negócio do Sistema de Gestão Pessoal, independentemente de a solicitação ter origem na web ou no WhatsApp. O Supabase armazena o estado da aplicação; o Google Agenda mantém uma cópia sincronizada dos compromissos. O domínio financeiro existente será incorporado por migração controlada, evitando manter duas implementações ativas da mesma regra.

### 4.2 Integração com Google Agenda

- O usuário conecta sua conta Google por autorização OAuth 2.0.
- O sistema guarda as credenciais/tokens de modo seguro e limitado à necessidade operacional.
- Cada compromisso contém a associação ao calendário e ao evento externo.
- Criação, edição e cancelamento feitos pelo sistema devem refletir no Google Agenda.
- A sincronização deve ser idempotente, com política de reconciliação após falhas.
- **MVP definido:** sincronização **do sistema para o Google Agenda**.
- Alterações realizadas diretamente no Google Agenda **não retornam ao sistema no MVP**.
- **Fase futura:** sincronização bidirecional, somente após definir política explícita de conflitos e reconciliação.

### 4.3 Integração WhatsApp

- Receber mensagens por webhook da Evolution API.
- Responder e enviar notificações por endpoints da Evolution API.
- Implementar identificação do remetente autorizado, deduplicação por ID da mensagem e proteção dos endpoints.
- Monitorar o estado da sessão e reconexões.
- **MVP:** utilizar uma única instância pessoal da Evolution API/Baileys vinculada ao proprietário. O domínio não deve ficar acoplado ao identificador da instância, preservando possibilidade de expansão futura.
- **Risco conhecido:** o modo Baileys usa integração baseada no WhatsApp Web, não sendo equivalente à API oficial da Meta; considerar limitações operacionais e eventual migração para canal oficial.

### 4.4 Incorporação do domínio financeiro

O projeto financeiro existente foi inspecionado em 03/11/2026. Ele é uma aplicação **Python/Django**, em arquitetura de monólito modular, com PostgreSQL gerenciado pelo Supabase, Evolution API para WhatsApp e OpenAI para interpretação estruturada. As regras financeiras estão concentradas no backend Django, com separação entre serviços de escrita, seletores de leitura, autorização, idempotência e auditoria.

**Decisão definida:** o Sistema de Gestão Pessoal se tornará a aplicação principal e **incorporará as funcionalidades financeiras existentes**, em vez de manter uma integração permanente entre dois backends independentes.

Diretrizes para essa incorporação:

- Não copiar regras financeiras de forma ad hoc nem manter duas implementações ativas da mesma regra.
- Usar o projeto financeiro atual como fonte de referência para regras, contratos, testes, validações, autorização, idempotência e comportamento já validado.
- Migrar cada capacidade financeira de forma controlada para a arquitetura principal em FastAPI/Python.
- Preservar invariantes do sistema financeiro, especialmente validação server-side, cálculos no banco, uso de valores decimais, autorização explícita e auditoria.
- Após a migração e validação de uma capacidade, a implementação antiga correspondente não deverá continuar evoluindo em paralelo.
- A única instância pessoal do WhatsApp ficará centralizada no Sistema de Gestão Pessoal; mensagens financeiras serão roteadas internamente ao domínio financeiro incorporado.
- O cronograma de migração financeira deve ocorrer por etapas e com testes de regressão, sem bloquear a entrega inicial de compromissos, tarefas e lembretes.

## 5. Modelo de dados inicial (proposta)

Nomes de tabelas e campos são sugestões. Devem ser refinados antes das migrations.

- `users` / `profiles`
  - Campos principais: `id`, `name`, `timezone`, `whatsapp_number`, `created_at`
  - Propósito: Identidade e preferências gerais
- `integrations`
  - Campos principais: `id`, `user_id`, `provider`, `status`, `external_account_id`
  - Propósito: Estado das conexões externas; segredos devem ficar protegidos
- `appointments`
  - Campos principais: `id`, `user_id`, `title`, `starts_at`, `ends_at`, `description`, `location`, `status`, `google_event_id`, `google_calendar_id`, `sync_status`
  - Propósito: Compromissos e associação ao Google Agenda
- `tasks`
  - Campos principais: `id`, `user_id`, `title`, `description`, `due_at`, `priority`, `status`, `completed_at`, `sync_to_calendar`, `google_event_id`
  - Propósito: Tarefas, conclusão e sincronização opcional com Google Agenda
- `routines`
  - Campos principais: `id`, `user_id`, `title`, `recurrence_rule`, `active`
  - Propósito: Definição de atividades recorrentes
- `routine_occurrences`
  - Campos principais: `id`, `routine_id`, `scheduled_for`, `status`, `completed_at`
  - Propósito: Execuções individuais de rotinas
- `reminders`
  - Campos principais: `id`, `user_id`, `entity_type`, `entity_id`, `scheduled_at`, `status`, `attempt_count`, `sent_at`, `idempotency_key`
  - Propósito: Envios programados e controle de duplicidade
- `message_events`
  - Campos principais: `id`, `provider_message_id`, `user_id`, `direction`, `processed_at`, `status`
  - Propósito: Rastreio técnico de mensagens e deduplicação
- `activity_log`
  - Campos principais: `id`, `user_id`, `entity_type`, `entity_id`, `action`, `created_at`
  - Propósito: Histórico de mudanças importantes
- `notification_preferences`
  - Campos principais: `user_id`, `morning_time`, `evening_time`, `quiet_hours`, `reminder_offsets`, `enabled`
  - Propósito: Preferências de comunicação; defaults iniciais 07:00, 23:00 e silêncio 00:00–07:00
### 5.1 Regras de modelagem

- Todas as entidades privadas devem estar vinculadas ao usuário proprietário.
- Armazenar instantes em formato compatível com UTC e interpretá-los conforme o fuso do usuário (`timezone`, por padrão configurável).
- Utilizar políticas de **Row Level Security (RLS)** quando aplicáveis no Supabase.
- Não salvar tokens de integração ou chaves em texto puro no frontend nem em logs.
- Usar identificadores externos (`google_event_id`, `provider_message_id`) para reconciliação e idempotência.
- Modelar exclusão/cancelamento e histórico conforme as necessidades de auditoria.
- O vínculo com Google Agenda em tarefas deve ser explícito e opcional; não inferir `sync_to_calendar` apenas pela presença de horário.
- A recorrência deve usar representação flexível e validável, evitando depender de uma lista fixa de padrões.

## 6. Interface web — telas previstas

### 6.1 Dashboard / Hoje

- Próximos compromissos.
- Tarefas e rotinas do dia.
- Indicadores simples: concluído, pendente e atrasado.
- Ações rápidas: **novo compromisso**, **nova tarefa**, **marcar como feito**.

### 6.2 Agenda

- Visualizações por dia, semana e mês.
- Criação, edição e cancelamento de compromissos.
- Indicação de falhas ou pendências de sincronização com o Google Agenda.

### 6.3 Tarefas e rotinas

- Listas filtráveis por status, data e prioridade.
- Configuração de recorrência.
- Histórico de execuções.

### 6.4 Integrações e configurações

- Conectar/desconectar Google Agenda.
- Verificar situação da única instância pessoal do canal WhatsApp.
- Configurar horários dos resumos e antecedência dos lembretes.
- Definir fuso horário, privacidade e preferências de notificações.

### 6.5 Finanças (integração)

- Acesso às funcionalidades do sistema financeiro existente, por módulo, link ou API, conforme arquitetura definida após análise do repositório.

## 7. Requisitos não funcionais

### 7.1 Segurança e privacidade

- Autenticar usuários da interface web e autorizar operações por proprietário.
- Validar origem/autenticidade de webhooks conforme recursos da versão instalada da Evolution API; adicionar controles complementares de rede/autorização quando necessário.
- Proteger credenciais, tokens de acesso e refresh tokens.
- Aplicar menor privilégio aos acessos ao banco e à API Google.
- Usar HTTPS, gestão de segredos fora do repositório, backups e política de retenção de dados.
- Atender à LGPD: transparência, finalidade, acesso, correção e exclusão de dados pessoais, conforme obrigações aplicáveis.

### 7.2 Confiabilidade operacional

- Jobs de envio **persistentes**, sobrevivendo ao reinício da aplicação. Agendamentos de longo prazo ficam no PostgreSQL; Celery/Redis executam o trabalho próximo ao momento previsto.
- Tratamento de falhas com tentativas limitadas e observabilidade.
- Impedir processamento repetido de webhooks e notificações.
- Não informar que uma ação foi executada quando ela ainda falhou ou depende de confirmação.
- Preservar a integridade do registro local caso serviços externos estejam indisponíveis.

### 7.3 Operação na VPS

- Planejar a implantação dos serviços necessários na VPS KVM2 da Hostinger (por exemplo, por containers), sem presumir capacidade ilimitada.
- Definir proxy reverso, HTTPS, reinício automático, logs, monitoramento e backups.
- Avaliar separação de serviços e limites de recursos conforme carga real.
- O Supabase será **gerenciado em nuvem** no MVP. A VPS não hospedará o Supabase.

## 8. Escopo de MVP sugerido

### Entrega 1 — Base operacional

- [ ] Autenticação e perfil do usuário.
- [ ] Banco de dados e políticas de acesso.
- [ ] Interface web para criar, listar e editar compromissos.
- [ ] Integração OAuth com Google Agenda e criação/edição/cancelamento de eventos.
- [ ] Tratamento e visualização de falhas de sincronização.

### Entrega 2 — WhatsApp

- [ ] Conexão da Evolution API (Baileys).
- [ ] Webhook seguro, identificação do remetente e deduplicação.
- [ ] Registrar compromissos pelo WhatsApp.
- [ ] Consultar compromissos do dia e da semana.
- [ ] Mensagens de confirmação e tratamento de ambiguidades.

### Entrega 3 — Produtividade e automações

- [ ] Gestão de tarefas e status de conclusão.
- [ ] Lembretes programados com worker persistente.
- [ ] Resumo matinal configurável.
- [ ] Revisão noturna com concluídos e pendentes.
- [ ] Marcação de tarefas como feitas pelo WhatsApp.
- [ ] Rotinas recorrentes básicas.

### Entrega 4 — Incorporação financeira

- [x] Revisar arquitetura, autenticação, modelo de dados e fronteiras do sistema financeiro existente.
- [ ] Mapear regras financeiras e testes que deverão ser preservados na migração.
- [ ] Migrar capacidades financeiras priorizadas para o backend principal sem duplicar regras.
- [ ] Incorporar consultas, vencimentos e lembretes financeiros ao planejamento diário.
- [ ] Desativar progressivamente implementações antigas após validação da capacidade migrada.

### Fora do MVP / evolução possível

- [ ] Sincronização bidirecional com Google Agenda.
- [ ] Recursos avançados de IA além da interpretação textual do MVP, como áudio, visão e conversação contextual prolongada.
- [ ] Relatórios e métricas avançadas de produtividade.
- [ ] Aplicativo móvel nativo.
- [ ] Suporte a múltiplas contas ou equipes, se houver necessidade.

## 9. Critérios de aceite — comportamentos verificáveis

1. **Cadastro web:** ao criar um compromisso válido, ele aparece na web e no Google Agenda vinculado, sem duplicação.
2. **Cadastro WhatsApp:** ao enviar uma solicitação completa, o usuário recebe confirmação e encontra o mesmo compromisso no painel web.
3. **Dados incompletos:** quando a data/hora necessária for ambígua, o sistema pede esclarecimento antes de criar o evento.
4. **Lembrete:** um evento com lembrete ativo gera uma mensagem no horário previsto, com registro e proteção contra duplicidade.
5. **Alteração:** reagendar um compromisso atualiza agenda e horários de lembretes; lembretes antigos deixam de ser enviados.
6. **Resumo matinal:** a mensagem reflete os dados reais do dia e é enviada uma vez por período configurado.
7. **Revisão noturna:** somente atividades marcadas como concluídas aparecem como feitas; as demais permanecem pendentes ou sem confirmação.
8. **Concluir pelo WhatsApp:** a alteração é persistida e aparece na web, com histórico.
9. **Falha externa:** indisponibilidade temporária do Google ou WhatsApp não provoca perda silenciosa do cadastro.
10. **Segurança:** um usuário não pode consultar, alterar nem receber dados privados de outro usuário.

## 10. Decisões aprovadas

As decisões abaixo foram consolidadas em 03/11/2026 e orientam a implementação do MVP:

- Público-alvo
  - Decisão aprovada: **Uso pessoal inicialmente**, com `user_id`, autenticação e isolamento preparados para múltiplos usuários no futuro.
- Frontend/backend
  - Decisão aprovada: **Next.js + TypeScript + Tailwind CSS** no frontend; **FastAPI + Python** no backend.
- Linguagem natural
  - Decisão aprovada: Abordagem **híbrida** com modelos da **OpenAI** para interpretação e extração estruturada; backend valida e executa.
- Eventos
  - Decisão aprovada: **Sem duração padrão de produto**. Fim/duração só é considerado quando informado pelo usuário.
- Tarefas e agenda
  - Decisão aprovada: Tarefas são principalmente acompanhadas por **WhatsApp**; sincronização com Google Agenda é **opcional por tarefa**.
- Recorrência
  - Decisão aprovada: Recorrência **flexível conforme o caso**, suportando padrões diários, semanais, mensais, intervalos e regras como último dia do mês.
- Sincronização
  - Decisão aprovada: MVP **unidirecional Sistema → Google Agenda**; bidirecional fica para fase futura com política de conflitos.
- Notificações
  - Decisão aprovada: Defaults: resumo **07:00**, revisão **23:00**, silêncio **00:00–07:00**, compromisso **1h antes**; tudo configurável.
- WhatsApp
  - Decisão aprovada: **Uma única instância pessoal** da Evolution API/Baileys no MVP.
- Supabase
  - Decisão aprovada: **Supabase gerenciado em nuvem**.
- Infraestrutura
  - Decisão aprovada: **Celery + Redis** para execução assíncrona; agendamentos de longo prazo persistidos no PostgreSQL/Supabase.
- Finanças
  - Decisão aprovada: **Incorporar o domínio financeiro existente** ao novo sistema por migração controlada, preservando regras, testes, autorização, idempotência e auditoria.
### 10.1 Decisões ainda necessárias durante a implementação

As decisões de produto e arquitetura acima estão fechadas para iniciar o desenvolvimento. Detalhes de implementação poderão ser definidos na fase correspondente, desde que não contradigam estas regras. Exemplos:

- versão e modelo OpenAI a usar em cada função, definidos por testes de qualidade, custo e latência;
- formato técnico exato da regra de recorrência;
- política de retry/backoff do Celery;
- forma de proteção/rotação de tokens OAuth do Google;
- sequência exata de migração das capacidades financeiras existentes;
- estratégia futura de sincronização bidirecional com Google Agenda.

## 11. Referências

### Inspiração de produto

- [Tony — Assistente pessoal](https://otony.ai/) — referência de experiência conversacional, lembretes, resumos e integração de diferentes áreas da vida. **Referência de produto, não especificação técnica do sistema.**

### Projeto já existente

- [Sistema Financeiro WhatsApp](https://github.com/DevAndradeGuilherme/Sistema-Financeiro-WhatsApp) — projeto financeiro existente, inspecionado em 03/11/2026. Stack observada: Python/Django, PostgreSQL gerenciado pelo Supabase, Evolution API e OpenAI. Servirá como fonte de regras e testes para a migração controlada do domínio financeiro.

### Documentação técnica

- [Evolution API — repositório oficial](https://github.com/evolution-foundation/evolution-api)
- [Evolution API — webhooks](https://github.com/evolution-foundation/evolution-docs/blob/main/docs/02-Configuration/Webhooks.md)
- [Google Calendar API — criação de eventos](https://developers.google.com/workspace/calendar/api/guides/create-events)
- [Supabase — documentação](https://supabase.com/docs)

## 12. Orientações para agentes de IA e desenvolvedores

Ao desenvolver este projeto:

1. **Trate este arquivo como contexto de produto, não como prova de que funcionalidades já existem.**
2. Diferencie sempre **requisito definido**, **proposta** e **decisão pendente**.
3. Não invente bibliotecas, endpoints, tabelas ou credenciais. Para o domínio financeiro, use o repositório existente e sua documentação como fonte antes de migrar regras.
4. Não replique regras de criação de compromissos entre WhatsApp e web: ambas as entradas devem usar serviços de domínio compartilhados.
5. Priorize consistência de dados, idempotência de webhooks, agendamentos persistentes e tratamento explícito de falhas.
6. Não marque tarefas como concluídas automaticamente apenas pela passagem do tempo.
7. Antes de alterar integrações externas, verificar documentação e comportamento da versão efetivamente instalada.
8. Ao implementar uma funcionalidade, atualizar este documento caso requisitos ou decisões tenham mudado, e registrar mudanças relevantes em documentação técnica específica.
9. A OpenAI interpreta e estrutura entradas; o backend FastAPI valida, autoriza e executa. Nunca conceder à IA acesso direto ao banco ou capacidade autônoma de mutação.
10. Redis/Celery não são a fonte de verdade de lembretes futuros; o PostgreSQL deve preservar o estado dos agendamentos.
11. Durante a migração financeira, preservar uma única fonte de verdade por regra e impedir evolução paralela de implementações duplicadas.

**Resumo em uma frase:** construir um assistente pessoal de uso inicialmente individual, com Next.js + FastAPI, dados no Supabase gerenciado, interação por uma instância pessoal do WhatsApp, interpretação híbrida com OpenAI, sincronização unidirecional com Google Agenda, automações Celery/Redis e incorporação progressiva do domínio financeiro existente.
