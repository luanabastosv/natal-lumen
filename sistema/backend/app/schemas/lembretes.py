"""Saida da tela de envio de cartoes: o lembrete do evento, por dia."""

from datetime import date

from pydantic import BaseModel


class CartaoDoLembrete(BaseModel):
    """Uma crianca apadrinhada, e o cartao que ela escreveu para ESTE padrinho.

    Uma linha por apadrinhamento, e nao por crianca: quem deu cesta e festa da
    mesma crianca recebe os dois cartoes, porque ela escreve um para cada.
    """

    apadrinhamento_id: int
    crianca_id: int
    crianca_codigo: str
    crianca_nome: str
    instituicao_id: int
    instituicao: str
    tipo: str
    # Nulo = o cartao ainda nao subiu. E o que deixa o padrinho em progresso.
    cartao_id: int | None = None


class LembretePadrinho(BaseModel):
    """O lembrete de UM padrinho para UM dia do evento."""

    padrinho_id: int
    padrinho_nome: str
    whatsapp: str | None = None
    # O numero cadastrado tem cara de telefone. Sem isto o lembrete nao tem
    # para onde ir, mesmo com todos os cartoes na mao.
    whatsapp_valido: bool
    cartoes: list[CartaoDoLembrete]
    faltam: int
    # pronto        todos os cartoes subiram e ha WhatsApp: pode sair
    # sem_whatsapp  os cartoes estao todos aqui, falta o numero
    # em_progresso  ainda falta cartao subir
    situacao: str
    # Em quantos OUTROS dias este padrinho tambem tem lembrete. E o que a tela
    # usa para avisar que ele vai receber mais de uma mensagem.
    outros_dias: int = 0


class DiaLembretes(BaseModel):
    # Nulos no grupo das criancas cuja instituicao ainda nao tem dia: o
    # lembrete delas nao tem o que dizer, e nao sai ate o dia ser definido.
    dia_id: int | None = None
    data: date | None = None
    descricao: str | None = None
    padrinhos: list[LembretePadrinho]
