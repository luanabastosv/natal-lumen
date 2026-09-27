# ESPECIFICAÇÃO — NATAL LUMEN

## O evento
- Evento anual de caridade que acontece em várias cidades. Cada cidade num ano é um evento independente, chamado "edição" (ex.: Fortaleza 2026).
- Instituições enviam listas de crianças carentes (nome, idade, sexo, código, instituição).
- Cada criança recebe dois padrinhos: padrinho de CESTA (valor padrão R$ 120, paga cesta/presente/kit higiene) e padrinho de FESTA (valor padrão R$ 60, ajuda nos custos do evento). Os valores podem mudar por edição.
- Cada criança escreve 2 cartões de agradecimento, um para cada padrinho. Os cartões são digitalizados e enviados aos padrinhos na semana do evento, junto com o convite para participar.
- Cada edição pode ter vários dias; cada criança vai a apenas um dia (normalmente +1500 crianças por edição).
- Equipes: coordenação, comissários (captam padrinhos e enviam cartões), monitores (recolhem e digitalizam cartões), estrutura (compram e montam os kits e fazem a entrega).
- Dados de crianças são sensíveis (LGPD): acesso sempre autenticado, isolado por cidade e registrado em log.

## Stack e publicação
- O site público fica em https://DOMINIO/ e NÃO faz parte deste projeto.
- O sistema fica em https://DOMINIO/acesso (frontend) e https://DOMINIO/acesso/api (backend), no mesmo domínio.
- Frontend: novo projeto React com Vite em sistema/frontend, usando a mesma tecnologia de estilização do site e a identidade visual documentada em docs/IDENTIDADE_VISUAL.md. Copie para o novo projeto os arquivos visuais necessários (logo, fontes, variáveis de cores) — nunca importe arquivos diretamente de site/.
  - Vite configurado com base "/acesso/"; React Router com basename "/acesso". As rotas internas são escritas sem o prefixo (ex.: "/cartoes-monitoria" resulta em /acesso/cartoes-monitoria).
  - /acesso sem sessão mostra a tela de login; com sessão, mostra o painel inicial do usuário.
  - Em desenvolvimento, o Vite faz proxy de /acesso/api para http://localhost:8000.
  - Layout responsivo (vários voluntários usarão pelo celular).
  - Um link discreto "Voltar ao site" no rodapé do sistema.
- Backend: Python, FastAPI (com root_path "/acesso/api"), SQLAlchemy 2, Alembic, Pydantic, pyjwt, pwdlib[argon2], openpyxl/pandas, opencv-python, numpy, rapidfuzz, qrcode. Pasta sistema/backend.
- Autenticação por cookie httpOnly, Secure e SameSite=Strict, com path "/acesso" (possível porque frontend e API estão no mesmo domínio). Nunca guardar o token em localStorage. Proteção contra CSRF nas rotas que alteram dados.
- Base de dados: PostgreSQL. URL na variável DATABASE_URL (arquivo .env, fora do git). Criar .env.example.
- Pasta dos arquivos enviados definida pela variável ARQUIVOS_DIR, fora das pastas públicas do frontend.
- Toda alteração de estrutura da base é feita por migration do Alembic, nunca manualmente.
- Manter um README em sistema/ explicando como rodar localmente e como publicar em /acesso.

## Tabelas
Operação:
- cidades: id, nome, uf, ativo
- edicoes: id, cidade_id, ano, nome, valor_cesta, valor_festa, ativa — único (cidade_id, ano)
- dias_evento: id, edicao_id, data, descricao
- instituicao_dia: id, edicao_id, instituicao_id, dia_evento_id — único (edicao_id, instituicao_id). O dia do evento é da INSTITUIÇÃO: todas as crianças dela vão no mesmo dia.
- instituicoes: id, cidade_id, nome, responsavel, telefone, endereco, ativo
- criancas: id, edicao_id, instituicao_id, dia_evento_id (opcional), comissario_id (usuario, opcional), codigo, nome, idade, sexo, observacoes, checkin_em, checkin_por (usuario) — único (edicao_id, instituicao_id, codigo)
- padrinhos: id, edicao_id, nome, whatsapp, email, observacoes, criado_por, criado_em (padrinhos pertencem a uma edição — cidade + ano; não persistem entre anos: todo ano são padrinhos novos)
- apadrinhamentos: id, crianca_id, padrinho_id, tipo (cesta|festa), valor, pagamento_id (opcional), comissario_id (usuario), vai_ao_evento (opcional), criado_em — único (crianca_id, tipo). A restrição única é do lado da criança: ela tem no máximo um padrinho de cesta e um de festa. **Um mesmo padrinho pode apadrinhar várias crianças.** O padrinho pode ser de outra edição/cidade: apadrinhamento entre cidades é permitido.
- pagamentos: id, padrinho_id, valor, data, forma, comprovante_arquivo, registrado_por, conferido (bool). Um pagamento pode quitar vários apadrinhamentos.
- cartoes: id, crianca_id, tipo (cesta|festa), arquivo, texto_ocr, status (digitalizado|enviado), monitor_id, enviado_por, enviado_em, criado_em — único (crianca_id, tipo). O destinatário é encontrado via criança + tipo → apadrinhamento → padrinho (o cartão pode existir antes de haver padrinho).
- kits: id, crianca_id (único), status (pendente|montado|entregue), entregue_em, entregue_por, observacoes
- compras: id, edicao_id, descricao, categoria, quantidade, valor_total, fornecedor, responsavel_id, data

