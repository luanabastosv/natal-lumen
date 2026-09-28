"""Apagar cidade, edicao e instituicao — e tudo o que vem pendurado.

Nenhum dos tres e um registro solto: a cidade segura as edicoes e as
instituicoes, a edicao segura as criancas e os padrinhos, a instituicao segura
as criancas de todos os anos. Apagar qualquer um deles e sempre apagar um
BLOCO, e quem clica precisa ver o tamanho do bloco antes. Por isso cada
exclusao tem um par:

    alcance_da_*  ->  o que seria levado junto (a conta do modal)
    apagar_*      ->  leva.

Os dois leem o mesmo `Alcance`, entao o numero que aparece na tela e
exatamente o do que vai ser apagado — nunca contar seis e apagar sete.

A crianca entra aqui so pela metade de cima: ela tem `alcance_da_crianca`
para a mesma conta aparecer no modal, mas nao tem `apagar_crianca` — o
cascade do banco da conta dela sozinho, e quem apaga e o `db.delete` do
router.

O grosso da remocao e do banco: as chaves estrangeiras ja tem ON DELETE CASCADE
(crianca -> cartoes, kits, apadrinhamentos; edicao -> criancas, padrinhos,
dias, compras, recebimentos, acessos). Aqui ficam so as pontas que o cascade
nao resolve: a ordem das tabelas cujo vinculo e RESTRICT —
criancas.instituicao_id e uma — e os arquivos no disco, que nenhuma chave
estrangeira alcanca.
"""

from dataclasses import dataclass

from sqlalchemy import Select, delete, false, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Apadrinhamento,
    Cartao,
    Cidade,
    Compra,
    Crianca,
    DiaEvento,
    Edicao,
    Grupo,
    Instituicao,
    Kit,
    Padrinho,
    Pagamento,
    Recebimento,
    Usuario,
    UsuarioEdicao,
    UsuarioInstituicao,
)
from app.schemas.cadastros import DependenciasOut, ItemDependencia
from app.servicos import arquivos

# Executar o DELETE sem sincronizar a sessao: quem chama commita e descarta a
# sessao logo em seguida, entao manter os objetos em memoria de acordo com o
# banco so renderia SELECTs a mais para nada.
SEM_SINCRONIZAR = {"synchronize_session": False}


@dataclass(frozen=True)
class Alcance:
    """Os ids que a exclusao alcanca — como CONSULTAS, nao como listas.

    Consulta, e nao lista, porque uma cidade de verdade tem milhares de
    criancas: contar e apagar por subconsulta evita trazer todos esses ids para
    o Python so para devolve-los ao banco dentro de um IN gigante.
    """

    edicoes: Select
    instituicoes: Select
    criancas: Select
    padrinhos: Select
    # So a cidade alcanca grupos: eles sao dela e atravessam os anos, como a
    # instituicao — apagar a edicao de 2026 nao apaga o grupo Elyon.
    grupos: Select


def _nenhum(coluna) -> Select:
    """Consulta que nao casa com nada — a parte do alcance que nao se aplica."""
    return select(coluna).where(false())


def alcance_da_cidade(cidade_id: int) -> Alcance:
    edicoes = select(Edicao.id).where(Edicao.cidade_id == cidade_id)
    instituicoes = select(Instituicao.id).where(Instituicao.cidade_id == cidade_id)
    return Alcance(
        edicoes=edicoes,
        instituicoes=instituicoes,
        # A crianca cai por dois caminhos: ou a edicao dela e desta cidade, ou
        # a instituicao e. Quase sempre sao a mesma cidade, mas quem apaga nao
        # pode depender disso — uma crianca sobrando apontando para instituicao
        # apagada travaria a exclusao inteira no meio.
        criancas=select(Crianca.id).where(
            or_(
                Crianca.edicao_id.in_(edicoes),
                Crianca.instituicao_id.in_(instituicoes),
            )
        ),
        padrinhos=select(Padrinho.id).where(Padrinho.edicao_id.in_(edicoes)),
        grupos=select(Grupo.id).where(Grupo.cidade_id == cidade_id),
    )


