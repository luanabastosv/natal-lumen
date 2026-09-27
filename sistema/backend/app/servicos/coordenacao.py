"""A coordenacao e da CIDADE, nao de um ano dela.

O sistema isola dados por edicao (cidade + ano) e todo vinculo mora em
usuario_edicao — inclusive o da coordenacao, senao nenhum filtro do sistema
funcionaria. Mas o alcance dela e outro: quem coordena uma cidade coordena tudo
o que esta aberto nela, e nao so o ano em que alguem se lembrou de criar o
vinculo. Este modulo e o que mantem essa promessa:

  - nomear a coordenacao numa edicao nomeia em todas as edicoes ATIVAS da cidade;
  - suspender ou tirar faz o mesmo caminho de volta;
  - edicao nova ja nasce com a coordenacao da cidade dentro.

Edicao inativa fica de fora de proposito: e ano encerrado, e a equipe daquele
ano e historico — nomear a coordenacao de 2026 nao reescreve quem coordenou
2025. A excecao e a edicao que ACABA de nascer: ela olha os vinculos ativos de
qualquer edicao da cidade, ativa ou nao, para a virada de ano nao depender de a
cidade ter deixado o ano anterior aberto.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Edicao, Perfil, UsuarioEdicao
from app.seeds.perfis_permissoes import PERFIL_COORDENACAO


def perfil(db: Session) -> Perfil | None:
    """O perfil de coordenacao. Nulo se a base ainda nao foi semeada."""
    return db.scalar(select(Perfil).where(Perfil.nome == PERFIL_COORDENACAO))


def eh_coordenacao(db: Session, perfil_id: int) -> bool:
    p = db.get(Perfil, perfil_id)
    return p is not None and p.nome == PERFIL_COORDENACAO


def _outras_edicoes_ativas(db: Session, cidade_id: int, exceto: int) -> list[Edicao]:
    return list(
        db.scalars(
            select(Edicao).where(
                Edicao.cidade_id == cidade_id,
                Edicao.id != exceto,
                Edicao.ativa.is_(True),
            )
        ).all()
    )


def _limpar_sobras(vinculo: UsuarioEdicao) -> None:
    """Coordenacao nao responde por instituicao nem por grupo.

    Quem chega a coordenacao vindo de comissario ou monitor traz as duas coisas
    penduradas no vinculo. Deixa-las ali seria guardar um recorte que nao vale
    mais — e que voltaria a valer sozinho no dia em que a pessoa mudasse de
    perfil de novo.
    """
    vinculo.grupo_id = None
    for ligacao in vinculo.instituicoes:
        ligacao.ativo = False


def espelhar(db: Session, vinculo: UsuarioEdicao) -> list[UsuarioEdicao]:
    """Repete um vinculo de coordenacao nas outras edicoes ativas da cidade.

    Chamar depois de criar ou editar um vinculo cujo perfil E o de coordenacao.
    Leva junto o `ativo`: suspender a coordenacao numa edicao suspende na
    cidade, que e o que "coordenar a cidade" quer dizer.

    Devolve os vinculos que mudaram — o chamador ainda precisa deles para
    soltar crianca e para o log.
    """
    edicao = db.get(Edicao, vinculo.edicao_id)
    if edicao is None:
        return []

    mexidos: list[UsuarioEdicao] = []
    for outra in _outras_edicoes_ativas(db, edicao.cidade_id, exceto=edicao.id):
        existente = db.scalar(
            select(UsuarioEdicao).where(
                UsuarioEdicao.usuario_id == vinculo.usuario_id,
                UsuarioEdicao.edicao_id == outra.id,
            )
        )

        if existente is None:
            novo = UsuarioEdicao(
                usuario_id=vinculo.usuario_id,
                edicao_id=outra.id,
                perfil_id=vinculo.perfil_id,
                ativo=vinculo.ativo,
            )
            db.add(novo)
            mexidos.append(novo)
            continue

        if existente.perfil_id == vinculo.perfil_id and existente.ativo == vinculo.ativo:
            continue

        # Promove o que ja existia. A pessoa podia ser comissaria em 2026 e
        # acabou de virar coordenacao da cidade: o perfil de la sobe junto, em
        # vez de ficar um acesso menor sobrando numa edicao aberta.
        existente.perfil_id = vinculo.perfil_id
        existente.ativo = vinculo.ativo
        _limpar_sobras(existente)
        mexidos.append(existente)

    db.flush()
    return mexidos


def encerrar(db: Session, vinculo: UsuarioEdicao) -> list[UsuarioEdicao]:
    """Desfaz o alcance de cidade de quem deixou de ser coordenacao.

    Chamar depois de um vinculo DEIXAR de ser coordenacao — porque mudou de
    perfil ou porque foi desativado. Os espelhos nas outras edicoes ativas sao
    desativados, e nao rebaixados: eles so existiam por causa da coordenacao da
    cidade. Se a pessoa continua na equipe de uma daquelas edicoes, quem
    gerencia diz em qual, no perfil que for — e isso e uma decisao de gente, nao
    uma conta que o sistema possa fazer sozinho.

    Vinculo que ja nao era coordenacao naquela edicao nao e tocado: ele nunca
    veio daqui.
    """
    edicao = db.get(Edicao, vinculo.edicao_id)
    coordenacao = perfil(db)
    if edicao is None or coordenacao is None:
        return []

    mexidos: list[UsuarioEdicao] = []
    for outra in _outras_edicoes_ativas(db, edicao.cidade_id, exceto=edicao.id):
        espelho = db.scalar(
            select(UsuarioEdicao).where(
                UsuarioEdicao.usuario_id == vinculo.usuario_id,
                UsuarioEdicao.edicao_id == outra.id,
                UsuarioEdicao.perfil_id == coordenacao.id,
                UsuarioEdicao.ativo.is_(True),
            )
        )
        if espelho is None:
            continue
        espelho.ativo = False
        mexidos.append(espelho)

    db.flush()
    return mexidos


def povoar_edicao_nova(db: Session, edicao: Edicao) -> list[UsuarioEdicao]:
    """A edicao nova ja nasce com a coordenacao da cidade dentro.

    Sem isto, abrir 2027 deixaria a cidade sem coordenacao ate alguem da
    administracao geral se lembrar de recriar os vinculos um a um — e o sistema
    abriria o ano com ninguem podendo cadastrar crianca nenhuma.

    Olha os vinculos ativos de QUALQUER edicao da cidade, ativa ou nao: a
    virada de ano normalmente acontece com o ano anterior ja encerrado.
    """
    coordenacao = perfil(db)
    if coordenacao is None:
        return []

    usuarios = db.scalars(
        select(UsuarioEdicao.usuario_id)
        .join(Edicao, Edicao.id == UsuarioEdicao.edicao_id)
        .where(
            Edicao.cidade_id == edicao.cidade_id,
            Edicao.id != edicao.id,
            UsuarioEdicao.perfil_id == coordenacao.id,
            UsuarioEdicao.ativo.is_(True),
        )
        .distinct()
    ).all()

    criados: list[UsuarioEdicao] = []
    for usuario_id in usuarios:
        ja_tem = db.scalar(
            select(UsuarioEdicao).where(
                UsuarioEdicao.usuario_id == usuario_id,
                UsuarioEdicao.edicao_id == edicao.id,
            )
        )
        if ja_tem is not None:
            continue
        novo = UsuarioEdicao(
            usuario_id=usuario_id, edicao_id=edicao.id, perfil_id=coordenacao.id
        )
        db.add(novo)
        criados.append(novo)

    db.flush()
    return criados
