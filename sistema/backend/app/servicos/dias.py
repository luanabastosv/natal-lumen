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


def onibus_da_instituicao(db: Session, edicao_id: int, instituicao_id: int) -> int:
    """Quantos onibus buscam esta instituicao nesta edicao. Sem dia, zero."""
    return (
        db.scalar(
            select(InstituicaoDia.onibus).where(
                InstituicaoDia.edicao_id == edicao_id,
                InstituicaoDia.instituicao_id == instituicao_id,
            )
        )
        or 0
    )


def definir(
    db: Session,
    edicao_id: int,
    instituicao_id: int,
    dia_evento_id: int | None,
    onibus: int | None = None,
) -> int:
    """Marca o dia da instituicao e leva todas as criancas dela junto.

    dia_evento_id None desmarca. `onibus` None deixa o numero como esta — quem
    so troca o dia de uma instituicao nao perde o transporte ja combinado.
    Devolve quantas criancas foram atualizadas.
    """
    ligacao = db.scalar(
        select(InstituicaoDia).where(
            InstituicaoDia.edicao_id == edicao_id,
            InstituicaoDia.instituicao_id == instituicao_id,
        )
    )

    if dia_evento_id is None:
        # Desmarcar o dia leva o numero de onibus junto, e esta certo: onibus e
        # o transporte PARA aquele dia. Sem dia nao ha o que transportar.
        if ligacao is not None:
            db.delete(ligacao)
    elif ligacao is None:
        db.add(
            InstituicaoDia(
                edicao_id=edicao_id,
                instituicao_id=instituicao_id,
                dia_evento_id=dia_evento_id,
                onibus=onibus or 0,
            )
        )
    else:
        ligacao.dia_evento_id = dia_evento_id
        if onibus is not None:
            ligacao.onibus = onibus

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