def alcance_da_edicao(edicao_id: int) -> Alcance:
    """A edicao leva o ano inteiro; as instituicoes ficam.

    Instituicao pertence a CIDADE e persiste entre anos: apagar a edicao de
    2026 nao pode apagar a escola que tambem atendeu em 2025.
    """
    edicoes = select(Edicao.id).where(Edicao.id == edicao_id)
    return Alcance(
        edicoes=edicoes,
        instituicoes=_nenhum(Instituicao.id),
        criancas=select(Crianca.id).where(Crianca.edicao_id == edicao_id),
        padrinhos=select(Padrinho.id).where(Padrinho.edicao_id == edicao_id),
        grupos=_nenhum(Grupo.id),
    )


def alcance_da_instituicao(instituicao_id: int) -> Alcance:
    """A instituicao leva as criancas dela de TODAS as edicoes.

    O cadastro e um so e atravessa os anos: apagar a escola apaga tambem a
    lista que ela mandou em 2025. Os padrinhos ficam — eles sao da edicao, nao
    da instituicao; o que cai sao os apadrinhamentos destas criancas.
    """
    return Alcance(
        edicoes=_nenhum(Edicao.id),
        instituicoes=select(Instituicao.id).where(Instituicao.id == instituicao_id),
        criancas=select(Crianca.id).where(Crianca.instituicao_id == instituicao_id),
        padrinhos=_nenhum(Padrinho.id),
        grupos=_nenhum(Grupo.id),
    )


def alcance_da_crianca(crianca_id: int) -> Alcance:
    """A crianca leva o que e so dela: cartoes, kit e apadrinhamentos.

    Nada sobe: a instituicao e a edicao continuam de pe, e o padrinho tambem —
    o que cai do lado dele e o apadrinhamento desta crianca, nao o cadastro.
    """
    return Alcance(
        edicoes=_nenhum(Edicao.id),
        instituicoes=_nenhum(Instituicao.id),
        criancas=select(Crianca.id).where(Crianca.id == crianca_id),
        padrinhos=_nenhum(Padrinho.id),
        grupos=_nenhum(Grupo.id),
    )


def _quantos(db: Session, modelo, condicao) -> int:
    return db.scalar(select(func.count()).select_from(modelo).where(condicao)) or 0


def contar(db: Session, alcance: Alcance) -> list[ItemDependencia]:
    """Quantos registros de cada tipo vao junto. Os zerados ficam de fora.

    A chave vai sem acento e no plural cru ("criancas", "cartoes"): quem
    escreve o rotulo lido na tela e o frontend, que e o lado acentuado do
    sistema. Aqui so sai a conta.
    """
    acessos = select(UsuarioEdicao.id).where(UsuarioEdicao.edicao_id.in_(alcance.edicoes))

    contagens = [
        ("edicoes", _quantos(db, Edicao, Edicao.id.in_(alcance.edicoes))),
        (
            "instituicoes",
            _quantos(db, Instituicao, Instituicao.id.in_(alcance.instituicoes)),
        ),
        ("dias", _quantos(db, DiaEvento, DiaEvento.edicao_id.in_(alcance.edicoes))),
        ("criancas", _quantos(db, Crianca, Crianca.id.in_(alcance.criancas))),
        ("cartoes", _quantos(db, Cartao, Cartao.crianca_id.in_(alcance.criancas))),
        ("kits", _quantos(db, Kit, Kit.crianca_id.in_(alcance.criancas))),
        ("padrinhos", _quantos(db, Padrinho, Padrinho.id.in_(alcance.padrinhos))),
        # Conta pelos DOIS lados: apadrinhamento entre cidades e permitido,
        # entao apagar a crianca daqui derruba o apadrinhamento de um padrinho
        # de outra edicao, e apagar o padrinho daqui derruba o de uma crianca
        # de outra. Contar so por um lado esconderia metade do estrago.
        (
            "apadrinhamentos",
            _quantos(
                db,
                Apadrinhamento,
                or_(
                    Apadrinhamento.crianca_id.in_(alcance.criancas),
                    Apadrinhamento.padrinho_id.in_(alcance.padrinhos),
                ),
            ),
        ),
        (
            "pagamentos",
            _quantos(db, Pagamento, Pagamento.padrinho_id.in_(alcance.padrinhos)),
        ),
        ("compras", _quantos(db, Compra, Compra.edicao_id.in_(alcance.edicoes))),
        (
            "recebimentos",
            _quantos(db, Recebimento, Recebimento.edicao_id.in_(alcance.edicoes)),
        ),
        ("grupos", _quantos(db, Grupo, Grupo.id.in_(alcance.grupos))),
        ("acessos", _quantos(db, UsuarioEdicao, UsuarioEdicao.id.in_(acessos))),
        # A atribuicao cai por dois caminhos, um por chave estrangeira: some
        # com a instituicao e some tambem com o acesso do usuario a edicao.
        (
            "atribuicoes",
            _quantos(
                db,
                UsuarioInstituicao,
                or_(
                    UsuarioInstituicao.instituicao_id.in_(alcance.instituicoes),
                    UsuarioInstituicao.usuario_edicao_id.in_(acessos),
                ),
            ),
        ),
    ]

    return [
        ItemDependencia(chave=chave, quantidade=quantidade)
        for chave, quantidade in contagens
        if quantidade
    ]


