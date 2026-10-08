# Sistema Natal Lumen

Sistema interno de gestão do evento, publicado em `https://DOMINIO/acesso`.
O site público (pasta `site/` na raiz) é um projeto separado e não faz parte daqui.

- Especificação: [docs/ESPECIFICACAO.md](docs/ESPECIFICACAO.md)
- Identidade visual: [docs/IDENTIDADE_VISUAL.md](docs/IDENTIDADE_VISUAL.md)
- Padrões de UI: [docs/PADROES_UI.md](docs/PADROES_UI.md)
- Agradecimento: [docs/AGRADECIMENTO.md](docs/AGRADECIMENTO.md)
- Comprovante no Google Drive: [docs/COMPROVANTE_NO_DRIVE.md](docs/COMPROVANTE_NO_DRIVE.md)
- Homologação e produção: [docs/DOIS_AMBIENTES.md](docs/DOIS_AMBIENTES.md)

## Estado

| Fase | O que é | Situação |
| --- | --- | --- |
| 1 | Fundação do backend: 19 tabelas, migrations, seed de perfis | **pronta** |
| 2 | Autenticação e autorização | **pronta** |
| 3 | Fundação do frontend | **pronta** |
| 4 | Cadastros base (cidades, edições, instituições, usuários) | **pronta** |
| 5 | Crianças e importação de listas | **pronta** |
| 6 | Padrinhos, apadrinhamentos e pagamentos | **pronta** |
| 7 | Cartões: envio em lote e envio aos padrinhos | **pronta** |
| 8 | Kits, compras e check-in | **pronta** |
| 9 | Painel e relatórios | **pronta** |
| 10 | Publicação em /acesso | **pronta** |

---

## Backend

Requisitos: Python 3.12 e PostgreSQL 16.

```bash
brew install python@3.12 postgresql@16
brew services start postgresql@16
```

### Base de dados

```bash
psql -d postgres -c "CREATE ROLE natal_lumen LOGIN PASSWORD 'natal_lumen_dev';"
psql -d postgres -c "CREATE DATABASE natal_lumen OWNER natal_lumen;"
```

> Se o `psql` não estiver no PATH:
> `export PATH="$(brew --prefix postgresql@16)/bin:$PATH"`

### Instalação

```bash
cd backend
$(brew --prefix python@3.12)/bin/python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env     # e ajuste a senha da base
```

A instalação baixa cerca de 600 MB (era 2 GB antes de o EasyOCR sair) e leva
alguns minutos.

