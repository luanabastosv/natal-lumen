"""A crianca pela qual o sistema convida a rezar hoje.

Uma por dia, por pessoa. A escolha nao e sorteio e nao fica gravada em lugar
nenhum: e uma conta sobre a data e o id do usuario. Duas consequencias, e as
duas sao o motivo de ser assim:

  - recarregar a pagina nao troca a crianca. Um sorteio de verdade daria um
    nome diferente a cada chamada, e o convite de hoje viraria outro no meio
    da oracao;
  - a lista e percorrida de ponta a ponta, um nome por dia, sem repetir
    enquanto houver nome novo. Um sorteio repetiria a mesma crianca em dias
    seguidos e deixaria outras de fora por semanas.

O deslocamento pelo id do usuario e o que faz duas pessoas da mesma equipe
comecarem em pontos diferentes da lista — senao a cidade inteira rezaria pelo
mesmo nome todo dia.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Crianca
from app.seguranca.contexto import ContextoAcesso

# O servidor roda em UTC. Sem o fuso daqui, o convite trocaria de crianca as
# 21h de Brasilia — no meio do trabalho de quem esta usando o sistema.
FUSO = ZoneInfo("America/Sao_Paulo")


def dia_de_hoje() -> int:
    """O dia corrente como numero, para a conta que escolhe a crianca."""
    return datetime.now(FUSO).date().toordinal()


def crianca_do_dia(
    db: Session, ctx: ContextoAcesso, edicao_id: int
) -> Crianca | None:
    """A crianca de hoje para este usuario, ou None se ele nao alcanca nenhuma.

    O alcance e o mesmo de toda consulta de criancas no sistema: o comissario
    reza pelas criancas que estao na mao dele, a coordenacao pela edicao
    inteira. E o filtro que faz o papel de portao — quem nao tem `ver_criancas`
    nesta edicao recebe `false()` e sai daqui com None, sem rota nenhuma
    precisar conferir permissao antes.

    Quem desistiu fica de fora: a crianca continua na lista das telas, riscada,
    porque o cartao e o kit dela ainda existem — mas ela nao vai mais ao
    evento, e o convite e para interceder por quem vai.
    """
    alcance = (
        ctx.filtro_criancas("ver_criancas")
        & (Crianca.edicao_id == edicao_id)
        & (Crianca.desistiu_em.is_(None))
    )

    total = db.scalar(select(func.count()).select_from(Crianca).where(alcance)) or 0
    if total == 0:
        return None

    # Ordenada por id: a ordem precisa ser a mesma amanha, senao o passo de um
    # dia cairia num nome ja visto. Por id, uma crianca nova entra no fim e nao
    # embaralha o que ja passou.
    posicao = (dia_de_hoje() + ctx.usuario.id) % total

    return db.scalar(
        select(Crianca)
        .where(alcance)
        .options(joinedload(Crianca.instituicao))
        .order_by(Crianca.id)
        .offset(posicao)
        .limit(1)
    )
