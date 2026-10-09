"""Entrada e saida das autorizacoes dos responsaveis."""

from datetime import datetime

from pydantic import BaseModel, model_validator

# As tres perguntas da autorizacao: o sim/nao e o campo do "qual".
PERGUNTAS = (
    ("necessidade_especial", "necessidade_especial_qual", "a necessidade especial"),
    ("restricao_alimentar", "restricao_alimentar_qual", "a alergia ou restricao alimentar"),
    ("tem_observacao", "observacao", "a observacao"),
)


class RespostasAutorizacao(BaseModel):
    """O que o monitor marca ao conferir a foto de uma autorizacao.

    As tres perguntas sao obrigatorias, e o "qual" tambem quando a resposta e
    sim: "tem alergia" sem dizer a que nao serve a quem monta o lanche.
    Quando e nao, o "qual" e descartado — um texto esquecido no campo antes de
    a pessoa mudar de ideia nao pode ficar gravado como se valesse.
    """

    necessidade_especial: bool
    necessidade_especial_qual: str | None = None
    restricao_alimentar: bool
    restricao_alimentar_qual: str | None = None
    tem_observacao: bool
    observacao: str | None = None

    @model_validator(mode="after")
    def _qual_quando_sim(self):
        for sim, qual, nome in PERGUNTAS:
            texto = (getattr(self, qual) or "").strip()
            if getattr(self, sim) and not texto:
                raise ValueError(f"Diga qual e {nome}.")
            setattr(self, qual, texto if getattr(self, sim) else None)
        return self


class AutorizacaoOut(BaseModel):
    id: int
    crianca_id: int
    crianca_codigo: str
    crianca_nome: str
    # Preenchido = a crianca desistiu de ir. A tela poe a etiqueta de
    # desistente em todo lugar onde ela aparece.
    crianca_desistiu_em: datetime | None = None
    instituicao: str
    criado_em: datetime
    # O caminho da imagem no disco. A tela o usa como "versao" na URL da
    # imagem: ele muda quando a imagem e trocada, e o navegador deixa de
    # mostrar a antiga guardada no cache.
    arquivo: str | None = None

    # Nulos so nas que subiram antes de o formulario existir.
    necessidade_especial: bool | None = None
    necessidade_especial_qual: str | None = None
    restricao_alimentar: bool | None = None
    restricao_alimentar_qual: str | None = None
    tem_observacao: bool | None = None
    observacao: str | None = None