Gere um segredo de sessão próprio para o `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Migrations

Toda alteração de estrutura passa por migration — nunca `CREATE TABLE` a mão.

```bash
cd backend
./.venv/bin/alembic upgrade head              # aplica tudo
./.venv/bin/alembic revision --autogenerate -m "o que mudou"
./.venv/bin/alembic downgrade -1              # desfaz a última
./.venv/bin/alembic current                   # em que ponto a base está
```

A URL da base vem do `.env` (via `app/config.py`), não do `alembic.ini` — assim
o mesmo arquivo de migration serve para desenvolvimento e produção, e nenhuma
credencial fica versionada.

### Seed de perfis e permissões

```bash
cd backend
./.venv/bin/python -m app.seeds.perfis_permissoes
```

Cria as 14 permissões e os 4 perfis (Coordenação, Comissário, Monitor,
Estrutura). É idempotente: rodar de novo não duplica nada, e não desfaz ajustes
feitos direto na base — os perfis existem na base justamente para poderem ser
alterados sem mexer no código.

### Segurança

`tests/test_seguranca.py` não confere se o código *parece* seguro — ele **tenta
atacar** o sistema. Cada verificação é um ataque que falhou:

| O que tenta | Resultado |
| --- | --- |
| Ler, editar e apagar dados de outra cidade pelo ID | 404 — nem confirma que existe |
| Alcançar instituição vizinha, da mesma cidade | 404 |
| Forçar `edicao_id` / `instituicao_id` na query | Lista vazia |
| Forjar JWT com outro segredo, com `alg: none`, expirado | 401 nos três |
| POST sem CSRF, ou com CSRF de outra sessão | 403 |
| `' OR '1'='1`, `DROP TABLE`, `UNION SELECT` na busca | Sem efeito; tabelas intactas |
| `../../etc/passwd` em caminho de arquivo e em id | Recusado |
| Virar admin por campo extra no JSON | Ignorado |
| Upload de 20 MB, arquivo vazio, executável com nome de foto | 413 / 400 |
| Enumerar quem tem conta pelo login ou pelo "esqueci a senha" | Mesma resposta sempre |
| Usar sessão de conta desativada | 401 |
| Usar token copiado **depois** de o dono sair | 401 |

Também auditados:

- **as 57 rotas exigem autenticação** — verificado por introspecção do FastAPI,
  não por leitura. As únicas públicas são login, definir-senha, esqueci-senha e
  `/saude`;
- **sem `eval`, `exec`, `pickle`, `subprocess` ou SQL cru** em lugar nenhum;
- **sem `dangerouslySetInnerHTML`** no frontend — o React escapa tudo;
- **a senha nunca entra em log** nem volta em resposta;
- **dependências sem CVE conhecido** (`npm audit` e `pip-audit`).

Para repetir a auditoria de dependências:

```bash
cd frontend && npm audit --omit=dev
cd ../backend && ./.venv/bin/python -m pip_audit
```

### Backup

**Duas coisas não dão para refazer:** a base de dados e a pasta
`sistema/arquivos/` — as imagens dos cartões **e os comprovantes de
pagamento**. O resto está no git.

```bash
cd backend
./backup.sh                    # guarda em sistema/backups/
./backup.sh /Volumes/PenDrive  # ou onde você quiser
```

Guarde **uma cópia fora do computador** — nuvem, pen drive, outro disco. Um
backup que mora no mesmo disco que os dados não protege contra o que mais
acontece: o disco morrer.

Para conferir que o backup presta, restaure numa base descartável:

```bash
psql -d postgres -c "CREATE DATABASE teste_restauro OWNER natal_lumen"
pg_restore -h localhost -U natal_lumen -d teste_restauro backups/natal-lumen_DATA.dump
psql -d postgres -c "DROP DATABASE teste_restauro"
```

Backup que nunca foi restaurado não é backup — é esperança.

#### A planilha do dia

Junto com o backup, toda noite, o `gerar_planilha.py` monta uma **planilha
consolidada de cada edição ativa** e sobe para o Drive, na pasta "Planilhas
diárias", já convertida em Planilha Google. É para o dia em que o sistema cair:
a equipe continua acompanhando pela planilha da noite anterior.

Ela imita a "LISTA GERAL" que a coordenação mantinha à mão: **CÁLCULOS** (por
dia e instituição, com ônibus, apadrinhados, o que falta e as formas de
pagamento), **CONSOLIDADO** (todas as crianças), **uma aba por instituição**
(cada criança com o padrinho de cesta e de festa, pagamento, comissário, grupo,
cartões, autorização, kit e check-in), **PADRINHOS** e **FINANCEIRO**.

Cada noite é um arquivo novo (`Fortaleza 2026 — 2026-10-08`), e os anteriores
ficam. É só leitura: mexer nela não muda nada no sistema. Edição de teste (`ZZ`)
nunca sobe. Para gerar à mão e guardar o `.xlsx` numa pasta:

```bash
./.venv/bin/python gerar_planilha.py /uma/pasta
```

> ⚠️ `alembic downgrade base` **apaga todas as tabelas**. É útil em
> desenvolvimento e desastroso em produção. Faça backup antes de qualquer
> comando do Alembic que não seja `upgrade`.

### Testes

```bash
cd backend
./.venv/bin/python -m tests.test_esquema        # 22 verificações
./.venv/bin/python -m tests.test_autenticacao   # 52 verificações
./.venv/bin/python -m tests.test_cadastros      # 33 verificações
./.venv/bin/python -m tests.test_criancas       # 143 verificações
./.venv/bin/python -m tests.test_padrinhos      # 77 verificações
./.venv/bin/python -m tests.test_cartoes        # 27 verificações
./.venv/bin/python -m tests.test_lembretes      # 16 verificações
./.venv/bin/python -m tests.test_planilha       # 16 verificações
./.venv/bin/python -m tests.test_logistica      # 27 verificações
./.venv/bin/python -m tests.test_painel         # 29 verificações
./.venv/bin/python -m tests.test_seguranca      # 44 ataques barrados
```


`test_cadastros` cobre quem pode o quê nos cadastros: só a administração geral
cria cidades, edições e coordenadores; a coordenação só mexe na própria cidade;
e a instituição atribuída tem de ser da cidade da edição.

Todo dado criado por teste tem nome começando com `ZZ`, e cada bateria limpa o
que criou. Se alguma for interrompida no meio, ou depois de mexer no sistema
pelo navegador, limpe o que ficou:

```bash
./.venv/bin/python -m tests.limpar_dados_de_teste
```

Ele só apaga o que começa com `ZZ`, lista o que apagou, e **se recusa a rodar
com `AMBIENTE=producao`**. Ainda assim: não batize nada de verdade com `ZZ`.

`test_esquema` valida as restrições do banco com dados reais (um padrinho em
várias crianças, apadrinhamento entre cidades, unicidade de cartões e kits).

`test_autenticacao` cobre login e bloqueio, os atributos dos cookies, o CSRF, os
tokens de uso único e o isolamento de dados por edição e por instituição.

Nenhum dos dois deixa nada gravado na base.

### Primeiro acesso ao sistema

O sistema não tem cadastro aberto: as contas dos voluntários são criadas pela
coordenação, já de dentro. Para criar a primeira conta de administração geral:

```bash
cd backend
./.venv/bin/python -m app.seeds.criar_admin "Seu Nome" "voce@exemplo.org"
```

A conta nasce **sem senha**. O comando imprime um link de uso único, válido por
72 horas, em que a pessoa define a própria senha — a senha nunca passa pelo
terminal nem fica em histórico. Rodar de novo para a mesma conta gera um link
novo (útil se o anterior expirou ou a conta ficou bloqueada).

### Rodar a API

```bash
cd backend
./.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Documentação interativa em <http://localhost:8000/docs> (desligada em produção).

### Como a equipe entra no sistema

1. A coordenação cadastra a pessoa em **Usuários**, escolhendo edição e perfil.
   Para comissário e monitor, marca também as instituições pelas quais ela
   responde.
2. O sistema devolve um **link de primeiro acesso**, de uso único, válido por 72
   horas. A coordenação o envia à pessoa — em geral por WhatsApp.
3. A pessoa abre o link e define a própria senha. A senha nunca passa pela
   coordenação.

Se o link expirar ou se perder, o botão **Gerar link** cria outro e invalida o
anterior. Ele também solta a conta de um bloqueio por tentativas falhas.

### Rotas de autenticação

| Método | Rota | O que faz |
| --- | --- | --- |
| `POST` | `/auth/login` | Abre a sessão. Devolve o usuário, as permissões e os vínculos. |
| `POST` | `/auth/logout` | Encerra a sessão. |
| `GET` | `/auth/eu` | Quem está na sessão. O frontend chama ao abrir. |
| `POST` | `/auth/definir-senha` | Define a senha pelo link de uso único. |
| `POST` | `/auth/esqueci-senha` | Gera link de redefinição (2 h). |
| `GET` | `/saude` | Confere que a API está de pé. |

### Como funciona o acesso

**Sessão.** JWT de **4 horas** num cookie `httpOnly`, `SameSite=Strict`, com
`path=/acesso` — e `Secure` quando `AMBIENTE=producao`. O token nunca vai para o
`localStorage`.

A sessão é curta de propósito, e **isso não incomoda quem está trabalhando**:
faltando menos de uma hora para expirar, qualquer requisição renova o token
sozinha. Quem está usando o sistema nunca é interrompido; quem parou, expira.

