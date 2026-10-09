"""O lembrete do evento: a mensagem que cada padrinho recebe na semana do
evento, convidando-o a ir, com os cartoes que as criancas dele escreveram.

Hoje isso e feito a mao, padrinho por padrinho, cacando o cartao de cada
crianca. Aqui o sistema monta a lista sozinho, porque ja sabe o caminho
inteiro: padrinho -> apadrinhamento -> crianca -> cartao do mesmo tipo.

**Um lembrete por padrinho POR DIA do evento.** A crianca vai a um dia so, e o
convite e para aquele dia. Quem apadrinhou criancas de dois dias recebe duas
mensagens, cada uma dizendo de que dia fala e levando so os cartoes das
criancas daquele dia — ver docs/LEMBRETE_DO_EVENTO.md, onde esta o texto.

**So sai quando esta tudo pronto.** Um padrinho com tres criancas no sabado e
dois cartoes subidos fica "em progresso": mandar o lembrete com dois cartoes e
depois o terceiro sozinho seria pior que esperar.

Quem entra no lembrete:

  - so apadrinhamento CONFIRMADO, pela mesma regra do agradecimento
    (servicos/apadrinhamento.py): promessa nao recebe cartao;
  - so crianca que nao desistiu: o convite e para ve-la no evento, e o cartao
    dela nao entra num lembrete de um dia em que ela nao vai estar.

Esta rota so MONTA a lista. O disparo entra quando o CRM estiver ligado.
"""

from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Apadrinhamento, Cartao, Crianca, DiaEvento
from app.schemas.lembretes import CartaoDoLembrete, DiaLembretes, LembretePadrinho
from app.seguranca.contexto import ContextoAcesso
from app.seguranca.dependencias import exige_permissao
from app.servicos import whatsapp
from app.servicos.apadrinhamento import CONFIRMADO

router = APIRouter(prefix="/lembretes", tags=["lembretes"])

BD = Annotated[Session, Depends(get_db)]
Enviar = Annotated[ContextoAcesso, Depends(exige_permissao("enviar_cartoes"))]

def _e_coordenacao_geral(ctx: ContextoAcesso, edicao_id: int) -> bool:
    """Se quem pede e a coordenacao geral do evento nesta edicao.

    So ela, desde 08/10/2026 — nem a coordenacao da captacao. O lembrete sai
    em nome do evento para todos os padrinhos de uma vez, e quem decide quando
    e o que vai e quem responde pelo evento inteiro.

    Pelo NOME do perfil, e nao por permissao, como os outros dois lugares do
    sistema que olham papel em vez de poder (ver PERFIL_COORDENACAO em
    seeds/perfis_permissoes.py). A coordenacao enxerga a edicao inteira, entao
    o padrinho aparece sempre com todas as criancas dele — e nunca "pronto"
    com metade dos cartoes, como pareceria a um comissario.
    """
    return ctx.e_coordenacao_geral(edicao_id)


def _situacao(faltam: int, whatsapp_valido: bool) -> str:
    if faltam:
        return "em_progresso"
    return "pronto" if whatsapp_valido else "sem_whatsapp"


@router.get("", response_model=list[DiaLembretes])
def listar(edicao_id: int, db: BD, ctx: Enviar):
    """Os lembretes da edicao, agrupados por dia do evento."""
    if not _e_coordenacao_geral(ctx, edicao_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "O envio dos lembretes e da coordenacao geral do evento.",
        )

    apadrinhamentos = db.scalars(
        select(Apadrinhamento)
        .join(Crianca, Crianca.id == Apadrinhamento.crianca_id)
        .where(Crianca.edicao_id == edicao_id, Crianca.desistiu_em.is_(None), CONFIRMADO)
        .options(
            joinedload(Apadrinhamento.crianca).joinedload(Crianca.instituicao),
            joinedload(Apadrinhamento.padrinho),
        )
        .order_by(Crianca.codigo)
    ).all()

    # Os cartoes da edicao inteira numa consulta so, em vez de um por crianca.
    cartoes = {
        (crianca_id, tipo): cartao_id
        for cartao_id, crianca_id, tipo in db.execute(
            select(Cartao.id, Cartao.crianca_id, Cartao.tipo).where(
                Cartao.crianca_id.in_(select(Crianca.id).where(Crianca.edicao_id == edicao_id))
            )
        ).all()
    }

    # dia -> padrinho -> [apadrinhamentos]
    grupos: dict[int | None, dict[int, list[Apadrinhamento]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for a in apadrinhamentos:
        grupos[a.crianca.dia_evento_id][a.padrinho_id].append(a)

    dias_do_padrinho: dict[int, int] = defaultdict(int)
    for por_padrinho in grupos.values():
        for padrinho_id in por_padrinho:
            dias_do_padrinho[padrinho_id] += 1

    dias = db.scalars(
        select(DiaEvento).where(DiaEvento.edicao_id == edicao_id).order_by(DiaEvento.data)
    ).all()

    def lembretes(por_padrinho: dict[int, list[Apadrinhamento]]) -> list[LembretePadrinho]:
        saida = []
        for padrinho_id, lista in por_padrinho.items():
            padrinho = lista[0].padrinho
            itens = [
                CartaoDoLembrete(
                    apadrinhamento_id=a.id,
                    crianca_id=a.crianca_id,
                    crianca_codigo=a.crianca.codigo,
                    crianca_nome=a.crianca.nome,
                    instituicao_id=a.crianca.instituicao_id,
                    instituicao=a.crianca.instituicao.nome,
                    tipo=a.tipo,
                    cartao_id=cartoes.get((a.crianca_id, a.tipo)),
                )
                for a in lista
            ]
            faltam = sum(1 for c in itens if c.cartao_id is None)
            valido = whatsapp.telefone_e164(padrinho.whatsapp) is not None
            saida.append(
                LembretePadrinho(
                    padrinho_id=padrinho_id,
                    padrinho_nome=padrinho.nome,
                    whatsapp=padrinho.whatsapp,
                    whatsapp_valido=valido,
                    cartoes=itens,
                    faltam=faltam,
                    situacao=_situacao(faltam, valido),
                    outros_dias=dias_do_padrinho[padrinho_id] - 1,
                )
            )
        return sorted(saida, key=lambda p: p.padrinho_nome.lower())

    # Todo dia da edicao aparece, mesmo sem lembrete nenhum: uma aba que some
    # quando esta vazia faria a pessoa achar que o dia nao existe.
    resposta = [
        DiaLembretes(
            dia_id=d.id,
            data=d.data,
            descricao=d.descricao,
            padrinhos=lembretes(grupos.get(d.id, {})),
        )
        for d in dias
    ]
    if None in grupos:
        resposta.append(DiaLembretes(padrinhos=lembretes(grupos[None])))
    return resposta
