"""Visitantes do evento: o QR Code da pulseira, o cadastro e a planilha.

A pulseira do evento leva um QR Code que abre `/acesso/f/<codigo>`. La a
Estrelinha pede nome e celular e entrega o link das fotos do dia. Sao duas
partes:

- PUBLICA (`/visitantes/publico/...`): sem sessao, e a pagina que o celular de
  qualquer visitante abre. Diz so o que a pagina precisa e grava o cadastro.
- PAINEL: a coordenacao geral do evento ve a planilha, baixa os QR Codes e
  cola o link da galeria. Como a lista de cuidados especiais, e pelo perfil, e
  nao por permissao: e contato de gente de fora, e a lista inteira junta e
  mais do que as equipes precisam.

O link das fotos so sai DEPOIS do cadastro. Isso nao e seguranca — quem
recebe o link pode repassar —, e o combinado com o visitante: o contato em
troca das fotos.
"""

import io
import re
from datetime import date
from typing import Annotated
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
from app.models import DiaEvento, Edicao, Visitante
from app.seguranca.dependencias import Contexto
from app.servicos.log import registrar

router = APIRouter(prefix="/visitantes", tags=["visitantes"])

BD = Annotated[Session, Depends(get_db)]

FUSO = ZoneInfo("America/Fortaleza")
DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
NOMES_DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


# ------------------------------------------------------------------ esquemas
class DiaPublico(BaseModel):
    edicao: str
    dia: str


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


class DiaVisitantes(BaseModel):
    id: int
    data: date
    descricao: str | None
    codigo_fotos: str
    endereco_qr: str
    link_fotos: str | None
    total: int


class VisitanteOut(BaseModel):
    id: int
    nome: str
    celular: str
    dia_evento_id: int
    criado_em: str


class Visitantes(BaseModel):
    dias: list[DiaVisitantes]
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


def _garantir_codigo(db: Session, dia: DiaEvento, ano: int) -> str:
    """O codigo do QR Code do dia, criado na primeira vez que e pedido.

    "26-sab": o ano e o dia da semana, que e como a equipe fala do evento. Se
    outra edicao do mesmo ano ja tem o mesmo, ganha um numero ("26-sab-2").
    Depois de criado nao muda nunca: ja pode estar impresso numa pulseira.
    """
    if dia.codigo_fotos:
        return dia.codigo_fotos
    base = f"{ano % 100:02d}-{DIAS_SEMANA[dia.data.weekday()]}"
    codigo, n = base, 1
    while db.scalar(select(DiaEvento.id).where(DiaEvento.codigo_fotos == codigo)):
        n += 1
        codigo = f"{base}-{n}"
    dia.codigo_fotos = codigo
    return codigo


def _dia_por_codigo(db: Session, codigo: str) -> tuple[DiaEvento, Edicao]:
    linha = db.execute(
        select(DiaEvento, Edicao)
        .join(Edicao, Edicao.id == DiaEvento.edicao_id)
        .where(DiaEvento.codigo_fotos == codigo.strip().lower())
    ).first()
    if linha is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "QR Code nao encontrado.")
    return linha[0], linha[1]


def _so_coordenacao(ctx, edicao_id: int) -> None:
    if not ctx.e_coordenacao_geral(edicao_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Os visitantes do evento sao da coordenacao geral.",
        )


def _dia_do_painel(db: Session, ctx, dia_id: int) -> tuple[DiaEvento, Edicao]:
    linha = db.execute(
        select(DiaEvento, Edicao)
        .join(Edicao, Edicao.id == DiaEvento.edicao_id)
        .where(DiaEvento.id == dia_id)
    ).first()
    if linha is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dia nao encontrado.")
    _so_coordenacao(ctx, linha[1].id)
    return linha[0], linha[1]


# ------------------------------------------------------------------ publico
@router.get("/publico/{codigo}", response_model=DiaPublico)
def dia_publico(codigo: str, db: BD):
    """O que a pagina do QR Code precisa saber antes de a pessoa preencher.

    Sem sessao. Nao diz quantos visitantes ha, nem o link das fotos.
    """
    dia, edicao = _dia_por_codigo(db, codigo)
    return DiaPublico(edicao=edicao.nome, dia=NOMES_DIAS[dia.data.weekday()])


@router.post("/publico/{codigo}", response_model=FotosLiberadas)
def cadastrar(codigo: str, dados: CadastroVisitante, db: BD):
    """Grava o visitante e devolve o link das fotos do dia (ou nulo, se a
    galeria ainda nao estiver pronta).

    Sem sessao. O mesmo celular no mesmo dia atualiza o nome, sem duplicar.
    """
    dia, edicao = _dia_por_codigo(db, codigo)
    db.execute(
        insert(Visitante)
        .values(
            edicao_id=edicao.id,
            dia_evento_id=dia.id,
            nome=dados.nome,
            celular=dados.celular,
        )
        .on_conflict_do_update(
            constraint="uq_visitantes_dia_celular",
            set_={"nome": dados.nome},
        )
    )
    db.commit()
    return FotosLiberadas(link_fotos=dia.link_fotos)