**O logout encerra a sessão de verdade.** Um JWT se valida sozinho, sem tocar na
base — rápido, mas significa que apagar o cookie só resolvia no navegador de
quem clicou: uma cópia do token continuaria valendo até expirar. Agora o token
vai para a tabela `sessoes_revogadas`, e quem tiver uma cópia perde o acesso
junto. A tabela guarda cada token só até a data em que ele expiraria, e é
limpa no próprio logout — nunca cresce sem limite.

**Contra adivinhação de senha, duas camadas:**

- a **conta** trava por 15 minutos após 5 tentativas falhas — protege quem tem
  senha fraca;
- o **IP** é limitado a 10 tentativas por minuto no nginx — protege contra o
  ataque que a primeira camada não pega: testar uma senha comum contra mil
  emails diferentes, em que nenhuma conta chega a travar.

Testado: da sétima tentativa em diante, o nginx responde 429 e a API normal
segue respondendo.

**CSRF.** O JWT carrega um valor aleatório que também é gravado num segundo
cookie, `nl_csrf`, esse legível pelo JavaScript. Em todo `POST`, `PUT`, `PATCH`
e `DELETE`, o frontend copia esse valor para o cabeçalho `X-CSRF-Token`, e o
backend confere se bate com o que está dentro do token. Um site de terceiros não
consegue ler o cookie, então não consegue forjar o cabeçalho.

**Autorização.** Toda decisão acontece no backend; o frontend só esconde menus.
Cada rota declara a permissão que exige:

```python
@router.post("/cartoes")
def subir(ctx: ContextoAcesso = Depends(exige_permissao("subir_cartoes"))):
    ...
```

**Isolamento de dados (LGPD).** A permissão é por edição — a mesma pessoa pode
ser coordenação numa cidade e comissária noutra. As consultas são filtradas
pelas edições em que ela tem *aquela* permissão, e não por todas as suas
edições. Comissários e monitores ainda são limitados às instituições atribuídas
em `usuario_instituicao`. Use sempre o filtro do contexto:

```python
criancas = db.scalars(select(Crianca).where(ctx.filtro_criancas())).all()
```

Um comissário ou monitor **sem instituição atribuída não vê nenhuma criança** —
de propósito: o vínculo existe, mas a coordenação ainda não definiu por quais
instituições ele responde.

**Uma instituição é atendida por um time, e o time divide a lista.** Quase
nunca é um comissário só: são 2 ou 3, e cada um responde por um punhado de
crianças dali. Quem responde por cada uma fica em `criancas.comissario_id` —
que **também é o acesso**: o comissário só alcança as crianças com o nome dele,
e não a lista inteira da instituição. A instituição é a cerca de fora, a
criança é a cerca de dentro.

Criança sem responsável não aparece para nenhum comissário: só para a
coordenação, que é quem distribui a lista (`editar_criancas`). Enquanto ela não
distribuir, o comissário vê a tela vazia — de propósito, como já acontecia com
quem não tem instituição atribuída. O **monitor não muda**: ele continua com a
instituição inteira, porque o trabalho dele é da lista toda.

Tirar o nome dele de uma criança tira a criança da lista dele na hora. E quando
alguém deixa de alcançar a criança — ela muda de escola, a instituição sai do
vínculo dele, o vínculo é desativado, o perfil deixa de ser comissário — o nome
cai sozinho.

`admin_geral` alcança tudo, em todas as cidades.

**Log.** Login, logout, tentativa falhada, bloqueio e definição de senha vão para
`log_atividades`. O registro entra na mesma transação da ação, para nunca existir
log de algo que acabou desfeito.

### Organização

| Pasta | Responsabilidade |
| --- | --- |
| `app/config.py` | configuração lida do `.env` |
| `app/database.py` | engine, sessão e a classe `Base` |
| `app/models/` | as 19 tabelas: `operacao` · `apadrinhamento` · `logistica` · `acesso` |
| `app/schemas/` | entrada e saída das rotas (Pydantic) |
| `app/routers/` | as rotas, cada uma declarando a permissão exigida |
| `app/seguranca/` | senhas, JWT, CSRF e as dependências de autorização |
| `app/servicos/` | regra de negócio sem HTTP (digitalização, importação, arquivos, log) |
| `app/seeds/` | dados iniciais |
| `alembic/versions/` | histórico de migrations |

### Códigos das crianças

As instituições mandam a lista **sem código** — nome, idade, sexo e instituição.
Quem numera é a aplicação, e a ordem é sempre a mesma:

1. **meninas primeiro**, depois meninos;
2. dentro de cada grupo, da **menor para a maior idade**;
3. dentro de cada idade, **ordem alfabética**.

O código é a **sigla da instituição** mais um número: `ES00`, `ES01`, `ES02`. A
sigla é sugerida a partir do nome (`Escolinha Sol` → `ES`, `Creche Lar da
Criança` → `CL`) e pode ser trocada na tela de Instituições. Ela é única dentro
da cidade, para dois códigos iguais nunca apontarem para instituições
diferentes.

Uma segunda lista da mesma instituição continua a numeração de onde a primeira
parou, em vez de repetir códigos.

**Trocar a sigla leva os códigos junto.** Mudar a sigla de uma instituição que
já tem crianças cadastradas troca o prefixo de todas elas, em todas as edições:
`ES04` vira `SL04`. O **número de cada criança não muda** — só o prefixo —, e a
tela diz quantos códigos mudaram, porque listas e crachás já impressos ficaram
desatualizados. Código que veio escrito na planilha da instituição (`001`,
`CSV1`) não tem sigla para trocar e fica como está. Estrear uma sigla numa
instituição que não tinha nenhuma também não mexe no que já existe.

**Renumerar.** Se a lista entrou fora de ordem, ou depois de corrigir idades e
sexos que vieram errados da planilha, o botão *Renumerar códigos* refaz a
instituição inteira pela regra. Os códigos **mudam** — crachás já impressos
ficam desatualizados, e a tela avisa isso antes.

Toda listagem de crianças sai ordenada por código.

### Importação de listas

As instituições mandam planilhas com o seu próprio jeito de nomear as colunas.
O importador normaliza tudo antes de comparar — tira acento, ignora a caixa e
os espaços — então `nome`, `Nome`, `NOME` e `  Nome  ` são a mesma coisa.

O reconhecimento tem **dois passes**:

1. **Cabeçalho igual** a um dos aceitos: `Nome`, `Nome Completo`, `Nome da
   Criança`, `Nome do Aluno`, `Matrícula`, `Cod`, `Nº`, `Idade`, `Anos`,
   `Sexo`, `Gênero`, `M/F`, `Escola`, `Creche`, `Entidade`, `Obs`…
2. **Cabeçalho que contenha** um deles, como palavra inteira. É o que resgata
   `Nome Completo da Criança (sem abreviar)` ou `Nome do Beneficiário`, que
   nenhuma lista preveria.

No segundo passe os campos são procurados numa ordem definida, com `nome` por
**último**. Assim uma planilha com `Nome da Instituição` e `Nome da Criança`
lado a lado acerta as duas: a instituição é reconhecida antes, e sobra a
criança para `nome`.

**O cabeçalho não precisa estar na primeira linha.** Planilha que começa com
título, subtítulo e linha em branco é comum. O importador procura nas dez
primeiras linhas e escolhe a que reconhece mais colunas — exigindo, no mínimo,
a de nome. A numeração das linhas na conferência continua batendo com a que
aparece no Excel, para você achar o problema rápido.

No CSV, o separador é testado um a um (`;` `,` tab `|`) em vez de adivinhado:
com um título na primeira linha, o palpite automático do pandas corta por
espaços. E as linhas são lidas com o módulo `csv` e igualadas em largura —
senão um título de uma célula só faria o pandas esperar uma coluna e quebrar na
linha do cabeçalho.

**Formatos aceitos**, todos testados:

| | |
| --- | --- |
| `.xlsx` | planilha do Excel |
| `.csv` separado por `;` ou `,` | o separador é detectado sozinho |
| sem coluna de código | o normal: a aplicação numera |
| cabeçalho fora da primeira linha | título e subtítulo antes da tabela |
| CSV UTF-8 **com BOM** | o que o Excel grava em "Salvar como > CSV UTF-8" |
| CSV em Windows-1252 | Excel mais antigo em português |
| idade escrita em texto | `2 ANOS`, `10a`, `1 ano e 6 meses`, `18 meses` → 1 |

> O BOM já quebrou a importação em produção: são três bytes **invisíveis** no
> começo do arquivo, e a mensagem de erro dizia que faltava a coluna `Codigo`
> enquanto listava `Codigo` entre as encontradas — porque na tela as duas
> pareciam idênticas. Hoje o BOM, o espaço inquebrável e os caracteres de
> largura zero são removidos antes de comparar.

A importação tem duas etapas, e **nada é gravado na primeira**:

1. `POST /criancas/importar` lê a planilha e devolve a conferência — quais
   colunas reconheceu, quais linhas estão prontas e quais têm problema.
2. `POST /criancas/importar/{id}/confirmar` grava só as linhas válidas.

O que vira **erro** (não importa): sem código, sem nome, idade ou sexo
inválidos, código repetido dentro da planilha, criança já cadastrada nesta
edição, instituição não reconhecida.

A idade aceita o jeito que a instituição escreveu — `8`, `8 ANOS`, `10a`,
`1 ano e 6 meses`, e meses viram anos completos (`18 meses` → 1). Só é erro o
que não tem número (`não informada`) ou o que é data de nascimento em vez de
idade (`04/03/2015`), e aí a mensagem mostra o que estava escrito na célula.

O que vira **aviso** (importa, mas aparece na conferência): nome muito parecido
com o de outra criança — da base ou da própria planilha. É só aviso porque
irmãos com nomes parecidos existem; quem confere decide. A comparação usa
`rapidfuzz` com corte em 88 de semelhança, ajustável em
`app/servicos/importador.py`.

### A tela de crianças

É o centro de controle da edição, não uma lista. Com 20+ instituições e mais de
1500 crianças, ela funciona como planilha:

- **uma aba por instituição**, com a contagem e quantas estão sem padrinho; um
  ponto âmbar marca a aba que tem pendência, para a coordenação achar o atraso
  sem abrir aba por aba;
- **as colunas não se mexem ao trocar de aba** — largura e posição vêm de um
  `<colgroup>` com `table-layout: fixed`, e a coluna Instituição aparece sempre,
  mesmo numa aba de instituição só. Informação que muda de lugar a cada clique
  obriga a reencontrar tudo de novo;
- **células editáveis** — clique para editar, Enter salva e desce para a linha
  seguinte, Esc desfaz;
- **marcadores de estado** em cada linha: padrinho de cesta e de festa, cartões
  (de 2), kit e check-in. O panorama inteiro da criança numa olhada;
- **edição em lote**: marque várias e aplique o dia do evento de uma vez —
  distribuir 1500 crianças uma a uma não é trabalho que alguém faça;
- **ficha da criança** no ícone de olho: uma janela pequena com tudo o que se
  sabe dela — padrinhos com nome e contato, cartões, kit e check-in.

### O dia do evento é da instituição

Se a Escolinha Sol vai no sábado, **todas** as crianças dela vão no sábado. Por
isso o dia não é editado criança a criança: é um **campo do cadastro da
instituição**, preenchido em Instituições — ao criar ou ao editar — e todas as
crianças dela mudam junto.

Como o dia é por edição, a tela de Instituições tem um seletor de edição no
topo, e a lista passa a mostrar só as instituições da cidade daquela edição.

Editar o dia de uma criança isolada foi **removido** da API e da tela — não é
uma restrição de interface que dá para contornar pelo backend. `app/servicos/
dias.py` é o único lugar que grava `criancas.dia_evento_id`.

Crianças criadas ou importadas depois herdam o dia que a instituição já tem, e
mudar uma criança de instituição leva junto o dia da nova.

> O **contato do padrinho só aparece para quem tem `ver_padrinhos`**. Um monitor
> abre a mesma ficha e vê *que* a criança tem padrinho de cesta e de festa, mas
> não o nome nem o telefone: contato de doador é dado de quem doa, não da
> criança. O WhatsApp vira link `wa.me` para abrir a conversa direto.

O panorama de todas as linhas vem em **3 consultas**, não uma por criança: numa
edição de 1500, o jeito ingênuo custaria 4500 consultas e a tela nunca abriria.

