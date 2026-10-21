"""Painel da edicao: o apadrinhamento de cesta e de festa, e quem falta.

Todos os numeros passam pelo mesmo filtro das telas: quem so alcanca algumas
instituicoes ve os numeros dessas instituicoes, e nao da edicao inteira. Com o
comissario o filtro vai mais fundo — crianca a crianca — e o painel entao deixa
de ser o da edicao para ser o dele: as criancas que estao na mao dele, e quanto
ainda falta apadrinhar delas.

A estrutura abre um painel mais estreito (ver_painel_logistica): as mesmas
contas, mas so as quebras por dia, por idade e por instituicao — o que orienta
a compra e a montagem dos kits. O resto e a cobranca da captacao, e sai vazio.
"""

import unicodedata
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Apadrinhamento,
    Crianca,
    DiaEvento,
    Edicao,
    Grupo,
    Instituicao,
    InstituicaoDia,
    LogAtividade,
    Perfil,
    Usuario,
    UsuarioEdicao,
)
from app.models.tipos import Sexo, TipoApadrinhamento
from app.schemas.painel import (
    FaixaIdade,
    ItemAtividade,
    LinhaComissario,
    LinhaDoTempo,
    LinhaDia,
    LinhaInstituicao,
    PessoaAtividade,
    Relatorio,
    ResumoEdicao,
)
from app.seeds.perfis_permissoes import PERFIL_COMISSARIO
from app.seguranca.contexto import ContextoAcesso
from app.servicos import atividade
from app.servicos.apadrinhamento import CONFIRMADO, PROMETIDO
from app.seguranca.dependencias import exige_qualquer

router = APIRouter(prefix="/painel", tags=["painel"])

BD = Annotated[Session, Depends(get_db)]
Painel = Annotated[
    ContextoAcesso, Depends(exige_qualquer("ver_painel", "ver_painel_logistica"))
]

CESTA = TipoApadrinhamento.CESTA.value
FESTA = TipoApadrinhamento.FESTA.value

MASCULINO = Sexo.MASCULINO.value
FEMININO = Sexo.FEMININO.value

SEM_COMISSARIO = "Sem comissário"


def _tipos_por_crianca(criancas_visiveis):
    """Cesta e festa de cada crianca, uma linha por crianca.

    Sai de um agrupamento, e nao de um join direto, porque quem pergunta quer
    saber quantas criancas estao COMPLETAS — e isso e uma conta sobre a
    crianca, nao sobre o apadrinhamento. A unicidade de (crianca, tipo)
    garante que cada coluna aqui valha 0 ou 1.
    """
    return (
        select(
            Apadrinhamento.crianca_id.label("crianca_id"),
            func.count(case((Apadrinhamento.tipo == CESTA, 1))).label("cesta"),
            func.count(case((Apadrinhamento.tipo == FESTA, 1))).label("festa"),
        )
        # So o que foi pago conta: promessa nao e apadrinhamento (ver
        # servicos/apadrinhamento.py). A promessa continua na base, segurando a
        # crianca, mas fora de toda conta desta tela.
        .where(Apadrinhamento.crianca_id.in_(criancas_visiveis), CONFIRMADO)
        .group_by(Apadrinhamento.crianca_id)
        .subquery()
    )


