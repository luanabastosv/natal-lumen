"""Entrada e saida do financeiro da edicao: saidas e recebimentos.

As saidas continuam com nome de `Compra` do lado da base (ver
models/financeiro.py); o que a tela chama de "saida" e exatamente isto.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.tipos import CategoriaRecebimento


# ------------------------------------------------------------------- saidas

class CompraIn(BaseModel):
    edicao_id: int
    descricao: str = Field(min_length=2, max_length=255)
    categoria: str | None = Field(default=None, max_length=80)
    quantidade: int = Field(default=1, gt=0)
    valor_total: Decimal = Field(ge=0, decimal_places=2)
    fornecedor: str | None = Field(default=None, max_length=180)
    data: date


class CompraEditar(BaseModel):
    descricao: str | None = Field(default=None, min_length=2, max_length=255)
    categoria: str | None = Field(default=None, max_length=80)
    quantidade: int | None = Field(default=None, gt=0)
    valor_total: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    fornecedor: str | None = Field(default=None, max_length=180)
    data: date | None = None


class CompraOut(BaseModel):
    id: int
    edicao_id: int
    descricao: str
    categoria: str | None
    quantidade: int
    valor_total: Decimal
    fornecedor: str | None
    data: date
    responsavel: str | None


class PaginaCompras(BaseModel):
    total: int
    itens: list[CompraOut]
    total_gasto: Decimal
    # Gasto por categoria, para o relatorio da edicao.
    por_categoria: dict[str, Decimal]


# -------------------------------------------------------------- recebimentos

class RecebimentoIn(BaseModel):
    edicao_id: int
    # So "outros" pede descricao: a doacao ja se explica pela categoria, e o
    # formulario nem mostra o campo para ela. Sem texto, a doacao grava
    # "Doacao" — a coluna e obrigatoria, e e dela que o log e o nome do
    # comprovante no Drive tiram o titulo quando nao ha doador.
    descricao: str | None = Field(default=None, max_length=255)
    # Conjunto fechado. Apadrinhamento NAO entra: aquele dinheiro e um
    # pagamento de padrinho, registrado em /pagamentos, e a categoria dele e
    # derivada do que ele quita.
    categoria: CategoriaRecebimento
    valor: Decimal = Field(gt=0, decimal_places=2)
    data: date
    doador: str | None = Field(default=None, max_length=180)
    forma: str | None = Field(default=None, max_length=40)
    observacoes: str | None = None

    @model_validator(mode="after")
    def _descricao_de_outros(self):
        texto = (self.descricao or "").strip()
        if len(texto) >= 2:
            self.descricao = texto
        elif self.categoria == CategoriaRecebimento.OUTROS:
            raise ValueError("Diga o que foi este recebimento.")
        else:
            self.descricao = "Doação"
        return self


class RecebimentoEditar(BaseModel):
    descricao: str | None = Field(default=None, min_length=2, max_length=255)
    categoria: CategoriaRecebimento | None = None
    valor: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    data: date | None = None
    doador: str | None = Field(default=None, max_length=180)
    forma: str | None = Field(default=None, max_length=40)
    observacoes: str | None = None
    conferido: bool | None = None


class RecebimentoOut(BaseModel):
    """O registro de `recebimentos`, como ele foi gravado."""

    id: int
    edicao_id: int
    descricao: str
    categoria: str
    valor: Decimal
    data: date
    doador: str | None
    forma: str | None
    observacoes: str | None
    conferido: bool
    comprovante_arquivo: str | None
    # Vazio = nao foi para o Drive (desligado, ou o envio falhou).
    comprovante_drive_link: str | None = None
    responsavel: str | None


class LinhaRecebimento(BaseModel):
    """Uma linha do que entrou na edicao, venha de onde vier.

    A tela do financeiro mostra as duas origens na MESMA lista, porque quem
    fecha o caixa quer ver todo o dinheiro que entrou, de uma vez. `fonte` diz
    de qual tabela a linha veio — e, com isso, em qual rota as acoes dela
    batem: conferir, subir comprovante e remover mudam de endereco, nao de
    significado.
    """

    fonte: str
    id: int
    categoria: str
    descricao: str
    # O padrinho que pagou, ou quem doou.
    quem: str | None
    valor: Decimal
    data: date
    forma: str | None
    observacoes: str | None
    conferido: bool
    tem_comprovante: bool
    comprovante_drive_link: str | None
    # Pagamento que nao quita apadrinhamento nenhum (o apadrinhamento foi
    # desfeito e o dinheiro ficou). A categoria dele cai no "apadrinhamento"
    # sem tipo, igual a cesta e festa juntas; isto e o que separa os dois.
    sem_destino: bool = False
    responsavel: str | None


class PaginaRecebimentos(BaseModel):
    """O que entrou na edicao: os totais inteiros, e a lista filtrada.

    Os totais sao SEMPRE da edicao inteira, mesmo com filtro na lista: eles
    respondem "qual e o caixa", e um caixa que muda quando se filtra a tela nao
    e caixa nenhum. `total` diz quantas linhas existem e `itens` traz as que o
    filtro deixou passar, ate o teto pedido — a tela avisa quando sobrou coisa
    de fora.
    """

    total: int
    itens: list[LinhaRecebimento]

    total_recebido: Decimal
    por_categoria: dict[str, Decimal]

    # Quanto do total veio do apadrinhamento, e em quantos pagamentos.
    apadrinhamento: Decimal
    pagamentos: int

    # Os dois numeros que pedem acao, e nao so somam.
    a_conferir: Decimal
    sem_comprovante: int