> ⚠️ O teste de navegador **nunca deve rodar contra dados reais** — ele edita
> registros pela interface. Use `python -m tests.preparar_navegador`, que cria
> cidade, edição, instituições, crianças e conta próprias com prefixo `ZZ`.
> Identifique linhas pelo **código**, nunca pela posição: a lista reordena ao
> editar um nome, e um teste que edita "a primeira linha" duas vezes acaba
> mexendo em duas crianças diferentes.

### Busca por código: o escape do filtro

Comissários e monitores só enxergam as crianças das instituições atribuídas a
eles. A exceção é a busca por **código exato**, que alcança qualquer instituição
das edições do usuário — necessária porque apadrinhamento entre cidades é
permitido. Todo uso dela vai para `log_atividades` com a ação
`busca_por_codigo`. Listagens e buscas por nome nunca escapam do filtro.

### Apadrinhamento

Um padrinho pertence a uma **edição** (cidade + ano) e não persiste entre anos —
o mesmo doador em 2027 é um registro novo. Ele pode apadrinhar **várias
crianças**; o que é único é o par (criança, tipo): cada criança tem no máximo um
padrinho de cesta e um de festa.

**Entre cidades é permitido.** Quando acontece, o valor vem da edição da
**criança** (é ela que define quanto custa a cesta e a festa daquele evento), e o
registro fica visível pelos dois lados: para quem alcança a edição do padrinho e
para quem alcança a da criança.

O valor é **copiado** no momento do registro. Se a edição mudar os valores
depois, o que já foi combinado com o padrinho não muda.

Do lado do padrinho, a criança aparece apenas pelo **primeiro nome e idade**,
como a especificação exige.

A ficha do padrinho tem três abas, e a de **Pagamento** faz duas coisas: registra
o próximo pagamento (marcando o que ele quita, com o comprovante obrigatório e
uma observação) e lista os que já existem, cada um com o comprovante para baixar
ou trocar. A pergunta "ele já pagou isso?" nasce no mesmo lugar em que se
registra o pagamento.

### Financeiro

Todo o dinheiro da edição numa tela só, em duas abas — porque são dois
lançamentos e **duas permissões**:

| Aba | O que entra | Permissão |
| --- | --- | --- |
| Saídas | todo gasto da edição: cestas, presentes, estrutura, transporte | `gerenciar_compras` |
| Recebimentos | tudo o que entrou: o pagamento dos padrinhos e o que chega solto | `registrar_pagamentos` |

Quem tem só uma das duas permissões vê só a sua aba — e nesse caso a faixa de
abas nem aparece. O **saldo** (recebido menos saídas) só existe para quem alcança
as duas metades: com meia conta na mão, um saldo seria um número errado com cara
de certo.

#### A lista de recebimentos junta duas tabelas

Não existe tela separada de pagamentos: **o pagamento de um padrinho é uma linha
da lista de recebimentos.** Quem fecha o caixa quer ver todo o dinheiro que
entrou de uma vez, e não em dois lugares.

| Origem | Tabela | Como nasce |
| --- | --- | --- |
| apadrinhamento | `pagamentos` | o padrinho paga o que apadrinhou — pela ficha dele, ou pelo formulário do financeiro |
| solto | `recebimentos` | doação, patrocínio, rifa: dinheiro sem criança do outro lado |

A linha **não é uma copia**: é o próprio pagamento, lido de lado. `fonte` diz de
qual tabela ela veio, e é por ela que a tela sabe onde cada ação bate — conferir,
subir comprovante e remover mudam de endereço, não de significado.

#### A categoria do apadrinhamento é derivada, não digitada

São quatro categorias na hora de registrar:

| Escolha | O que acontece |
| --- | --- |
| Apadrinhamento - cesta | pede o padrinho e marca quais **cestas** em aberto o dinheiro quita → grava um `pagamento` |
| Apadrinhamento - festa | o mesmo, com as **festas** em aberto |
| Doação | grava um `recebimentos` com quem doou |
| Outros | idem, para o que não é doação nem apadrinhamento |

Na lista, a categoria de uma linha de apadrinhamento **sai do que o pagamento
quita** (só cesta, só festa, ou "Apadrinhamento" quando cobre os dois juntos, ou
quando ainda não quita nada). Não é um campo gravado: um campo poderia dizer
"cesta" num dinheiro que pagou festa, e isto não pode.

Só `doacao` e `outros` são gravadas, com CHECK na base — a lista fechada está em
`CategoriaRecebimento`, e acrescentar uma categoria é uma migration de CHECK.

#### Comprovante e conferência valem para as duas origens

Qualquer linha guarda comprovante, e a coluna mostra o arquivo (baixar, trocar,
link do Drive quando existe) ou a etiqueta `falta`.

**Pagamento de padrinho não se registra sem comprovante**: o botão espera o
arquivo, nos dois lugares onde se registra (a ficha do padrinho e o formulário
do Financeiro). Sem ele ninguém confere depois se o valor chegou. Doação e
"outros" seguem podendo entrar sem arquivo — dinheiro deixado na caixinha às
vezes não tem recibo, e recusar o lançamento faria a edição perder o registro do
dinheiro em vez de ganhar a prova dele.

A exigência é da **tela**, não do servidor: o arquivo sobe numa segunda
requisição, e se ela falhar o dinheiro já está gravado — recusá-lo aí perderia a
quitação por causa do arquivo. Quem ficou sem arquivo aparece com `falta` e
recebe o comprovante depois.

Tanto o pagamento quanto o recebimento têm **observação** (caixa de texto), para
o que não cabe em valor, data e forma. Ela aparece como dica do mouse na linha do
Financeiro e embaixo do valor na ficha do padrinho. O recibo de uma doação prova
a mesma coisa que o de um apadrinhamento, e uma coluna que só funcionasse em
metade das linhas mentiria na outra metade. O trabalho de guardar, trocar,
espelhar no Drive e entregar o arquivo é um só: `app/servicos/comprovantes.py`.

Mesma coisa com `conferido`: é a marca de quem conferiu o dinheiro contra o
comprovante, e vale para as duas origens.