Acesso:
- usuarios: id, nome, email (único), whatsapp, senha_hash, admin_geral (bool), ativo, ultimo_login, tentativas_falhas, bloqueado_ate, criado_em
- perfis: id, nome, descricao
- permissoes: id, codigo (único), descricao
- perfil_permissoes: perfil_id, permissao_id
- usuario_edicao: id, usuario_id, edicao_id, perfil_id, ativo — único (usuario_id, edicao_id)
- usuario_instituicao: id, usuario_edicao_id (FK usuario_edicao), instituicao_id, ativo — único (usuario_edicao_id, instituicao_id). Define as instituições sob responsabilidade daquele usuário naquela edição. A instituição precisa ser da mesma cidade da edição (validado na aplicação).
- tokens_acesso: id, usuario_id, token_hash, tipo (primeiro_acesso|redefinir_senha), expira_em, usado_em
- log_atividades: id, usuario_id, acao, tabela, registro_id, detalhes (json), criado_em

## Perfis e permissões
Permissões: importar_listas, editar_criancas, ver_criancas, gerenciar_usuarios, subir_cartoes, ver_padrinhos, editar_padrinhos, registrar_pagamentos, enviar_cartoes, gerenciar_kits, gerenciar_compras, fazer_checkin, ver_painel, gerenciar_cadastros.
- Coordenação da cidade: todas as permissões, limitadas às suas edições.
- Comissário: ver_criancas, ver_padrinhos, editar_padrinhos, enviar_cartoes. (Mudança posterior à especificação original: pagamento é da coordenação e check-in é do monitor e da estrutura.)
- Monitor: ver_criancas, subir_cartoes, fazer_checkin.
- Estrutura: ver_criancas, gerenciar_kits, gerenciar_compras, fazer_checkin.
- admin_geral = true: acesso total a todas as cidades e edições; único que cria cidades, edições e coordenadores de cidade.
Os perfis e permissões são criados por seed e podem ser alterados na base sem mudar código.

## Regras de acesso (obrigatórias)
- Toda autorização é verificada no BACKEND. O frontend apenas esconde menus e rotas.
- Cada rota da API declara a permissão exigida (dependência do FastAPI, ex.: exige_permissao("subir_cartoes")).
- Toda consulta é filtrada pelas edições em que o usuário tem vínculo ativo em usuario_edicao (exceto admin_geral).
- Num apadrinhamento entre cidades, o registro é visível para quem tem vínculo ativo na edição do padrinho OU na edição da criança. Os dados da criança continuam sujeitos à permissão ver_criancas.
- Comissários e monitores só alcançam crianças das instituições atribuídas a eles em usuario_instituicao. Coordenação e estrutura veem a edição inteira. **Uma instituição pode ter vários comissários**, e todos eles alcançam a lista inteira dela: é um time. `criancas.comissario_id` diz quem responde por cada criança, e não restringe nada — nem o alcance nem a edição.
- Escape para o caso entre cidades: a busca por **código exato** da criança alcança qualquer instituição das edições do usuário, mesmo fora das atribuídas — e é gravada em log_atividades. Listagens e exportações nunca escapam do filtro.
- O coordenador de cidade só cria/edita usuários e vínculos da sua própria cidade, e é quem atribui as instituições de cada comissário e monitor.
- Ações sensíveis (criar/editar/excluir registros, exportar listas, login) são gravadas em log_atividades.
- Sessão em cookie httpOnly com JWT de expiração curta (ex.: 8h). Bloqueio temporário após 5 tentativas falhas. Senhas apenas como hash.
- Primeiro acesso: o coordenador cria a conta e o sistema gera um link com token de uso único (expira em 72h) para o voluntário definir a senha.
- Padrinhos recebem apenas o primeiro nome e a idade da criança.