def resumir(db: Session, registro_id: int, nome: str, alcance: Alcance) -> DependenciasOut:
    itens = contar(db, alcance)
    return DependenciasOut(
        id=registro_id,
        nome=nome,
        total=sum(item.quantidade for item in itens),
        itens=itens,
    )


def resumir_usuario(db: Session, usuario: Usuario) -> DependenciasOut:
    """O que some junto com a conta — e so o que some de verdade.

    A conta do usuario nao usa `Alcance`: ela nao segura um bloco de dados como
    a cidade ou a edicao. O que cai com ela sao os proprios acessos (vinculo com
    cada edicao) e as atribuicoes de instituicao, ambos por ON DELETE CASCADE.

    O que o trabalho dela deixou fica: crianca, padrinho, pagamento e compra
    apontam para o usuario com ON DELETE SET NULL, entao sobrevivem sem dono.
    Nada disso entra na conta — quem le "leva junto" tem de poder confiar que
    aquilo vai ser apagado mesmo. As criancas que ficam sem responsavel sao
    assunto do aviso da tela, nao desta lista.
    """
    acessos = select(UsuarioEdicao.id).where(UsuarioEdicao.usuario_id == usuario.id)

    contagens = [
        # Os acessos vao todos, suspensos inclusive — e a tela mostra os
        # suspensos, entao o numero bate com o que a pessoa esta vendo.
        ("acessos", _quantos(db, UsuarioEdicao, UsuarioEdicao.usuario_id == usuario.id)),
        (
            # Aqui so as que valem. Tirar uma instituicao de alguem nao apaga a
            # linha, desliga: quem foi comissario da Escola A e deixou de ser
            # tem uma linha inativa que nenhuma tela mostra. Conta-las diria
            # "3 atribuicoes" a quem enxerga uma — e o numero existe justamente
            # para ser conferido contra o que esta na tela.
            "atribuicoes",
            _quantos(
                db,
                UsuarioInstituicao,
                UsuarioInstituicao.usuario_edicao_id.in_(acessos)
                & UsuarioInstituicao.ativo.is_(True),
            ),
        ),
    ]

    itens = [
        ItemDependencia(chave=chave, quantidade=quantidade)
        for chave, quantidade in contagens
        if quantidade
    ]

    return DependenciasOut(
        id=usuario.id,
        nome=usuario.nome,
        total=sum(item.quantidade for item in itens),
        itens=itens,
    )


def criancas_sob_responsabilidade(db: Session, usuario_id: int) -> int:
    """Quantas criancas ficam sem responsavel se esta conta sair.

    Separado da conta de exclusao de proposito: estas criancas NAO sao apagadas,
    so perdem o nome de quem respondia por elas. A tela avisa, mas noutro tom.
    """
    return _quantos(db, Crianca, Crianca.comissario_id == usuario_id)