Três filtros, que é para isso que a tela existe no dia a dia: **categoria**, o
que ainda não foi **conferido** e o que está **sem comprovante**. Os filtros
cortam a lista e **nunca os totais** — os totais respondem "qual é o caixa", e um
caixa que muda quando se filtra a tela não é caixa nenhum.

No banco, as saídas continuam na tabela `compras` — é o que ela era quando
nasceu, e o histórico em `log_atividades` aponta para esse nome.

### Cartões

Cada criança escreve dois cartões, um para cada padrinho. Eles sobem **em
lote**, em duas etapas, como a importação de planilha:

1. `POST /cartoes/lote` recebe a pilha de fotos, o **tipo** (cesta ou festa) e a
   edição. Para cada arquivo: encontra a criança pelo **código no nome do
   arquivo**, corrige a perspectiva (escala de cinza → blur → Canny → contornos
   → `warpPerspective`) e devolve uma miniatura para conferência. Nada é gravado.
2. `POST /cartoes/lote/{id}/confirmar` guarda os arquivos e grava os cartões.

**A criança é identificada pelo código, não pelo nome escrito no cartão.**
Houve OCR aqui (EasyOCR) lendo o nome para o monitor conferir. Saiu: errava — num
cartão de teste com "BRUNO" escrito, leu "INPI" — e levava junto 609 MB de disco
e 884 MB de RAM por worker. O app inteiro cabe em 152 MB agora.

O casamento do nome do arquivo está em `app/servicos/nomes_de_arquivo.py`, e é
deliberadamente desconfiado: `IMG_20261110_SL12.jpg` casa, mas nome que bate com
dois códigos vira erro, e código puramente numérico só casa se o nome do arquivo
for exatamente ele (`IMG_20261110_001.jpg` contém "001" **e** "010").

Se as bordas não forem encontradas, a foto é usada como está e a resposta traz o
aviso `bordas não detectadas` — uma foto torta ainda serve, e travar o monitor no
dia do evento seria pior.

A orientação EXIF é corrigida: foto de celular guarda a rotação na tag em vez de
girar os pixels.

**O destinatário não fica gravado no cartão.** É encontrado por
criança + tipo → apadrinhamento → padrinho. Assim o cartão pode ser digitalizado
antes de a criança ter padrinho — que é o que acontece na prática.

Um cartão só pode ser marcado como enviado quando já existe padrinho para
recebê-lo.

**Prévia abandonada.** Quem sobe um lote e nunca confirma deixa as imagens na
pasta temporária. A cada prévia nova o servidor varre o que tem mais de 12h e
apaga — sem isso ficariam fotos de cartão de criança ocupando disco sem nenhuma
linha no banco apontando para elas.

### Lembrete do evento

Na semana do evento cada padrinho recebe um lembrete com os cartões das crianças
dele — **uma mensagem por dia do evento**, cada uma com os cartões das crianças
daquele dia. Só fica pronto quem tem todos os cartões do dia subidos. As regras,
o texto da mensagem e o que falta para o disparo estão em
[`docs/LEMBRETE_DO_EVENTO.md`](docs/LEMBRETE_DO_EVENTO.md).

### Kits

A lista de kits parte das **crianças**, não dos kits: a criança existe desde a
importação e o kit só ganha registro quando alguém mexe nele. Sem isso a equipe
de estrutura não veria quem ainda falta — e é justamente essa a informação que
ela precisa.

Os estados mudam em lote (a equipe monta dezenas de uma vez). Voltar de
"entregue" para "montado" limpa a hora de entrega, para não sobrar data de
entrega num kit que voltou para a bancada.

### Check-in

No dia do evento, quem está na porta lê o QR do crachá — ou digita o código. O
check-in **nunca é recusado**: deixar a criança esperando na porta seria pior do
que qualquer inconsistência. O que estiver estranho volta como aviso na tela:

- a criança já tinha feito check-in;
- o dia dela não é hoje, ou ela não está marcada em nenhum dia;
- o kit ainda não está montado;
- ela não tem padrinho;
- faltam cartões digitalizados.

`GET /checkin/qrcode/{crianca_id}` gera o QR para imprimir no crachá. Ele traz
`edicao:codigo`, e a tela aceita os dois formatos — colado do leitor ou digitado
à mão.

### Painel

`GET /painel/{edicao_id}` devolve os números da edição: crianças, apadrinhamentos
(feitos sobre possíveis, que são dois por criança), quantas crianças já têm os
dois padrinhos, valores combinado e pago, cartões digitalizados e enviados,
kits, compras e check-ins — mais a quebra por instituição e por dia.

**Os números respeitam o mesmo filtro das telas.** Quem só alcança algumas
instituições vê os números dessas instituições, não os da edição inteira. Um
relatório que vazasse o total geral para quem não pode ver as crianças seria uma
brecha silenciosa.

> A permissão `ver_painel` é, pela especificação, só da Coordenação. Por isso a
> página `/acesso/painel` funciona para todo mundo — é a porta de entrada, com os
> atalhos do que cada um alcança — mas **os números só aparecem para quem tem a
> permissão**. Para abrir os números a outros perfis, basta acrescentar
> `ver_painel` ao perfil na base, sem mexer no código.

### Arquivos enviados

Ficam em `ARQUIVOS_DIR` (por padrão `sistema/arquivos/`), **fora** das pastas
públicas do frontend. Nunca são servidos diretamente: só por
`GET /cartoes/{id}/imagem`, que confere permissão e alcance antes de devolver o
arquivo. A pasta está no `.gitignore` — são dados sensíveis (LGPD).

Organização e nomes, como a especificação define:

```
{ARQUIVOS_DIR}/cartoes/{CIDADE}/{ano}/{INSTITUICAO}_{NOME}_{TIPO}.jpg
```

Tudo em maiúsculas, sem acento, espaços viram `_`, só A-Z 0-9 e `_`. Se o nome
já existir, ganha `_2`, `_3` e assim por diante.

