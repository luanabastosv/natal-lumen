"""Seed das permissoes e dos perfis.

Os perfis e permissoes vivem na base justamente para poderem ser alterados sem
mudar codigo. Este seed cria o estado inicial e e idempotente: rodar de novo nao
duplica nada.

Rodar com:  python -m app.seeds.perfis_permissoes
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Perfil, Permissao

# codigo -> descricao
# gerenciar_cadastros nao estava na lista original da especificacao: foi
# acrescentada porque instituicoes e dias do evento precisavam de dono. Vai
# so para a Coordenacao, entao na pratica nada mudou de alcance.
PERMISSOES: dict[str, str] = {
    "ver_painel": "Ver o painel inicial e os indicadores da edicao",
    "ver_criancas": "Ver a lista e os dados das criancas",
    "editar_criancas": "Criar, editar e excluir criancas",
    "importar_listas": "Importar listas de criancas enviadas pelas instituicoes",
    # Poder ESTREITO, separado de editar_criancas de proposito: muda so quem
    # responde pela crianca, e nada mais dela. Quem coordena a captacao precisa
    # redistribuir a lista entre os comissarios do time — e nao precisa criar,
    # renomear nem apagar crianca para isso.
    "atribuir_comissario": "Definir o comissario responsavel por uma crianca",
    "ver_padrinhos": "Ver a lista e os dados dos padrinhos",
    "editar_padrinhos": "Criar e editar padrinhos e apadrinhamentos",
    # O dinheiro que ENTRA se separa em duas permissoes desde 30/09/2026,
    # quando o comissario passou a poder registrar o pagamento dos padrinhos
    # dele. As duas existem porque sao dois alcances muito diferentes:
    #
    #   registrar_pagamentos_padrinho  o pagamento de um padrinho que ele
    #       alcanca. E o que CONFIRMA o apadrinhamento (promessa nao conta),
    #       entao sem isto o comissario dependeria da coordenacao para que o
    #       trabalho dele aparecesse em qualquer numero.
    #   registrar_pagamentos  a aba Recebimentos do financeiro: TODO o dinheiro
    #       que entra na edicao, doacao e patrocinio inclusive, com o poder de
    #       lancar, remover e CONFERIR. Continua so com a coordenacao — abrir
    #       isto a cada comissario mostraria o caixa inteiro da edicao a quem
    #       so precisa registrar o proprio padrinho.
    #
    # Conferir e apagar pagamento ficam com a coordenacao de proposito: quem
    # registra o dinheiro nao e quem audita o registro.
    "registrar_pagamentos_padrinho": "Registrar o pagamento dos padrinhos que alcanca",
    "registrar_pagamentos": "Registrar os recebimentos da edicao e conferir pagamentos",
    # Desfazer engano de captacao: apagar o cadastro de um padrinho, e desfazer
    # um apadrinhamento MESMO ja pago. Separada de `editar_padrinhos` porque nao
    # e a mesma coisa: quem capta corrige o que acabou de digitar; isto aqui
    # desfaz o que ja virou numero no painel e, no caso do pagamento, mexe onde
    # ha dinheiro. Fica so com a coordenacao.
    "excluir_padrinhos": "Apagar padrinhos e desfazer apadrinhamentos ja pagos",
    "subir_cartoes": "Digitalizar e subir os cartoes das criancas",
    "enviar_cartoes": "Marcar cartoes como enviados aos padrinhos",
    "gerenciar_kits": "Montar e registrar a entrega dos kits",
    "gerenciar_compras": "Registrar as saidas (gastos) da edicao",
    "fazer_checkin": "Fazer o check-in das criancas no dia do evento",
    "gerenciar_usuarios": "Criar usuarios e definir vinculos, perfis e instituicoes",
    "gerenciar_cadastros": "Cadastrar instituicoes e os dias do evento da edicao",
}

# Os dois lados do comissariado partem da MESMA lista; a coordenacao da
# captacao ganha, alem dela, o poder de redistribuir a lista entre o time.
COMISSARIADO = (
    "ver_painel",
    "ver_criancas",
    "ver_padrinhos",
    "editar_padrinhos",
    # Sem isto o apadrinhamento que ele capta nunca se confirma sozinho:
    # promessa nao conta em numero nenhum, e o pagamento e o que a
    # transforma em apadrinhamento.
    "registrar_pagamentos_padrinho",
    "enviar_cartoes",
)

# As duas monitorias tem a MESMA lista de permissoes: o que as separa e o
# alcance, nao o que cada uma faz. Escrita uma vez para que as duas nao possam
# divergir numa linha solta.
MONITORIA = (
    "ver_criancas",
    "subir_cartoes",
    "fazer_checkin",
)

# nome do perfil -> (descricao, permissoes)
# Vem da especificacao, com duas mudancas pedidas depois. A primeira: o
# comissario perdeu registrar_pagamentos e fazer_checkin — o caixa da edicao e a
# conferencia do dinheiro ficam com a coordenacao, e o check-in do dia e do
# monitor e da estrutura. A segunda, de 30/09/2026: ele reganhou o registro do
# pagamento DO PADRINHO DELE (registrar_pagamentos_padrinho), porque agora e o
# pagamento que confirma o apadrinhamento — sem isso nada do que ele capta
# apareceria nos numeros ate a coordenacao passar por ali.
# A coordenacao recebe todas as permissoes — tudo o que qualquer equipe faz,
# ela tambem faz — limitadas a sua CIDADE: o unico alcance que ela nao tem e o
# de cidades e edicoes, que fica so com a administracao geral, porque e de la
# que a propria cidade dela nasce.
# Nota: ver_painel vale para a coordenacao e para o comissario, e os dois veem
# coisas diferentes com ela — a coordenacao, a edicao inteira; o comissario, so
# as criancas atribuidas a ele, porque o painel passa pelo mesmo filtro das
# telas. As monitorias e a estrutura seguem sem — o painel delas ainda esta
# por definir. Para abrir e acrescentar "ver_painel" aqui (ou na base, sem
# mexer no codigo), mas antes vale escolher o que cada uma veria ali: o painel
# de hoje e o da captacao, e mostraria a elas numero de padrinho e de dinheiro
# que nenhuma das duas alcanca nas telas.
PERFIS: dict[str, tuple[str, tuple[str, ...]]] = {
    "Coordenacao": (
        "Coordenacao da cidade: todas as permissoes, em todas as edicoes dela",
        tuple(PERMISSOES),
    ),
    # O comissariado se parte em dois desde 01/10/2026, pelo mesmo motivo da
    # monitoria: quem coordena a captacao precisa da edicao inteira, e quem
    # capta no dia a dia responde por uma lista nominal de criancas.
    #
    # A diferenca aqui nao e so de alcance, e por isso as duas listas nao sao
    # iguais: a coordenacao da captacao REDISTRIBUI a lista (atribuir_comissario)
    # e nao fica presa as proprias criancas, e por nao ficar presa ela tambem
    # pode mexer no apadrinhamento feito por qualquer um do time — ver
    # `so_proprias_criancas` em seguranca/contexto.py, que e o que separa os
    # dois no codigo.
    "Comissarios - coordenacao": (
        "Coordena a captacao: todas as instituicoes, e distribui a lista do time",
        (*COMISSARIADO, "atribuir_comissario"),
    ),
    "Comissarios - comissario": (
        "Capta padrinhos das criancas atribuidas a ele e envia os cartoes",
        COMISSARIADO,
    ),
    # A monitoria se parte em dois desde 01/10/2026, e a diferenca entre os
    # dois e SO o alcance — as permissoes sao as mesmas. Quem coordena a
    # monitoria precisa da edicao inteira (abre qualquer pasta de cartao, faz
    # check-in de qualquer instituicao); o monitor responde por uma
    # instituicao, e normalmente em dupla ou trio.
    #
    # Nenhum dos dois ve padrinho nem kit: as colunas sumem sozinhas, porque
    # quem decide isso e a permissao, nao o perfil. Ver `_saida` em
    # routers/criancas.py.
    "Monitoria - coordenacao": (
        "Coordena a monitoria: todas as instituicoes da edicao",
        MONITORIA,
    ),
    "Monitoria - monitores": (
        "Recolhe e digitaliza os cartoes das instituicoes sob sua responsabilidade",
        MONITORIA,
    ),
    "Estrutura": (
        "Compra e monta os kits e faz a entrega",
        (
            "ver_criancas",
            "gerenciar_kits",
            "gerenciar_compras",
            "fazer_checkin",
        ),
    ),
}

# Perfis filtrados pelas instituicoes atribuidas em usuario_instituicao.
# Coordenacao, Estrutura e a coordenacao da monitoria veem a edicao inteira.
PERFIS_FILTRADOS_POR_INSTITUICAO = ("Comissarios - comissario", "Monitoria - monitores")

# Perfis filtrados tambem crianca a crianca: nao basta a instituicao estar
# atribuida, a crianca tem de ter o nome dele em criancas.comissario_id.
# So o comissario. O monitor continua vendo a instituicao inteira porque o
# trabalho dele e da lista toda: recolher e digitalizar os cartoes do dia — e
# porque uma instituicao costuma ter uma dupla ou um trio de monitores, que
# precisam enxergar a mesma lista.
#
# Consequencia de proposito: crianca sem responsavel nao aparece para nenhum
# comissario — ela so existe para a coordenacao, que e quem distribui a lista.
PERFIS_FILTRADOS_POR_CRIANCA = ("Comissarios - comissario",)

# Perfis que respondem por um grupo da comunidade (usuario_edicao.grupo_id).
# So o comissario: os monitores respondem pela instituicao e a coordenacao
# pela edicao inteira, e nenhum deles pertence a um grupo enquanto esta ali.
PERFIS_COM_GRUPO = ("Comissarios - comissario",)

# Os dois unicos lugares em que o sistema olha um perfil pelo NOME, e nao pela
# permissao. Existem porque nenhum dos dois e uma permissao: sao papeis.
#
#   PERFIL_COMISSARIO   quem aparece como responsavel por uma crianca
#                       (criancas.comissario_id) — ao lado da coordenacao e da
#                       administracao geral, que tambem assumem crianca.
#   PERFIL_COORDENACAO  o alcance de cidade inteira: o vinculo da coordenacao e
#                       repetido em todas as edicoes ativas da cidade, e a
#                       edicao nova ja nasce com ela dentro. Quem cuida disso e
#                       app/servicos/coordenacao.py.
#
# O nome vive na base e pode ser mudado la; se for mudado, mude aqui tambem.
PERFIS_COMISSARIADO = ("Comissarios - coordenacao", "Comissarios - comissario")
# O perfil cujo nome aparece primeiro na lista de responsaveis, e o unico que
# e filtrado crianca a crianca.
PERFIL_COMISSARIO = "Comissarios - comissario"
PERFIL_COORDENACAO = "Coordenacao"


def semear(db: Session) -> tuple[int, int]:
    """Cria o que falta. Devolve (permissoes criadas, perfis criados)."""
    permissoes_criadas = 0
    for codigo, descricao in PERMISSOES.items():
        permissao = db.scalar(select(Permissao).where(Permissao.codigo == codigo))
        if permissao is None:
            db.add(Permissao(codigo=codigo, descricao=descricao))
            permissoes_criadas += 1
        else:
            # Mantem a descricao em dia sem tocar nos vinculos existentes.
            permissao.descricao = descricao

    db.flush()

    por_codigo = {p.codigo: p for p in db.scalars(select(Permissao)).all()}

    perfis_criados = 0
    for nome, (descricao, codigos) in PERFIS.items():
        perfil = db.scalar(select(Perfil).where(Perfil.nome == nome))
        if perfil is None:
            perfil = Perfil(nome=nome, descricao=descricao)
            db.add(perfil)
            perfis_criados += 1
        else:
            perfil.descricao = descricao

        # Acrescenta as que faltam; nao remove ajustes feitos na base a mao.
        atuais = {p.codigo for p in perfil.permissoes}
        for codigo in codigos:
            if codigo not in atuais:
                perfil.permissoes.append(por_codigo[codigo])

    db.commit()
    return permissoes_criadas, perfis_criados


def main() -> None:
    db = SessionLocal()
    try:
        permissoes_criadas, perfis_criados = semear(db)
        print(f"permissoes: {permissoes_criadas} criada(s), {len(PERMISSOES)} no total")
        print(f"perfis    : {perfis_criados} criado(s), {len(PERFIS)} no total")
        print()
        for perfil in db.scalars(select(Perfil).order_by(Perfil.nome)).all():
            codigos = sorted(p.codigo for p in perfil.permissoes)
            print(f"{perfil.nome:14} {len(codigos):2} permissoes")
            print(f"               {', '.join(codigos)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