@router.get("/{edicao_id}", response_model=Relatorio)
def relatorio(edicao_id: int, db: BD, ctx: Painel):
    edicao = db.scalar(
        select(Edicao).where(Edicao.id == edicao_id).options(joinedload(Edicao.cidade))
    )
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    # Qual painel abre e decidido nesta edicao: quem tem os dois fica com o
    # inteiro, e quem nao tem nenhum dos dois aqui nao ve a edicao.
    if ctx.alcanca_edicao(edicao_id, "ver_painel"):
        permissao, so_logistica = "ver_painel", False
    elif ctx.alcanca_edicao(edicao_id, "ver_painel_logistica"):
        permissao, so_logistica = "ver_painel_logistica", True
    else:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    # Mesmo filtro das telas: quem so alcanca algumas instituicoes ve os
    # numeros dessas instituicoes.
    # Sem as criancas que o comissario alcanca so pela festa: os numeros dele
    # sao os da lista de cesta, e a festa dele e contada a parte, abaixo.
    alcance = ctx.filtro_criancas(permissao, com_festa=False) & (Crianca.edicao_id == edicao_id)
    criancas_visiveis = select(Crianca.id).where(alcance)

    criancas = db.scalar(select(func.count()).select_from(Crianca).where(alcance)) or 0
    instituicoes = db.scalar(
        select(func.count(func.distinct(Crianca.instituicao_id))).where(alcance)
    ) or 0

    por_tipo = dict(
        db.execute(
            select(Apadrinhamento.tipo, func.count())
            .where(Apadrinhamento.crianca_id.in_(criancas_visiveis), CONFIRMADO)
            .group_by(Apadrinhamento.tipo)
        ).all()
    )

    # As promessas a cobrar. Sem este numero a queda nas contas acima nao teria
    # explicacao na tela: a crianca sai de "apadrinhada" e nao aparece em lugar
    # nenhum, e quem olha o painel conclui que o padrinho sumiu. Aqui ele esta,
    # esperando o pagamento ser registrado.
    prometidos = db.scalar(
        select(func.count())
        .select_from(Apadrinhamento)
        .where(Apadrinhamento.crianca_id.in_(criancas_visiveis), PROMETIDO)
    ) or 0

    # Crianca completa: tem cesta E festa. Conta uma vez por crianca, entao sai
    # de um agrupamento — somar os dois tipos contaria a completa duas vezes.
    completas = db.scalar(
        select(func.count()).select_from(
            select(Apadrinhamento.crianca_id)
            .where(Apadrinhamento.crianca_id.in_(criancas_visiveis), CONFIRMADO)
            .group_by(Apadrinhamento.crianca_id)
            .having(func.count(func.distinct(Apadrinhamento.tipo)) == 2)
            .subquery()
        )
    ) or 0

    # A festa do comissario nao e a das criancas da lista dele: e a que a
    # coordenacao passou para ele, de qualquer instituicao. Para quem ve a
    # edicao inteira, sao as mesmas criancas de sempre.
    so_minhas_criancas = ctx.so_proprias_criancas(edicao_id)
    festa_criancas, festa_feitos = criancas, por_tipo.get(FESTA, 0)
    if so_minhas_criancas and edicao.festa_liberada_em is None:
        festa_criancas = festa_feitos = 0
    elif so_minhas_criancas:
        da_festa = (Crianca.edicao_id == edicao_id) & (
            Crianca.comissario_festa_id == ctx.usuario.id
        )
        festa_criancas = db.scalar(
            select(func.count()).select_from(Crianca).where(da_festa)
        ) or 0
        festa_feitos = db.scalar(
            select(func.count())
            .select_from(Apadrinhamento)
            .where(
                Apadrinhamento.crianca_id.in_(select(Crianca.id).where(da_festa)),
                Apadrinhamento.tipo == FESTA,
                CONFIRMADO,
            )
        ) or 0

    resumo = ResumoEdicao(
        edicao_id=edicao.id,
        edicao=edicao.nome,
        cidade=edicao.cidade.nome,
        ano=edicao.ano,
        criancas=criancas,
        instituicoes=instituicoes,
        cesta_feitos=por_tipo.get(CESTA, 0),
        festa_feitos=festa_feitos,
        festa_criancas=festa_criancas,
        completas=completas,
        # As promessas sao cobranca da captacao, nao assunto de quem monta kit.
        prometidos=0 if so_logistica else prometidos,
        festa_liberada=edicao.festa_liberada_em is not None,
    )

    # O comissario ja esta vendo so as criancas dele — a quebra por comissario
    # nao tem o que quebrar, e traria os colegas todos zerados. Ela e da
    # coordenacao, que e quem distribui a lista e cobra o time.
    por_instituicao = _por_instituicao(db, alcance, criancas_visiveis, edicao_id)
    if so_minhas_criancas and edicao.festa_liberada_em is not None:
        por_instituicao = _com_a_festa_do_comissario(
            db, por_instituicao, edicao_id, ctx.usuario.id
        )

    return Relatorio(
        resumo=resumo,
        so_minhas_criancas=so_minhas_criancas,
        so_logistica=so_logistica,
        por_instituicao=por_instituicao,
        por_comissario=(
            []
            if so_minhas_criancas or so_logistica
            else _por_comissario(
                db, alcance, criancas_visiveis, edicao_id,
                festa_ligada=edicao.festa_liberada_em is not None,
            )
        ),
        por_idade=_por_idade(db, alcance),
        por_dia=_por_dia(por_instituicao),
    )