## Arquivos dos cartões
- Pasta: {ARQUIVOS_DIR}/cartoes/{cidade}/{ano}/
- Nome: {INSTITUICAO}_{NOME_DA_CRIANCA}_{TIPO}.jpg, em maiúsculas, sem acentos, espaços viram "_", apenas A-Z 0-9 _. Se já existir, acrescentar _2, _3...
- Os arquivos nunca são servidos publicamente: só por rota autenticada que verifica a permissão e a edição do usuário.

---

## Correções posteriores

Alterações feitas na especificação depois do registro inicial, para manter o
rastro do que mudou e por quê.

### 2026-09-22 — Padrinhos passam a ser por edição, e apadrinhamento entre cidades é permitido

Decidido pela Luana. Substitui o que a versão inicial dizia.

| | Versão inicial | Agora |
| --- | --- | --- |
| Escopo do padrinho | `cidade_id` — "padrinhos pertencem a uma cidade e persistem entre anos" | `edicao_id` — padrinho pertence a uma edição (cidade + ano); todo ano são padrinhos novos |
| Apadrinhamento entre cidades | não previsto | permitido: o padrinho pode apadrinhar criança de outra edição/cidade |
| Visibilidade do caso cruzado | não previsto | visível pela edição do padrinho **ou** pela edição da criança |

Consequências práticas:

- O mesmo doador que participa em 2026 e 2027 tem **dois registros** em `padrinhos`, um por edição. Não há histórico ligando os dois (se isso passar a ser necessário, será preciso um campo de identificação da pessoa, ex.: whatsapp normalizado).
- `padrinhos.edicao_id` é FK para `edicoes`, e não há restrição obrigando a criança do apadrinhamento a ser da mesma edição.
- A cidade do padrinho é obtida por `padrinhos → edicoes → cidades` (não fica duplicada na tabela).

### 2026-09-22 — Comissários e monitores respondem por instituições específicas

Decidido pela Luana. Acrescenta uma tabela e uma camada ao filtro de acesso.

| | Versão inicial | Agora |
| --- | --- | --- |
| Responsabilidade por instituição | não prevista | tabela `usuario_instituicao` liga o vínculo do usuário (usuario_edicao) às instituições que ele acompanha |
| Alcance do comissário e do monitor | toda a edição | só as instituições atribuídas, com escape por código exato (registrado em log) |
| Alcance da estrutura e da coordenação | toda a edição | sem mudança: toda a edição |

Consequências práticas:

- O filtro de crianças passa a ter **dois níveis**: primeiro a edição (`usuario_edicao`), depois a instituição (`usuario_instituicao`) para os perfis comissário e monitor.
- A tabela é genérica (serve a qualquer perfil), mas o filtro só é aplicado a comissário e monitor. Ligar para estrutura no futuro é mudar a regra, não o esquema.
- A ligação é feita a `usuario_edicao.id`, não a `usuario_id` + `edicao_id` soltos: assim a atribuição não pode existir sem o vínculo com a edição, e cai junto quando o vínculo é removido.
- Total de tabelas passa de 18 para **19** (11 de operação + 8 de acesso).

### 2026-09-22 — Esclarecimento: um padrinho pode apadrinhar várias crianças

Decidido pela Luana. **Não houve mudança de esquema** — o modelo original já
permitia. A restrição única de `apadrinhamentos` é `(crianca_id, tipo)`, isto é,
limita a criança a um padrinho de cesta e um de festa; não limita quantas vezes o
mesmo `padrinho_id` aparece. O texto da tabela foi apenas explicitado para não
deixar dúvida.

### 2026-09-23 — Nova permissão: gerenciar_cadastros

Decidido durante a fase 4. A lista original tinha 13 permissões e nenhuma cobria
**instituições** e **dias do evento**, que a coordenação precisa gerenciar.

| | Versão inicial | Agora |
| --- | --- | --- |
| Instituições e dias do evento | sem permissão definida | `gerenciar_cadastros`, só na Coordenação |
| Total de permissões | 13 | 14 |

