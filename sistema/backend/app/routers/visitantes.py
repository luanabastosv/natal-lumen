"""Visitantes do evento: o QR Code da pulseira, o cadastro e a planilha.

A pulseira do evento leva um QR Code que abre `/acesso/f/<codigo>`. La a
Estrelinha pede nome e celular e entrega o link das fotos. Um QR Code e um
link so por edicao, para os dois dias: a pulseira que sobra no sabado serve
no domingo, e a galeria separa os dias por dentro. Sao duas partes:

- PUBLICA (`/visitantes/publico/...`): sem sessao, e a pagina que o celular de
  qualquer visitante abre. Diz so o que a pagina precisa e grava o cadastro.
- PAINEL: a coordenacao geral do evento ve a planilha, baixa o QR Code e cola
  o link da galeria. Como a lista de cuidados especiais, e pelo perfil, e nao
  por permissao: e contato de gente de fora, e a lista inteira junta e mais
  do que as equipes precisam.

O link das fotos so sai DEPOIS do cadastro. Isso nao e seguranca — quem
recebe o link pode repassar —, e o combinado com o visitante: o contato em
troca das fotos.
"""

import io
import re
from typing import Annotated
from urllib.parse import quote
from zoneinfo import ZoneInfo

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import config
from app.database import get_db
from app.models import Apadrinhamento, Crianca, Edicao, Visitante
from app.models.tipos import TipoApadrinhamento
from app.seguranca.dependencias import Contexto
from app.servicos.apadrinhamento import CONFIRMADO
from app.servicos.log import registrar

router = APIRouter(prefix="/visitantes", tags=["visitantes"])

BD = Annotated[Session, Depends(get_db)]

FUSO = ZoneInfo("America/Fortaleza")


# ------------------------------------------------------------------ esquemas
class EdicaoPublica(BaseModel):
    edicao: str


class CadastroVisitante(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    celular: str

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v).strip()
        if len(v) < 2:
            raise ValueError("Escreva o seu nome.")
        return v

    @field_validator("celular")
    @classmethod
    def _celular(cls, v: str) -> str:
        digitos = re.sub(r"\D", "", v)
        if len(digitos) not in (10, 11):
            raise ValueError("O celular precisa do DDD: 10 ou 11 digitos.")
        return digitos


class FotosLiberadas(BaseModel):
    link_fotos: str | None


class CadastroFeito(FotosLiberadas):
    """O que a Estrelinha precisa para fechar a conversa.

    Antes das fotos ela lembra quantos apadrinhamentos ainda faltam e oferece
    o WhatsApp da coordenacao. `faltam` 0 ou `whatsapp_ajuda` nulo: ela pula o
    convite e entrega as fotos.
    """

    faltam: int
    whatsapp_ajuda: str | None


MENSAGEM_AJUDA = (
    "Oi! Vim pelo QR Code das fotos do Natal Lumen e quero ajudar a "
    "apadrinhar uma criança."
)


class VisitanteOut(BaseModel):
    id: int
    nome: str
    celular: str
    criado_em: str


class Visitantes(BaseModel):
    codigo_fotos: str
    endereco_qr: str
    link_fotos: str | None
    visitantes: list[VisitanteOut]


class LinkFotos(BaseModel):
    link_fotos: str | None = Field(default=None, max_length=500)

    @field_validator("link_fotos")
    @classmethod
    def _link(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if not v:
            return None
        if not re.match(r"^https://[^\s]+$", v):
            raise ValueError("O link precisa comecar com https://")
        return v


# ------------------------------------------------------------------ apoio
def _endereco_qr(codigo: str) -> str:
    base = (config.url_publica or "https://acesso.natallumen.com").rstrip("/")
    return f"{base}/acesso/f/{codigo}"


def _celular_formatado(d: str) -> str:
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    return f"({d[:2]}) {d[2:6]}-{d[6:]}"


def _garantir_codigo(db: Session, edicao: Edicao) -> str:
    """O codigo do QR Code da edicao, criado na primeira vez que e pedido.

    "nl26": Natal Lumen e o ano. Se outra edicao do mesmo ano ja tem o mesmo,
    ganha um numero ("nl26-2"). Depois de criado nao muda nunca: ja pode estar
    impresso numa pulseira.
    """
    if edicao.codigo_fotos:
        return edicao.codigo_fotos
    base = f"nl{edicao.ano % 100:02d}"
    codigo, n = base, 1
    while db.scalar(select(Edicao.id).where(Edicao.codigo_fotos == codigo)):
        n += 1
        codigo = f"{base}-{n}"
    edicao.codigo_fotos = codigo
    return codigo


def _edicao_por_codigo(db: Session, codigo: str) -> Edicao:
    edicao = db.scalar(select(Edicao).where(Edicao.codigo_fotos == codigo.strip().lower()))
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "QR Code nao encontrado.")
    return edicao