def _por_instituicao(
    db: Session, alcance, criancas_visiveis, edicao_id: int
) -> list[LinhaInstituicao]:
    """Quantas criancas a instituicao tem, quanto ja esta apadrinhado, e a
    logistica do dia dela.

    So aparece instituicao que tem crianca nesta edicao. A que foi marcada para
    um dia mas ainda nao mandou a lista fica de fora — ela nao tem numero
    nenhum para mostrar, e a pergunta "quem ainda nao mandou a lista" e da tela
    de instituicoes, que lista o cadastro inteiro.
    """
    tipos = _tipos_por_crianca(criancas_visiveis)

    linhas = db.execute(
        select(
            Crianca.instituicao_id,
            Instituicao.nome,
            Instituicao.sigla,
            func.count(Crianca.id),
            func.coalesce(func.sum(tipos.c.cesta), 0),
            func.coalesce(func.sum(tipos.c.festa), 0),
            func.count(case(((tipos.c.cesta > 0) & (tipos.c.festa > 0), Crianca.id))),
            InstituicaoDia.dia_evento_id,
            DiaEvento.data,
            DiaEvento.descricao,
            func.coalesce(InstituicaoDia.onibus, 0),
        )
        .join(Instituicao, Instituicao.id == Crianca.instituicao_id)
        .outerjoin(tipos, tipos.c.crianca_id == Crianca.id)
        # Nenhum destes tres multiplica a linha: instituicao_dia e unica por
        # edicao + instituicao, o dia e um so, e `tipos` ja vem agrupado por
        # crianca. Por isso as somas acima contam cada crianca uma vez.
        .outerjoin(
            InstituicaoDia,
            (InstituicaoDia.instituicao_id == Crianca.instituicao_id)
            & (InstituicaoDia.edicao_id == edicao_id),
        )
        .outerjoin(DiaEvento, DiaEvento.id == InstituicaoDia.dia_evento_id)
        .where(alcance)
        .group_by(
            Crianca.instituicao_id,
            Instituicao.nome,
            Instituicao.sigla,
            InstituicaoDia.dia_evento_id,
            DiaEvento.data,
            DiaEvento.descricao,
            InstituicaoDia.onibus,
        )
        .order_by(Instituicao.nome)
    ).all()

    return [
        LinhaInstituicao(
            instituicao_id=i,
            instituicao=nome,
            sigla=sigla,
            criancas=c,
            cesta=cesta,
            festa=festa,
            completas=completas,
            faltam=c - completas,
            dia_evento_id=dia_id,
            dia_evento=data,
            dia_evento_descricao=descricao,
            onibus=onibus,
        )
        for i, nome, sigla, c, cesta, festa, completas, dia_id, data, descricao, onibus
        in linhas
    ]


def _com_a_festa_do_comissario(
    db: Session, linhas: list[LinhaInstituicao], edicao_id: int, usuario_id: int
) -> list[LinhaInstituicao]:
    """A festa do comissario em cada instituicao: as criancas que a
    coordenacao passou para ele, e quantas ja tem padrinho de festa.

    A lista de cesta dele e uma, a de festa e outra — numa instituicao ele pode
    ter so a festa. A linha dessa instituicao entra aqui, com zero de cesta.
    """
    festa_ok = (
        select(Apadrinhamento.crianca_id)
        .where(Apadrinhamento.tipo == FESTA, CONFIRMADO)
    )
    contas = {
        i: (total, feitas)
        for i, total, feitas in db.execute(
            select(
                Crianca.instituicao_id,
                func.count(Crianca.id),
                func.count(case((Crianca.id.in_(festa_ok), Crianca.id))),
            )
            .where(Crianca.edicao_id == edicao_id, Crianca.comissario_festa_id == usuario_id)
            .group_by(Crianca.instituicao_id)
        ).all()
    }

    saida = []
    for linha in linhas:
        total, feitas = contas.pop(linha.instituicao_id, (0, 0))
        saida.append(linha.model_copy(update={"festa_criancas": total, "festa": feitas}))

    # Instituicoes em que ele so tem festa.
    if contas:
        for inst in db.scalars(select(Instituicao).where(Instituicao.id.in_(contas))).all():
            total, feitas = contas[inst.id]
            saida.append(LinhaInstituicao(
                instituicao_id=inst.id, instituicao=inst.nome, sigla=inst.sigla,
                criancas=0, cesta=0, festa=feitas, festa_criancas=total,
                completas=0, faltam=0, dia_evento_id=None, dia_evento=None,
                dia_evento_descricao=None, onibus=0,
            ))
        saida.sort(key=lambda l: l.instituicao)
    # O que falta, para ele, e o que falta das duas listas.
    return [
        l.model_copy(update={"faltam": (l.criancas - l.cesta) + (l.festa_criancas - l.festa)})
        for l in saida
    ]


