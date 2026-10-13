"""A programacao do dia do evento: o quadro de horarios de uma edicao."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

HORA = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
COR = r"^#[0-9a-fA-F]{6}$"
NUCLEOS = ("A", "B", "C", "D")


class Atividade(BaseModel):
    """Uma atividade do evento e a cor com que ela aparece no quadro."""

    nome: str = Field(min_length=1, max_length=60)
    cor: str = Field(pattern=COR)


class Horario(BaseModel):
    """Um horario do quadro.

    `todos`: todos os nucleos juntos, na mesma atividade (a abertura, o
    magico, a peca). `por_nucleo`: cada nucleo numa atividade — o rodizio.
    """

    inicio: str = Field(pattern=HORA)
    fim: str = Field(pattern=HORA)
    modo: Literal["todos", "por_nucleo"]
    atividade: str | None = Field(default=None, max_length=80)
    nucleos: dict[str, str | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _confere(self):
        if self.fim <= self.inicio:
            raise ValueError(f"O horario {self.inicio}-{self.fim} termina antes de comecar.")
        if any(n not in NUCLEOS for n in self.nucleos):
            raise ValueError("Os nucleos sao A, B, C e D.")
        return self


class Bloco(BaseModel):
    """Uma parte do dia: Abertura, Rodizios - Manha, Rodizios - Tarde."""

    titulo: str = Field(min_length=1, max_length=60)
    horarios: list[Horario] = Field(default_factory=list, max_length=30)


class ProgramacaoIn(BaseModel):
    atividades: list[Atividade] = Field(default_factory=list, max_length=40)
    blocos: list[Bloco] = Field(default_factory=list, max_length=10)


class ProgramacaoSalvar(ProgramacaoIn):
    # O `atualizado_em` que a tela leu ao abrir a edicao. Se o salvo mudou
    # desde entao, outra pessoa salvou no meio do caminho, e gravar o quadro
    # inteiro por cima apagaria o que ela fez.
    versao_lida: datetime | None = None


class InstituicaoNoNucleo(BaseModel):
    nome: str
    sigla: str | None
    nucleo: str | None
    cor_bata_nome: str | None
    cor_bata_hex: str | None


class NucleosDoDia(BaseModel):
    """Quem esta em cada nucleo num dia do evento. O quadro e o mesmo nos dois
    dias; os nucleos nao — por isso a folha impressa sai uma por dia."""

    dia_evento_id: int
    data: date
    descricao: str | None
    instituicoes: list[InstituicaoNoNucleo]


class ProgramacaoOut(ProgramacaoIn):
    # Nulo quando a edicao ainda nao tem programacao: a tela oferece o modelo.
    existe: bool
    atualizado_em: datetime | None = None
    atualizado_por: str | None = None
    # Liberada para toda a equipe. `pode_editar` diz a tela se mostra os
    # botoes da coordenacao (editar, concluir).
    concluida_em: datetime | None = None
    concluida_por: str | None = None
    pode_editar: bool = False
    # So leitura: vem da organizacao dos nucleos da monitoria, nao do quadro.
    nucleos: list[NucleosDoDia] = Field(default_factory=list)


class ConclusaoIn(BaseModel):
    concluida: bool
