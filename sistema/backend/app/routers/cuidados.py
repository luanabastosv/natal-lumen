"""Cuidados especiais: as criancas cuja autorizacao avisa alguma coisa.

Necessidade especial, alergia ou restricao alimentar, e as outras
observacoes que o responsavel escreveu. A lista e da coordenacao geral do
evento — e quem prepara o dia (a comida, a estrutura, quem acompanha quem) —
e vem separada por dia do evento, que e como ela e usada.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Autorizacao, Crianca
from app.schemas.cuidados import CriancaComCuidados
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao

router = APIRouter(prefix="/cuidados", tags=["cuidados"])

BD = Annotated[Session, Depends(get_db)]
Ver = Annotated[ContextoAcesso, Depends(exige_permissao("ver_criancas"))]


@router.get("", response_model=list[CriancaComCuidados])
def listar(edicao_id: int, db: BD, ctx: Ver):
    """As criancas da edicao com algum "Sim" na autorizacao.

    So a coordenacao geral do evento e a administracao geral: e dado de saude
    de crianca, e a lista inteira junta numa tela so e mais do que cada equipe
    precisa ver. Quem recebe a crianca ve o aviso dela na propria lista.
    """
    if not ctx.e_coordenacao_geral(edicao_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "A lista de cuidados especiais e da coordenacao geral do evento.",
        )

    linhas = db.execute(
        select(Crianca, Autorizacao)
        .join(Autorizacao, Autorizacao.crianca_id == Crianca.id)
        .where(
            Crianca.edicao_id == edicao_id,
            Autorizacao.necessidade_especial.is_(True)
            | Autorizacao.restricao_alimentar.is_(True)
            | Autorizacao.tem_observacao.is_(True),
        )
        .options(joinedload(Crianca.instituicao), joinedload(Crianca.dia_evento))
        .order_by(Crianca.codigo)
    ).all()

    return [
        CriancaComCuidados(
            crianca_id=c.id,
            codigo=c.codigo,
            nome=c.nome,
            idade=c.idade,
            sexo=c.sexo,
            instituicao_id=c.instituicao_id,
            instituicao=c.instituicao.nome,
            dia_evento_id=c.dia_evento_id,
            dia_evento=c.dia_evento.data if c.dia_evento else None,
            dia_evento_descricao=c.dia_evento.descricao if c.dia_evento else None,
            necessidade_especial=a.necessidade_especial_qual if a.necessidade_especial else None,
            restricao_alimentar=a.restricao_alimentar_qual if a.restricao_alimentar else None,
            observacao=a.observacao if a.tem_observacao else None,
            desistiu_em=c.desistiu_em,
        )
        for c, a in linhas
    ]