def _arquivos_do_alcance(db: Session, alcance: Alcance) -> list[str]:
    """Caminhos dos cartoes e dos comprovantes que vao ficar sem dono.

    Lido ANTES dos DELETEs, porque depois nao ha mais linha apontando para
    eles. Nenhum ON DELETE alcanca o disco: sem isto, apagar uma edicao
    deixaria no servidor as fotos dos cartoes escritos pelas criancas — dado
    sensivel de menor de idade, sem uma linha sequer no banco para encontra-lo
    depois.
    """
    caminhos = list(
        db.scalars(
            select(Cartao.arquivo).where(Cartao.crianca_id.in_(alcance.criancas))
        ).all()
    )
    caminhos += list(
        db.scalars(
            select(Pagamento.comprovante_arquivo).where(
                Pagamento.padrinho_id.in_(alcance.padrinhos),
                Pagamento.comprovante_arquivo.is_not(None),
            )
        ).all()
    )
    # O recibo da doacao mora na mesma pasta e cai pelo mesmo motivo: a linha
    # dele sai no cascade da edicao, e sem isto o arquivo ficaria no servidor
    # sem nada apontando para ele.
    caminhos += list(
        db.scalars(
            select(Recebimento.comprovante_arquivo).where(
                Recebimento.edicao_id.in_(alcance.edicoes),
                Recebimento.comprovante_arquivo.is_not(None),
            )
        ).all()
    )
    return caminhos


def remover_arquivos(caminhos: list[str]) -> int:
    """Tira do disco, ignorando o que ja nao esta la.

    Roda DEPOIS do commit, de proposito: arquivo apagado nao volta, entao so
    sai do disco o que ja saiu do banco para valer. E nunca levanta erro — a
    exclusao ja aconteceu, e falhar aqui so deixaria a tela dizendo que nao
    deu certo quando os dados ja foram.
    """
    apagados = 0
    for relativo in caminhos:
        try:
            caminho = arquivos.dentro_da_pasta(relativo)
            caminho.unlink()
            apagados += 1
        except (OSError, ValueError):
            continue
    return apagados


def apagar_cidade(db: Session, cidade_id: int) -> list[str]:
    """Apaga a cidade e devolve os arquivos que ficaram sem dono."""
    alcance = alcance_da_cidade(cidade_id)
    orfaos = _arquivos_do_alcance(db, alcance)

    # As criancas saem primeiro, e a ordem tem motivo: criancas.instituicao_id
    # NAO tem cascade (apagar instituicao com crianca e erro, de proposito).
    # Aqui a instituicao vai junto, entao a crianca precisa sair antes dela.
    db.execute(
        delete(Crianca).where(Crianca.instituicao_id.in_(alcance.instituicoes)),
        execution_options=SEM_SINCRONIZAR,
    )
    # A edicao leva no cascade dias, criancas, padrinhos, compras e acessos.
    db.execute(
        delete(Edicao).where(Edicao.cidade_id == cidade_id),
        execution_options=SEM_SINCRONIZAR,
    )
    db.execute(
        delete(Instituicao).where(Instituicao.cidade_id == cidade_id),
        execution_options=SEM_SINCRONIZAR,
    )
    # Depois das edicoes: os vinculos que apontavam para estes grupos ja cairam
    # no cascade delas.
    db.execute(
        delete(Grupo).where(Grupo.cidade_id == cidade_id),
        execution_options=SEM_SINCRONIZAR,
    )
    db.execute(
        delete(Cidade).where(Cidade.id == cidade_id),
        execution_options=SEM_SINCRONIZAR,
    )
    return orfaos


def apagar_edicao(db: Session, edicao_id: int) -> list[str]:
    """Apaga a edicao e devolve os arquivos que ficaram sem dono.

    Uma linha so: tudo o que pendura na edicao ja tem ON DELETE CASCADE.
    """
    orfaos = _arquivos_do_alcance(db, alcance_da_edicao(edicao_id))

    db.execute(
        delete(Edicao).where(Edicao.id == edicao_id),
        execution_options=SEM_SINCRONIZAR,
    )
    return orfaos


def apagar_instituicao(db: Session, instituicao_id: int) -> list[str]:
    """Apaga a instituicao e devolve os arquivos que ficaram sem dono."""
    orfaos = _arquivos_do_alcance(db, alcance_da_instituicao(instituicao_id))

    # Antes da instituicao, pelo mesmo motivo de apagar_cidade: o vinculo da
    # crianca com a instituicao e RESTRICT.
    db.execute(
        delete(Crianca).where(Crianca.instituicao_id == instituicao_id),
        execution_options=SEM_SINCRONIZAR,
    )
    db.execute(
        delete(Instituicao).where(Instituicao.id == instituicao_id),
        execution_options=SEM_SINCRONIZAR,
    )
    return orfaos