# ------------------------------------------------------------------ painel
@router.get("", response_model=Visitantes)
def listar(edicao_id: int, db: BD, ctx: Contexto):
    """Os dias da edicao, com o QR Code de cada um, e a lista de visitantes.

    Abrir a tela cria o codigo do QR dos dias que ainda nao tem — e ali que a
    coordenacao vai busca-lo para mandar a grafica.
    """
    _so_coordenacao(ctx, edicao_id)
    edicao = db.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")

    dias = db.scalars(
        select(DiaEvento).where(DiaEvento.edicao_id == edicao_id).order_by(DiaEvento.data)
    ).all()
    criou = False
    for d in dias:
        if not d.codigo_fotos:
            _garantir_codigo(db, d, edicao.ano)
            criou = True
    if criou:
        db.commit()

    totais = dict(
        db.execute(
            select(Visitante.dia_evento_id, func.count())
            .where(Visitante.edicao_id == edicao_id)
            .group_by(Visitante.dia_evento_id)
        ).all()
    )
    visitantes = db.scalars(
        select(Visitante)
        .where(Visitante.edicao_id == edicao_id)
        .order_by(Visitante.criado_em.desc(), Visitante.id.desc())
    ).all()

    return Visitantes(
        dias=[
            DiaVisitantes(
                id=d.id,
                data=d.data,
                descricao=d.descricao,
                codigo_fotos=d.codigo_fotos,
                endereco_qr=_endereco_qr(d.codigo_fotos),
                link_fotos=d.link_fotos,
                total=totais.get(d.id, 0),
            )
            for d in dias
        ],
        visitantes=[
            VisitanteOut(
                id=v.id,
                nome=v.nome,
                celular=_celular_formatado(v.celular),
                dia_evento_id=v.dia_evento_id,
                criado_em=v.criado_em.astimezone(FUSO).strftime("%d/%m %H:%M"),
            )
            for v in visitantes
        ],
    )


@router.put("/dias/{dia_id}/link", response_model=DiaVisitantes)
def salvar_link(dia_id: int, dados: LinkFotos, db: BD, ctx: Contexto):
    """O link da galeria de fotos do dia. Vazio = fotos ainda nao prontas."""
    dia, edicao = _dia_do_painel(db, ctx, dia_id)
    dia.link_fotos = dados.link_fotos
    _garantir_codigo(db, dia, edicao.ano)
    registrar(
        db,
        "alterar_link_fotos",
        usuario_id=ctx.usuario.id,
        tabela="dias_evento",
        registro_id=dia.id,
        detalhes={"link_fotos": dados.link_fotos},
    )
    db.commit()
    total = db.scalar(select(func.count()).where(Visitante.dia_evento_id == dia.id)) or 0
    return DiaVisitantes(
        id=dia.id,
        data=dia.data,
        descricao=dia.descricao,
        codigo_fotos=dia.codigo_fotos,
        endereco_qr=_endereco_qr(dia.codigo_fotos),
        link_fotos=dia.link_fotos,
        total=total,
    )


@router.get("/dias/{dia_id}/qrcode")
def baixar_qrcode(
    dia_id: int,
    db: BD,
    ctx: Contexto,
    formato: Annotated[str, Query(pattern="^(png|svg)$")] = "png",
):
    """O QR Code da pulseira do dia. PNG grande para conferir; SVG para a
    grafica, que aumenta sem perder nitidez."""
    dia, edicao = _dia_do_painel(db, ctx, dia_id)
    codigo = _garantir_codigo(db, dia, edicao.ano)
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
    nome = f"QR_PULSEIRA_{codigo.upper()}.{formato}"
    return Response(
        content=buffer.getvalue(),
        media_type=tipo,
        headers={"Content-Disposition": f'inline; filename="{nome}"'},
    )


@router.get("/planilha")
def baixar_planilha(edicao_id: int, db: BD, ctx: Contexto):
    """A planilha (.xlsx) dos visitantes da edicao, com uma aba por dia."""
    _so_coordenacao(ctx, edicao_id)
    edicao = db.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edicao nao encontrada.")
    dias = db.scalars(
        select(DiaEvento).where(DiaEvento.edicao_id == edicao_id).order_by(DiaEvento.data)
    ).all()

    livro = Workbook()
    livro.remove(livro.active)
    for d in dias:
        aba = livro.create_sheet(f"{NOMES_DIAS[d.data.weekday()].capitalize()} {d.data:%d-%m}")
        aba.append(["Nome", "Celular", "Cadastro"])
        for c in aba[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="153377")
        for v in db.scalars(
            select(Visitante).where(Visitante.dia_evento_id == d.id).order_by(Visitante.criado_em)
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
    if not dias:
        livro.create_sheet("Visitantes").append(["Nome", "Celular", "Cadastro"])

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