Caminhos vindos da base passam por `dentro_da_pasta()`, que recusa qualquer um
que escape de `ARQUIVOS_DIR` — sem isso, um caminho como `../../etc/passwd`
gravado na base viraria leitura de arquivo do servidor.

---

## Frontend

React 19 + Vite, JavaScript (sem TypeScript), como o site.

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Abre em <http://localhost:5173/acesso/>. **O backend precisa estar rodando**: o
Vite encaminha `/acesso/api` para `http://localhost:8000`, removendo o prefixo —
igual ao que o nginx fará em produção.

```bash
npm run lint     # oxlint
npm run build    # build de produção em dist/
npm run preview  # serve o build
```

### Telas

| Rota | O que é | Quem alcança |
| --- | --- | --- |
| `/acesso/entrar` | Login | qualquer um |
| `/acesso/definir-senha?token=...` | Primeiro acesso e redefinição de senha | quem tem o link |
| `/acesso/esqueci-senha` | Pede o link de redefinição | qualquer um |
| `/acesso/painel` | Painel inicial, com atalhos do que o perfil alcança | com sessão |
| `/acesso/usuarios` | Equipe, vínculos e instituições atribuídas | `gerenciar_usuarios` |
| `/acesso/instituicoes` | Instituições da cidade | `gerenciar_cadastros` |
| `/acesso/cidades-edicoes` | Cidades, edições e dias do evento | `admin_geral` |
| `/acesso/criancas` | Lista, cadastro, importação e o comissário responsável | `ver_criancas` |
| `/acesso/padrinhos` | Padrinhos e apadrinhamentos | `ver_padrinhos` |
| `/acesso/padrinhos/envio-de-cartoes` | O lembrete do evento: quem já pode receber, por dia | perfil Coordenação (e admin geral) |
| `/acesso/cartoes` | Digitalização, conferência e envio | `ver_criancas` |
| `/acesso/kits` | Montagem e entrega dos kits | `gerenciar_kits` |
| `/acesso/financeiro` | Saídas e recebimentos da edição (com os pagamentos dos padrinhos), comprovantes e saldo | `gerenciar_compras` **ou** `registrar_pagamentos` |
| `/acesso/checkin` | Entrada das crianças no dia | `fazer_checkin` |

`/acesso` sem sessão cai no login; com sessão, vai para o painel.

### Organização

| Pasta | Responsabilidade |
| --- | --- |
| `src/services/` | `api.js` (fetch com cookie e CSRF) e `auth.js` |
| `src/contexts/` | sessão: usuário, permissões e edição ativa |
| `src/routes/` | `RotaProtegida` — exige sessão e, se pedido, uma permissão (ou qualquer uma de uma lista) |
| `src/components/core/` | `Button` (portado do site), `Campo` |
| `src/components/layout/` | cabeçalho, menu, rodapé e a casca |
| `src/components/feedback/` | `EmptyState` (portado), `Carregando`, `Mensagem` |
| `src/styles/` | `tokens.css` (cópia do site), `base.css`, `layout.css` |
| `src/pages/` | as telas |

### Identidade visual

Os arquivos visuais foram **copiados** de `site/`, nunca importados — 11 fontes,
o mascote, a textura de estrelinhas e o `tokens.css` inteiro, sem alterar um
valor. O que o site não tinha (campos, tabelas, mensagens, carregamento,
navegação de aplicação) foi criado aqui sobre os mesmos tokens. Ver
[docs/IDENTIDADE_VISUAL.md](docs/IDENTIDADE_VISUAL.md).

**Celular.** O site público esconde o menu abaixo de 860px. Aqui não dá: muitos
voluntários usam o sistema pelo telefone. No mesmo ponto de quebra, o menu vira
uma gaveta de verdade — com botão, fundo escurecido, fecho por Esc e ao navegar.

### Como o frontend conversa com a API

O cookie de sessão é `httpOnly`: o JavaScript não consegue lê-lo, só perguntar
ao backend quem está na sessão (`GET /auth/eu`, feito uma vez ao abrir a
página). Todo pedido vai com `credentials: "include"`, e nos métodos que alteram
dados o `api.js` copia sozinho o cookie `nl_csrf` para o cabeçalho
`X-CSRF-Token` — nenhuma tela precisa se lembrar disso.

O `pode(permissao)` do contexto **apenas esconde menus**. Quem decide o acesso é
o backend, em cada rota.

---

## Rodando tudo junto

Dois terminais:

```bash
# terminal 1 — API
cd backend && ./.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# terminal 2 — telas
cd frontend && npm run dev
```

Depois abra <http://localhost:5173/acesso/>.

Na primeira vez, crie sua conta e abra o link que o comando imprime:

```bash
cd backend
./.venv/bin/python -m app.seeds.criar_admin "Seu Nome" "voce@exemplo.org"
```

> Se a porta 5173 estiver ocupada, o Vite sobe noutra e avisa no terminal — mas
> aí o endereço muda. Confira a linha `Local:` antes de abrir o navegador.

## Publicação

> **Nunca publicou este sistema?** Comece pelo
> [docs/HOSPEDAGEM.md](docs/HOSPEDAGEM.md) — passo a passo completo, do
> contratar a VPS ao cadeado do HTTPS, escrito para quem não administra
> servidor. Esta seção aqui é o resumo para quem já conhece o caminho.

```
natallumen.com                      → Shopify: loja e site público
acesso.natallumen.com/acesso        → sistema   sistema/frontend/dist
acesso.natallumen.com/acesso/api    → API       uvicorn em 127.0.0.1:8000
teste.natallumen.com                → homologação, mesma coisa noutra máquina
```

O site público **não é servido por este servidor**: ele vive no Shopify, no
domínio raiz. O nginx daqui atende só o subdomínio do sistema.

Frontend e API no mesmo domínio é o que permite o cookie de sessão `httpOnly`
com `SameSite=Strict` e `path=/acesso`, sem CORS em produção.

O prefixo `/acesso` continua no caminho mesmo agora que o sistema tem
subdomínio próprio: ele está gravado no `base` do [vite.config.js](frontend/vite.config.js),
no `cookie_path` e no `root_path` do [config.py](backend/app/config.py). O nginx
redireciona a raiz do subdomínio para `/acesso/`, então quem digita
`acesso.natallumen.com` cai direto na tela de entrada.