def _edicao_do_painel(db: Session, ctx, edicao_id: int) -> Edicao:
    if not ctx.e_coordenacao_geral(edicao_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Os visitantes do evento sao da coordenacao geral.",
        )
    edicao = db.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")
    return edicao


def _faltam_apadrinhar(db: Session, edicao: Edicao) -> int:
    """O "faltam" do painel para a edicao inteira: as cestas que faltam,
    mais as festas que faltam quando a festa ja esta aberta.

    Conta vagas, nao criancas (a crianca sem os dois soma 2). Mesma regra do
    painel: sem as desistentes, e so o apadrinhamento pago conta.
    """
    ativas = select(Crianca.id).where(
        Crianca.edicao_id == edicao.id, Crianca.desistiu_em.is_(None)
    )
    criancas = db.scalar(select(func.count()).select_from(ativas.subquery())) or 0
    feitos = dict(
        db.execute(
            select(Apadrinhamento.tipo, func.count())
            .where(Apadrinhamento.crianca_id.in_(ativas), CONFIRMADO)
            .group_by(Apadrinhamento.tipo)
        ).all()
    )
    faltam = criancas - feitos.get(TipoApadrinhamento.CESTA.value, 0)
    if edicao.festa_liberada_em is not None:
        faltam += criancas - feitos.get(TipoApadrinhamento.FESTA.value, 0)
    return max(faltam, 0)


def _whatsapp_ajuda() -> str | None:
    numero = re.sub(r"\D", "", config.whatsapp_coordenacao)
    if not numero:
        return None
    return f"https://wa.me/{numero}?text={quote(MENSAGEM_AJUDA)}"


# ------------------------------------------------------------------ publico
@router.get("/publico/{codigo}", response_model=EdicaoPublica)
def edicao_publica(codigo: str, db: BD):
    """Confere o QR Code antes de a pessoa preencher. Sem sessao.

    Nao diz quantos visitantes ha, nem o link das fotos.
    """
    return EdicaoPublica(edicao=_edicao_por_codigo(db, codigo).nome)


@router.post("/publico/{codigo}", response_model=CadastroFeito)
def cadastrar(codigo: str, dados: CadastroVisitante, db: BD):
    """Grava o visitante e devolve o link das fotos (ou nulo, se a galeria
    ainda nao estiver pronta).

    Sem sessao. O mesmo celular na mesma edicao atualiza o nome, sem duplicar.
    """
    edicao = _edicao_por_codigo(db, codigo)
    db.execute(
        insert(Visitante)
        .values(edicao_id=edicao.id, nome=dados.nome, celular=dados.celular)
        .on_conflict_do_update(
            constraint="uq_visitantes_edicao_celular",
            set_={"nome": dados.nome},
        )
    )
    db.commit()
    return CadastroFeito(
        link_fotos=edicao.link_fotos,
        faltam=_faltam_apadrinhar(db, edicao),
        whatsapp_ajuda=_whatsapp_ajuda(),
    )


