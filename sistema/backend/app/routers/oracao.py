"""O convite de oracao do primeiro acesso do dia.

Rota de leitura e nada mais: quem guarda que a pessoa ja viu o convite hoje e
o proprio navegador. Por isso nao ha POST aqui, e nao ha tabela.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.oracao import ConviteDoDia
from app.seguranca.dependencias import Contexto
from app.servicos.oracao import crianca_do_dia

router = APIRouter(prefix="/oracao", tags=["oracao"])

BD = Annotated[Session, Depends(get_db)]


@router.get("/{edicao_id}", response_model=ConviteDoDia)
def convite(edicao_id: int, db: BD, ctx: Contexto):
    """A crianca de hoje para quem esta na sessao.

    Sem `exige_permissao` de proposito, e sem 404 para edicao fora de alcance:
    quem nao alcanca criancas nesta edicao recebe o convite vazio, nao um erro.
    O portao e o filtro dentro de `crianca_do_dia`, que e o mesmo de todas as
    consultas de crianca — um 403 aqui so faria uma tela de trabalho abrir com
    um erro que ninguem pediu.
    """
    crianca = crianca_do_dia(db, ctx, edicao_id)
    if crianca is None:
        return ConviteDoDia()

    return ConviteDoDia(crianca=crianca.nome, instituicao=crianca.instituicao.nome)