Na prática nada mudou de alcance: a Coordenação já recebia todas as permissões,
e os outros perfis não recebem esta. A mudança é de legibilidade — a rota passa
a declarar `exige_permissao("gerenciar_cadastros")` em vez de pegar carona numa
permissão de nome errado.

Cidades e edições continuam restritas ao `admin_geral`, sem permissão própria,
como a especificação define.

### 2026-09-23 — O dia do evento é da instituição, não da criança

Decidido pela Luana. A divisão dos dias é feita por instituição: se a Escolinha
Sol vai no sábado, **todas** as crianças dela vão no sábado.

| | Versão inicial | Agora |
| --- | --- | --- |
| Onde o dia é definido | por criança (`criancas.dia_evento_id`) | por instituição, em `instituicao_dia` |
| Duas crianças da mesma escola em dias diferentes | possível | impossível |

`criancas.dia_evento_id` continua existindo — kit, check-in e painel filtram por
ele — mas passa a ser **derivado**: só `app/servicos/dias.py` o grava. Editar o
dia de uma criança isolada foi removido da API e da tela; quem muda é a
instituição, e todas as crianças dela vão junto.

Crianças criadas ou importadas depois herdam o dia que a instituição já tem.

### 2026-09-23 — Códigos gerados pela aplicação

As planilhas passam a vir sem código (nome, idade, sexo, instituição). A
aplicação numera com a sigla da instituição mais um sequencial, na ordem:
meninas primeiro, depois idade crescente, depois ordem alfabética.

### 2026-09-27 — O comissário não vê pagamentos nem check-in

Decidido pela Luana. O comissário perde `registrar_pagamentos` e
`fazer_checkin`.

| | Versão inicial | Agora |
| --- | --- | --- |
| Pagamentos | comissário e coordenação | só a coordenação |
| Check-in | comissário, monitor, estrutura e coordenação | monitor, estrutura e coordenação |

Consequências práticas:

- As abas **Pagamentos** e **Check-in** desaparecem do menu do comissário, e as
  rotas correspondentes passam a devolver 403 para ele. O botão de pagamento na
  ficha do padrinho também sai — ele continua captando padrinhos e ligando
  crianças, mas quem registra e confere o dinheiro é a coordenação.
- O comprovante no Drive passa a ser subido pela coordenação.
- O seed dos perfis **só acrescenta** permissões, de propósito, para não desfazer
  ajustes feitos direto na base. Tirar as duas da lista não mexe em base já
  existente: por isso a mudança vem com a migração
  `b3f5d0a71e29_comissario_sem_pagamentos_nem_checkin`.

### 2026-09-27 — Time de comissários por instituição, e responsável por criança

Decidido pela Luana. Uma instituição raramente é de um comissário só: às vezes
são 2 ou 3, e cada um responde por um punhado de crianças dali.

| | Versão inicial | Agora |
| --- | --- | --- |
| Comissários por instituição | já eram vários (nada impedia) | continuam vários, agora é a regra declarada |
| Quem alcança as crianças da instituição | todos os comissários dela | sem mudança: **todos**, o time inteiro |
| Quem responde por cada criança | não existia | `criancas.comissario_id`, uma coluna na planilha |

Consequências práticas:

- `criancas.comissario_id` é **organizacional, não de acesso**. O comissário
  continua vendo e trabalhando todas as crianças das instituições dele, mesmo
  as que estão no nome de outro — é o que significa ser um time. O campo
  responde a outra pergunta: com quem eu falo sobre esta criança.
- O responsável tem de ser do **time daquela instituição**: um comissário de
  outra escola, de outra cidade ou um monitor é recusado (422). A conferência
  vive em `_conferir_comissario`, no router de crianças.
- **Só a coordenação atribui** (`editar_criancas`). O comissário vê a coluna e
  não a muda.
- Quem deixa de alcançar a criança é **solto automaticamente**: quando a
  criança muda de escola, quando a instituição sai do vínculo do comissário,
  quando o vínculo é desativado e quando o perfil deixa de ser comissário. Um
  nome que não enxerga mais a criança é pior que nenhum.
- `GET /criancas/comissarios?edicao_id=` devolve o time da edição com as
  instituições de cada um — é o que alimenta o seletor da coluna. Sai só o
  nome, e pede `ver_criancas`.