Os arquivos prontos estão em [publicacao/](publicacao/):

| Arquivo | O que é |
| --- | --- |
| `nginx.conf` | Configuração do nginx, com os três caminhos acima |
| `natal-lumen-api.service` | Unidade systemd da API |
| `publicar.sh` | Atualiza uma instalação já existente |

### Primeira instalação

No servidor (Ubuntu/Debian):

```bash
sudo apt install python3.12 python3.12-venv postgresql nginx git curl rsync

# O OpenCV endireita a foto do cartao e exige estas duas, que nao vem num
# servidor sem tela. Sem elas a API NAO SOBE: libGL.so.1: cannot open shared
# object file.
sudo apt install libgl1 libglib2.0-0

# O nodejs do Ubuntu 24.04 e o 18; o Vite 8 exige 20+.
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install nodejs
```

Dois usuarios, com papeis diferentes: um administrador que publica (`lumen`,
dono da pasta e com `sudo`) e um usuario de servico sem poder nenhum
(`natal-lumen`), que so roda o uvicorn.

```bash
sudo adduser --system --group natal-lumen

sudo mkdir -p /var/www/natal-lumen
sudo chown lumen:lumen /var/www/natal-lumen
git clone SEU_REPO /var/www/natal-lumen
cd /var/www/natal-lumen
```

Base de dados:

```bash
sudo -u postgres psql -c "CREATE ROLE natal_lumen LOGIN PASSWORD 'uma-senha-forte';"
sudo -u postgres psql -c "CREATE DATABASE natal_lumen OWNER natal_lumen;"
```

Backend:

```bash
cd sistema/backend
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt

cp .env.example .env
```

No `.env` de produção, obrigatoriamente:

```
DATABASE_URL=postgresql+psycopg://natal_lumen:uma-senha-forte@localhost:5432/natal_lumen
JWT_SECRET=<gere um novo, veja abaixo>
AMBIENTE=producao
ARQUIVOS_DIR=/var/www/natal-lumen/sistema/arquivos
```

```bash
./.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"

# O .env é do usuário do serviço: é ele quem roda a aplicação, e a aplicação
# lê este arquivo além de recebê-lo pelo systemd. Com o dono errado, a API
# sobe e morre em PermissionError.
sudo chown natal-lumen:natal-lumen .env
sudo chmod 600 .env

sudo mkdir -p /var/www/natal-lumen/sistema/arquivos
sudo chown -R natal-lumen:natal-lumen /var/www/natal-lumen/sistema/arquivos

# Daqui em diante, como o usuário do serviço — é quem consegue ler o .env.
sudo -u natal-lumen ./.venv/bin/alembic upgrade head
sudo -u natal-lumen ./.venv/bin/python -m app.seeds.perfis_permissoes
sudo -u natal-lumen ./.venv/bin/python -m app.seeds.criar_admin "Seu Nome" "voce@exemplo.org"
```

> O `criar_admin` imprime o link de primeiro acesso, válido por 72 horas.
> **Guarde:** é por ele que você define a própria senha. Perdeu? Rode de novo.

> `AMBIENTE=producao` muda três coisas: o cookie passa a exigir HTTPS
> (`Secure`), o CORS é desligado (desnecessário no mesmo domínio) e o `/docs`
> some.

Frontend:

```bash
cd ../frontend
npm ci
npm run build
```

Serviço e nginx:

```bash
cd ../publicacao
sudo cp natal-lumen-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now natal-lumen-api

sudo cp nginx.conf /etc/nginx/sites-available/natal-lumen
sudo sed -i 's/SUBDOMINIO/acesso.natallumen.com/g' /etc/nginx/sites-available/natal-lumen
sudo ln -s /etc/nginx/sites-available/natal-lumen /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default /var/www/html/index.nginx-debian.html
sudo nginx -t && sudo systemctl reload nginx

# O nginx.conf é só HTTP de propósito: é o certbot que promove para HTTPS,
# aponta o certificado e cria o redirect de 80 para 443.
sudo certbot --nginx -d acesso.natallumen.com
```

Confira: `curl https://acesso.natallumen.com/acesso/api/saude` deve responder
`{"ok":true,"ambiente":"producao"}`.

### Atualizações

```bash
cd /var/www/natal-lumen
DOMINIO=acesso.natallumen.com REF=v2026.1 ./sistema/publicacao/publicar.sh
```

Ele busca a versão nova, instala dependências, **roda as migrations antes de
reiniciar** (o código novo costuma esperar o esquema novo), reconstrói o
frontend, reinicia a API e confere se ela respondeu.

A conferência é em duas etapas: primeiro direto no uvicorn
(`127.0.0.1:8000/saude`), que responde "a API subiu?", e depois — só se você
passar `DOMINIO` — a volta inteira pelo nginx e pelo HTTPS, que responde "o
caminho público está certo?". Separar as duas diz onde olhar quando falha:
journalctl para a primeira, log do nginx para a segunda.

### Detalhes que costumam morder

**A barra no fim do `proxy_pass`.** `proxy_pass http://127.0.0.1:8000/;` remove
o prefixo `/acesso/api` antes de encaminhar. A aplicação atende em
`/auth/login`, não em `/acesso/api/auth/login` — o `root_path` do FastAPI serve
só para ela montar links e documentação. Sem a barra, tudo dá 404.

**`try_files ... /acesso/index.html`.** Sem isso, abrir `/acesso/criancas`
direto no navegador dá 404: quem conhece essa rota é o React Router, não o
nginx.

**`ARQUIVOS_DIR` não é servido pelo nginx.** As imagens dos cartões só saem por
`GET /acesso/api/cartoes/{id}/imagem`, que confere sessão e permissão antes.
Apontar o nginx para essa pasta abriria as fotos a quem tivesse o link.

**Backup.** O que não dá para refazer são dois: a base (`pg_dump natal_lumen`) e
a pasta `sistema/arquivos/` (imagens dos cartões e comprovantes de pagamento —
registro financeiro, guarde com o mesmo cuidado da base). O resto está no git.
