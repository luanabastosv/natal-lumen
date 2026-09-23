"""O dia do evento de cada instituicao.

O dia e da instituicao, nao da crianca. Este modulo e o unico lugar que grava
crianca.dia_evento_id — assim duas criancas da mesma escola nunca caem em dias
diferentes.
"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Crianca, InstituicaoDia


def dia_da_instituicao(db: Session, edicao_id: int, instituicao_id: int) -> int | None:
    """O dia marcado para esta instituicao nesta edicao, se houver."""
    return db.scalar(
        select(InstituicaoDia.dia_evento_id).where(
            InstituicaoDia.edicao_id == edicao_id,
            InstituicaoDia.instituicao_id == instituicao_id,
        )
    )


def definir(
    db: Session, edicao_id: int, instituicao_id: int, dia_evento_id: int | None
) -> int:
    """Marca o dia da instituicao e leva todas as criancas dela junto.

    dia_evento_id None desmarca. Devolve quantas criancas foram atualizadas.
    """
    ligacao = db.scalar(
        select(InstituicaoDia).where(
            InstituicaoDia.edicao_id == edicao_id,
            InstituicaoDia.instituicao_id == instituicao_id,
        )
    )

    if dia_evento_id is None:
        if ligacao is not None:
            db.delete(ligacao)
    elif ligacao is None:
        db.add(
            InstituicaoDia(
                edicao_id=edicao_id,
                instituicao_id=instituicao_id,
                dia_evento_id=dia_evento_id,
            )
        )
    else:
        ligacao.dia_evento_id = dia_evento_id

    # Em massa: numa instituicao de 300 criancas, uma a uma seria lento e o
    # resultado, o mesmo.
    resultado = db.execute(
        update(Crianca)
        .where(
            Crianca.edicao_id == edicao_id,
            Crianca.instituicao_id == instituicao_id,
        )
        .values(dia_evento_id=dia_evento_id)
    )
    db.flush()
    return resultado.rowcount or 0


def aplicar_a_novas(db: Session, edicao_id: int, instituicao_ids: set[int]) -> None:
    """Depois de importar, acerta o dia das criancas que acabaram de entrar.

    Sem isto, uma lista importada depois de a instituicao ja ter dia marcado
    entraria sem dia nenhum.
    """
    for instituicao_id in instituicao_ids:
        dia = dia_da_instituicao(db, edicao_id, instituicao_id)
        if dia is None:
            continue
        db.execute(
            update(Crianca)
            .where(
                Crianca.edicao_id == edicao_id,
                Crianca.instituicao_id == instituicao_id,
                Crianca.dia_evento_id.is_(None),
            )
            .values(dia_evento_id=dia)
        )
    db.flush()
