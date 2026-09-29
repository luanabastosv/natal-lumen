"""Painel da edicao: o apadrinhamento de cesta e de festa, e quem falta.

Todos os numeros passam pelo mesmo filtro das telas: quem so alcanca algumas
instituicoes ve os numeros dessas instituicoes, e nao da edicao inteira. Com o
comissario o filtro vai mais fundo — crianca a crianca — e o painel entao deixa
de ser o da edicao para ser o dele: as criancas que estao na mao dele, e quanto
ainda falta apadrinhar delas.
"""

from datetime import date
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
    Perfil,
    Usuario,
    UsuarioEdicao,
)
from app.models.tipos import Sexo, TipoApadrinhamento
from app.schemas.painel import (
    FaixaIdade,
    LinhaComissario,
    LinhaDia,
    LinhaInstituicao,
    Relatorio,
    ResumoEdicao,
)
from app.seeds.perfis_permissoes import PERFIL_COMISSARIO
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao

router = APIRouter(prefix="/painel", tags=["painel"])

BD = Annotated[Session, Depends(get_db)]
Painel = Annotated[ContextoAcesso, Depends(exige_permissao("ver_painel"))]

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
        .where(Apadrinhamento.crianca_id.in_(criancas_visiveis))
        .group_by(Apadrinhamento.crianca_id)
        .subquery()
    )


@router.get("/{edicao_id}", response_model=Relatorio)
def relatorio(edicao_id: int, db: BD, ctx: Painel):
    edicao = db.scalar(
        select(Edicao).where(Edicao.id == edicao_id).options(joinedload(Edicao.cidade))
    )
    if edicao is None or not ctx.alcanca_edicao(edicao_id, "ver_painel"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    # Mesmo filtro das telas: quem so alcanca algumas instituicoes ve os
    # numeros dessas instituicoes.
    alcance = ctx.filtro_criancas("ver_painel") & (Crianca.edicao_id == edicao_id)
    criancas_visiveis = select(Crianca.id).where(alcance)

    criancas = db.scalar(select(func.count()).select_from(Crianca).where(alcance)) or 0
    instituicoes = db.scalar(
        select(func.count(func.distinct(Crianca.instituicao_id))).where(alcance)
    ) or 0

    por_tipo = dict(
        db.execute(
            select(Apadrinhamento.tipo, func.count())
            .where(Apadrinhamento.crianca_id.in_(criancas_visiveis))
            .group_by(Apadrinhamento.tipo)
        ).all()
    )

    # Crianca completa: tem cesta E festa. Conta uma vez por crianca, entao sai
    # de um agrupamento — somar os dois tipos contaria a completa duas vezes.
    completas = db.scalar(
        select(func.count()).select_from(
            select(Apadrinhamento.crianca_id)
            .where(Apadrinhamento.crianca_id.in_(criancas_visiveis))
            .group_by(Apadrinhamento.crianca_id)
            .having(func.count(func.distinct(Apadrinhamento.tipo)) == 2)
            .subquery()
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
        festa_feitos=por_tipo.get(FESTA, 0),
        completas=completas,
    )

    # O comissario ja esta vendo so as criancas dele — a quebra por comissario
    # nao tem o que quebrar, e traria os colegas todos zerados. Ela e da
    # coordenacao, que e quem distribui a lista e cobra o time.
    so_minhas_criancas = ctx.so_proprias_criancas(edicao_id)
    por_instituicao = _por_instituicao(db, alcance, criancas_visiveis, edicao_id)

    return Relatorio(
        resumo=resumo,
        so_minhas_criancas=so_minhas_criancas,
        por_instituicao=por_instituicao,
        por_comissario=(
            []
            if so_minhas_criancas
            else _por_comissario(db, alcance, criancas_visiveis, edicao_id)
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


def _por_comissario(db: Session, alcance, criancas_visiveis, edicao_id: int):
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
        total, cesta, festa, completas = contagens.get(i, (0, 0, 0, 0))
        # So comissario tem grupo; o resto do time aparece sem.
        linhas.append(
            LinhaComissario(
                comissario_id=i, comissario=nome,
                grupo=grupo if perfil == PERFIL_COMISSARIO else None,
                criancas=total, cesta=cesta, festa=festa,
                completas=completas, faltam=total - completas,
            )
        )

    # Sem grupo vai para o fim de cada bloco, e o nome ordena dentro do grupo.
    linhas.sort(key=lambda l: (l.grupo is None, l.grupo or "", l.comissario))

    if None in contagens:
        total, cesta, festa, completas = contagens[None]
        linhas.append(
            LinhaComissario(
                comissario_id=None, comissario=SEM_COMISSARIO, grupo=None,
                criancas=total, cesta=cesta, festa=festa,
                completas=completas, faltam=total - completas,
            )
        )

    return linhas