def _por_idade(db: Session, alcance) -> list[FaixaIdade]:
    """A distribuicao de idade, separada por sexo.

    A faixa sai continua — do menor ao maior, sem pular idade sem crianca. Um
    zero no meio da lista e informacao ("nao veio nenhuma de 7"); um buraco
    entre 6 e 8 se le como se a idade nem existisse.
    """
    contagem: dict[int, dict[str, int]] = {}
    for idade, sexo, quantas in db.execute(
        select(Crianca.idade, Crianca.sexo, func.count())
        .where(alcance)
        .group_by(Crianca.idade, Crianca.sexo)
    ).all():
        faixa = contagem.setdefault(idade, {MASCULINO: 0, FEMININO: 0})
        if sexo in faixa:
            faixa[sexo] = quantas

    if not contagem:
        return []

    vazia = {MASCULINO: 0, FEMININO: 0}
    return [
        FaixaIdade(
            idade=idade,
            masculino=contagem.get(idade, vazia)[MASCULINO],
            feminino=contagem.get(idade, vazia)[FEMININO],
        )
        for idade in range(min(contagem), max(contagem) + 1)
    ]


def _por_dia(instituicoes: list[LinhaInstituicao]) -> list[LinhaDia]:
    """O total de cada dia do evento, somado das instituicoes que vao nele.

    Sai das linhas que ja foram calculadas, e nao de uma consulta propria: sao
    os mesmos numeros somados de outro jeito, e duas consultas para a mesma
    verdade acabariam discordando uma hora.
    """
    dias: dict[int | None, LinhaDia] = {}

    for linha in instituicoes:
        dia = dias.get(linha.dia_evento_id)
        if dia is None:
            dia = dias[linha.dia_evento_id] = LinhaDia(
                dia_evento_id=linha.dia_evento_id,
                data=linha.dia_evento,
                descricao=linha.dia_evento_descricao,
                instituicoes=0,
                criancas=0,
                onibus=0,
                completas=0,
                faltam=0,
            )
        dia.instituicoes += 1
        dia.criancas += linha.criancas
        dia.onibus += linha.onibus
        dia.completas += linha.completas
        dia.faltam += linha.faltam

    # So ha quebra se houver mais de um dia. Com um dia so — ou com nenhum
    # marcado — a tabela repetiria o resumo do topo linha por linha.
    if len(dias) < 2:
        return []

    # Pela data, e as sem dia marcado por ultimo: elas sao a pendencia, nao o
    # comeco da lista.
    return sorted(
        dias.values(), key=lambda d: (d.data is None, d.data or date.min)
    )


