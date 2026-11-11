"""As vivencias de intercessao marcadas nas criancas.

Quem marcou e quem rezou: cada vivencia de uma crianca tem um dono so, e o
nome dele aparece como etiqueta ao lado do checkbox. Ver o modelo
`Intercessao` em models/oracao.py.
"""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Intercessao
from app.models.tipos import TipoIntercessao

# Quantas criancas cada vivencia leva, pela regra da planilha: cinco por missa,
# adoracao ou jejum; quinze por terco (tres por misterio, cinco misterios).
CRIANCAS_POR_VIVENCIA = {
    TipoIntercessao.MISSA.value: 5,
    TipoIntercessao.ADORACAO.value: 5,
    TipoIntercessao.JEJUM.value: 5,
    TipoIntercessao.TERCO.value: 15,
}


def marcas(db: Session, ids: list[int]) -> dict[int, list[dict]]:
    """As marcacoes de varias criancas, numa consulta so, da mais antiga para a
    mais nova."""
    por_crianca: dict[int, list[dict]] = defaultdict(list)
    if not ids:
        return por_crianca
    for m in db.scalars(
        select(Intercessao)
        .where(Intercessao.crianca_id.in_(ids))
        .options(joinedload(Intercessao.usuario))
        .order_by(Intercessao.criado_em, Intercessao.id)
    ).all():
        por_crianca[m.crianca_id].append(
            {
                "tipo": m.tipo,
                "usuario_id": m.usuario_id,
                "nome": m.usuario.nome if m.usuario else None,
                "em": m.criado_em,
            }
        )
    return por_crianca