# ------------------------------------------------------------------ painel
@router.get("", response_model=Visitantes)
def listar(edicao_id: int, db: BD, ctx: Contexto):
    """O QR Code da edicao, o link das fotos e a lista de visitantes.

    Abrir a tela cria o codigo do QR, se a edicao ainda nao tem — e ali que a
    coordenacao vai busca-lo para mandar a grafica.
    """
    edicao = _edicao_do_painel(db, ctx, edicao_id)
    if not edicao.codigo_fotos:
        _garantir_codigo(db, edicao)
        db.commit()

    visitantes = db.scalars(
        select(Visitante)
        .where(Visitante.edicao_id == edicao_id)
        .order_by(Visitante.criado_em.desc(), Visitante.id.desc())
    ).all()

    return Visitantes(
        codigo_fotos=edicao.codigo_fotos,
        endereco_qr=_endereco_qr(edicao.codigo_fotos),
        link_fotos=edicao.link_fotos,
        visitantes=[
            VisitanteOut(
                id=v.id,
                nome=v.nome,
                celular=_celular_formatado(v.celular),
                criado_em=v.criado_em.astimezone(FUSO).strftime("%d/%m %H:%M"),
            )
            for v in visitantes
        ],
    )


@router.put("/link", response_model=FotosLiberadas)
def salvar_link(edicao_id: int, dados: LinkFotos, db: BD, ctx: Contexto):
    """O link da galeria de fotos. Vazio = fotos ainda nao prontas."""
    edicao = _edicao_do_painel(db, ctx, edicao_id)
    edicao.link_fotos = dados.link_fotos
    _garantir_codigo(db, edicao)
    registrar(
        db,
        "alterar_link_fotos",
        usuario_id=ctx.usuario.id,
        tabela="edicoes",
        registro_id=edicao.id,
        detalhes={"link_fotos": dados.link_fotos},
    )
    db.commit()
    return FotosLiberadas(link_fotos=edicao.link_fotos)


@router.get("/qrcode")
def baixar_qrcode(
    edicao_id: int,
    db: BD,
    ctx: Contexto,
    formato: Annotated[str, Query(pattern="^(png|svg)$")] = "png",
):
    """O QR Code das pulseiras. PNG para conferir; SVG para a grafica, que
    aumenta sem perder nitidez."""
    edicao = _edicao_do_painel(db, ctx, edicao_id)
    codigo = _garantir_codigo(db, edicao)
    db.commit()

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2, box_size=24)
    qr.add_data(_endereco_qr(codigo))
    qr.make(fit=True)
    buffer = io.BytesIO()
    if formato == "svg":
        qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).save(buffer)
        tipo = "image/svg+xml"
    else:
        qr.make_image(fill_color="#153377", back_color="white").save(buffer)
        tipo = "image/png"
    nome = f"QR_PULSEIRA_NATAL_LUMEN_{edicao.ano}.{formato}"
    return Response(
        content=buffer.getvalue(),
        media_type=tipo,
        headers={"Content-Disposition": f'inline; filename="{nome}"'},
    )


@router.get("/planilha")
def baixar_planilha(edicao_id: int, db: BD, ctx: Contexto):
    """A planilha (.xlsx) dos visitantes da edicao."""
    edicao = _edicao_do_painel(db, ctx, edicao_id)

    livro = Workbook()
    aba = livro.active
    aba.title = "Visitantes"
    aba.append(["Nome", "Celular", "Cadastro"])
    for c in aba[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="153377")
    for v in db.scalars(
        select(Visitante).where(Visitante.edicao_id == edicao_id).order_by(Visitante.criado_em)
    ):
        aba.append(
            [
                v.nome,
                _celular_formatado(v.celular),
                v.criado_em.astimezone(FUSO).strftime("%d/%m/%Y %H:%M"),
            ]
        )
    aba.column_dimensions["A"].width = 38
    aba.column_dimensions["B"].width = 18
    aba.column_dimensions["C"].width = 18

    registrar(
        db, "baixar_planilha_visitantes", usuario_id=ctx.usuario.id, detalhes={"edicao_id": edicao_id}
    )
    db.commit()
    buffer = io.BytesIO()
    livro.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="VISITANTES_NATAL_LUMEN_{edicao.ano}.xlsx"'
        },
    )