def _por_comissario(
    db: Session, alcance, criancas_visiveis, edicao_id: int, festa_ligada: bool = False
):
    """Cada comissario, o grupo dele, e o que falta no time dele.

    A lista comeca pelo time da edicao, e nao pelas criancas ja atribuidas: um
    comissario sem nenhuma crianca na mao e justamente o que a coordenacao
    precisa enxergar, e ele nao apareceria se a contagem mandasse.
    """
    tipos = _tipos_por_crianca(criancas_visiveis)

    contagens = {
        responsavel: (total, cesta, festa, completas)
        for responsavel, total, cesta, festa, completas in db.execute(
            select(
                Crianca.comissario_id,
                func.count(Crianca.id),
                func.coalesce(func.sum(tipos.c.cesta), 0),
                func.coalesce(func.sum(tipos.c.festa), 0),
                func.count(
                    case(((tipos.c.cesta > 0) & (tipos.c.festa > 0), Crianca.id))
                ),
            )
            .outerjoin(tipos, tipos.c.crianca_id == Crianca.id)
            .where(alcance)
            .group_by(Crianca.comissario_id)
        ).all()
    }

    # A festa de cada um, quando a campanha esta ligada: as criancas cuja festa
    # a coordenacao passou para ele, e quantas ja tem padrinho de festa. A
    # chave nula e a festa que ainda esta com a coordenacao.
    festas: dict = {}
    if festa_ligada:
        festas = {
            responsavel: (total, feitas)
            for responsavel, total, feitas in db.execute(
                select(
                    Crianca.comissario_festa_id,
                    func.count(Crianca.id),
                    func.coalesce(func.sum(tipos.c.festa), 0),
                )
                .outerjoin(tipos, tipos.c.crianca_id == Crianca.id)
                .where(alcance)
                .group_by(Crianca.comissario_festa_id)
            ).all()
        }

    def linha(i, nome, grupo):
        total, cesta, festa, completas = contagens.get(i, (0, 0, 0, 0))
        if not festa_ligada:
            return LinhaComissario(
                comissario_id=i, comissario=nome, grupo=grupo,
                criancas=total, cesta=cesta, festa=festa,
                completas=completas, faltam=total - completas,
            )
        festa_total, festa_feitas = festas.get(i, (0, 0))
        return LinhaComissario(
            comissario_id=i, comissario=nome, grupo=grupo,
            criancas=total, cesta=cesta, festa=festa_feitas,
            festa_criancas=festa_total, completas=completas,
            faltam=(total - cesta) + (festa_total - festa_feitas),
        )

    # O time da edicao. Coordenacao e administracao geral tambem podem assumir
    # criancas; elas entram na lista se tiverem alguma, mas sem grupo, porque
    # grupo e coisa de comissario.
    time = db.execute(
        select(Usuario.id, Usuario.nome, Grupo.nome, Perfil.nome)
        .join(UsuarioEdicao, UsuarioEdicao.usuario_id == Usuario.id)
        .join(Perfil, Perfil.id == UsuarioEdicao.perfil_id)
        .outerjoin(Grupo, Grupo.id == UsuarioEdicao.grupo_id)
        .where(UsuarioEdicao.edicao_id == edicao_id, UsuarioEdicao.ativo.is_(True))
    ).all()
    membros = {i: (nome, grupo, perfil) for i, nome, grupo, perfil in time}

    responsaveis = {
        i for i, (_, _, perfil) in membros.items() if perfil == PERFIL_COMISSARIO
    }
    responsaveis |= {i for i in contagens if i is not None}
    responsaveis |= {i for i in festas if i is not None}

    # Quem assumiu crianca mas nao tem vinculo ativo nesta edicao (saiu do time
    # depois de atribuido) continua aparecendo: as criancas dele existem.
    faltando = [i for i in responsaveis if i not in membros]
    if faltando:
        for i, nome in db.execute(
            select(Usuario.id, Usuario.nome).where(Usuario.id.in_(faltando))
        ).all():
            membros[i] = (nome, None, None)

    linhas = []
    for i in responsaveis:
        nome, grupo, perfil = membros.get(i, (f"Usuário {i}", None, None))
        # So comissario tem grupo; o resto do time aparece sem.
        linhas.append(linha(i, nome, grupo if perfil == PERFIL_COMISSARIO else None))

    # Em ordem alfabetica: e pelo nome que a coordenacao procura alguem. O
    # grupo segue ao lado do nome.
    # Sem acento na comparacao, senao "Alvaro" com acento iria para o fim.
    linhas.sort(key=lambda l: unicodedata.normalize("NFKD", l.comissario).casefold())

    if None in contagens or None in festas:
        linhas.append(linha(None, SEM_COMISSARIO, None))

    return linhas


# ------------------------------------------------------------------ atividade
#
# "Ver atividade", no painel da coordenacao: quem da equipe da edicao esta
# trabalhando e o que fez. So a coordenacao geral do evento e a administracao
# geral — e o trabalho de cada pessoa, nominalmente, e nao numero da edicao.

FUSO = ZoneInfo("America/Fortaleza")
POR_PAGINA = 50


def _so_coordenacao(ctx: ContextoAcesso, edicao_id: int) -> None:
    if not ctx.e_coordenacao_geral(edicao_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "A atividade da equipe e da coordenacao geral do evento.",
        )


