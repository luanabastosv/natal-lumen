"""Entrada e saida de padrinhos, apadrinhamentos e pagamentos."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class PadrinhoIn(BaseModel):
    edicao_id: int
    nome: str = Field(min_length=3, max_length=180)
    whatsapp: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    observacoes: str | None = None
    # Nulo nao e "nao": e "ninguem perguntou". Ver o modelo.
    membro_ser_feliz: bool | None = None
    interesse_mensal: bool | None = None


class PadrinhoEditar(BaseModel):
    nome: str | None = Field(default=None, min_length=3, max_length=180)
    whatsapp: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    observacoes: str | None = None
    membro_ser_feliz: bool | None = None
    interesse_mensal: bool | None = None


class ApadrinhamentoResumo(BaseModel):
    id: int
    crianca_id: int
    # O primeiro nome e o que vai para o PADRINHO — e o que o cartao de
    # agradecimento usa (ver servicos/agradecimento.py, que le a crianca
    # direto e nao passa por aqui).
    crianca_primeiro_nome: str
    # Codigo e nome completo sao para quem opera o sistema: sem o codigo nao
    # da para casar a linha da ficha com a linha da planilha. Nao alarga
    # acesso nenhum — todo perfil que tem `ver_padrinhos` tambem tem
    # `ver_criancas`, e esta saida so existe atras dessas rotas.
    crianca_codigo: str
    crianca_nome: str
    crianca_idade: int
    # Preenchido = a crianca desistiu de ir. A tela poe a etiqueta de
    # desistente em todo lugar onde ela aparece.
    crianca_desistiu_em: datetime | None = None
    tipo: str
    valor: Decimal
    pago: bool
    vai_ao_evento: bool | None
    # Quem registrou o apadrinhamento. Um padrinho recebe criancas de mais de
    # um comissario, e na ficha dele a etiqueta e o unico jeito de saber quem
    # trouxe qual — e, portanto, quem cobra qual. Vazio quando o comissario foi
    # excluido do sistema depois (a FK e SET NULL).
    comissario_id: int | None = None
    comissario: str | None = None
    # Ultimo envio do cartao pelo WhatsApp: None = nunca tentou.
    cartao_status: str | None = None
    cartao_enviado_em: datetime | None = None


class EnvioCartaoOut(BaseModel):
    """Resultado de uma tentativa de mandar o cartao pelo WhatsApp."""

    apadrinhamento_id: int
    status: str
    telefone: str
    mensagem_id: str | None = None
    erro: str | None = None
    enviado_em: datetime


class PadrinhoOut(BaseModel):
    id: int
    edicao_id: int
    edicao: str
    cidade: str
    ano: int
    nome: str
    whatsapp: str | None
    email: str | None
    observacoes: str | None
    membro_ser_feliz: bool | None
    interesse_mensal: bool | None
    criado_em: datetime
    apadrinhamentos: list[ApadrinhamentoResumo]
    total_combinado: Decimal
    total_pago: Decimal
    # So na resposta do apadrinhar: o pagamento que acabou de nascer, para o
    # comprovante subir para ele em seguida.
    ultimo_pagamento_id: int | None = None


class PaginaPadrinhos(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    itens: list[PadrinhoOut]


class PadrinhoParecido(BaseModel):
    """Um padrinho ja cadastrado com nome parecido com o que se esta digitando."""

    id: int
    nome: str
    whatsapp: str | None
    # Quantas criancas ele ja tem: ajuda a reconhecer se e a mesma pessoa.
    criancas: int


class CriancaApadrinhada(BaseModel):
    crianca_id: int
    tipo: str = Field(pattern="^(cesta|festa)$")


class ApadrinharComPagamento(BaseModel):
    """Apadrinhar e pagar sao um ato so: as criancas escolhidas e o dinheiro
    que as quita entram juntos, ou nada entra. Nao ha mais "reservar" uma
    crianca para pagar depois."""

    criancas: list[CriancaApadrinhada] = Field(min_length=1)
    data: date
    forma: str | None = Field(default=None, max_length=40)
    observacoes: str | None = None


class ApadrinhamentoEditar(BaseModel):
    valor: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    vai_ao_evento: bool | None = None


class PagamentoIn(BaseModel):
    padrinho_id: int
    valor: Decimal = Field(gt=0, decimal_places=2)
    data: date
    forma: str | None = Field(default=None, max_length=40)
    observacoes: str | None = None
    # Apadrinhamentos que este pagamento quita.
    apadrinhamentos: list[int] = Field(default_factory=list)


class PagamentoEditar(BaseModel):
    valor: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    data: date | None = None
    forma: str | None = Field(default=None, max_length=40)
    observacoes: str | None = None
    conferido: bool | None = None
    apadrinhamentos: list[int] | None = None


class PagamentoOut(BaseModel):
    id: int
    padrinho_id: int
    padrinho: str
    valor: Decimal
    data: date
    forma: str | None
    observacoes: str | None
    conferido: bool
    comprovante_arquivo: str | None
    # Vazio = nao foi para o Drive (desligado, ou o envio falhou).
    comprovante_drive_link: str | None = None
    apadrinhamentos: list[int]


class PaginaPagamentos(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    itens: list[PagamentoOut]