def _equipe(db: Session, edicao_id: int):
    """Quem tem vinculo ativo nesta edicao, com o perfil de cada um."""
    return db.execute(
        select(Usuario, Perfil.nome)
        .join(UsuarioEdicao, UsuarioEdicao.usuario_id == Usuario.id)
        .join(Perfil, Perfil.id == UsuarioEdicao.perfil_id)
        .where(
            UsuarioEdicao.edicao_id == edicao_id,
            UsuarioEdicao.ativo.is_(True),
            Usuario.ativo.is_(True),
        )
    ).all()


TRABALHO = LogAtividade.acao.not_in(atividade.IGNORADAS)


@router.get("/{edicao_id}/atividade", response_model=list[PessoaAtividade])
def atividade_da_equipe(edicao_id: int, db: BD, ctx: Painel):
    _so_coordenacao(ctx, edicao_id)

    equipe = _equipe(db, edicao_id)
    ids = [u.id for u, _ in equipe]
    if not ids:
        return []

    agora = datetime.now(UTC)
    inicio_de_hoje = datetime.combine(agora.astimezone(FUSO).date(), time.min, FUSO)
    sete_dias = agora - timedelta(days=7)

    contas = {
        uid: (hoje, semana)
        for uid, hoje, semana in db.execute(
            select(
                LogAtividade.usuario_id,
                func.count(case((LogAtividade.criado_em >= inicio_de_hoje, 1))),
                func.count(),
            )
            .where(LogAtividade.usuario_id.in_(ids), TRABALHO, LogAtividade.criado_em >= sete_dias)
            .group_by(LogAtividade.usuario_id)
        ).all()
    }

    # A ultima acao de trabalho de cada um, de qualquer data: a mais recente
    # pela hora, uma por pessoa (DISTINCT ON do Postgres).
    ultimos = db.scalars(
        select(LogAtividade)
        .where(LogAtividade.usuario_id.in_(ids), TRABALHO)
        .distinct(LogAtividade.usuario_id)
        .order_by(LogAtividade.usuario_id, LogAtividade.criado_em.desc(), LogAtividade.id.desc())
    ).all()
    textos = dict(zip((log.usuario_id for log in ultimos), atividade.descrever_varios(db, ultimos)))
    ultimo_em = {log.usuario_id: log.criado_em for log in ultimos}

    pessoas = [
        PessoaAtividade(
            usuario_id=u.id,
            nome=u.nome,
            perfil=perfil,
            sem_senha=u.senha_hash is None,
            ultimo_acesso=u.ultimo_login,
            ultima_acao=textos.get(u.id),
            ultima_acao_em=ultimo_em.get(u.id),
            hoje=contas.get(u.id, (0, 0))[0],
            semana=contas.get(u.id, (0, 0))[1],
        )
        for u, perfil in equipe
    ]

    # Quem trabalhou por ultimo no topo; quem nunca fez nada, no fim, por nome.
    pessoas.sort(key=lambda p: (
        p.ultima_acao_em is None,
        -p.ultima_acao_em.timestamp() if p.ultima_acao_em else 0,
        p.nome.lower(),
    ))
    return pessoas


@router.get("/{edicao_id}/atividade/{usuario_id}", response_model=LinhaDoTempo)
def atividade_da_pessoa(
    edicao_id: int, usuario_id: int, db: BD, ctx: Painel, antes: int | None = None
):
    _so_coordenacao(ctx, edicao_id)

    pessoa = next((u for u, _ in _equipe(db, edicao_id) if u.id == usuario_id), None)
    if pessoa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esta pessoa nao esta na equipe desta edicao.")

    condicao = (LogAtividade.usuario_id == usuario_id) & TRABALHO
    if antes is not None:
        condicao = condicao & (LogAtividade.id < antes)

    logs = db.scalars(
        select(LogAtividade).where(condicao).order_by(LogAtividade.id.desc()).limit(POR_PAGINA + 1)
    ).all()
    mais = len(logs) > POR_PAGINA
    logs = logs[:POR_PAGINA]

    return LinhaDoTempo(
        usuario_id=pessoa.id,
        nome=pessoa.nome,
        itens=[
            ItemAtividade(id=log.id, quando=log.criado_em, texto=texto)
            for log, texto in zip(logs, atividade.descrever_varios(db, logs))
        ],
        mais=mais,
    )
