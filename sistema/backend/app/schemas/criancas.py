"""Entrada e saida de criancas e da importacao de listas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CriancaIn(BaseModel):
    edicao_id: int
    instituicao_id: int
    codigo: str = Field(min_length=1, max_length=40)
    nome: str = Field(min_length=3, max_length=180)
    idade: int = Field(ge=0, le=21)
    sexo: str = Field(pattern="^[MF]$")
    observacoes: str | None = None
    # Sem dia aqui: ele vem da instituicao (ver InstituicaoDia).


class CriancaEditar(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=40)
    nome: str | None = Field(default=None, min_length=3, max_length=180)
    idade: int | None = Field(default=None, ge=0, le=21)
    sexo: str | None = Field(default=None, pattern="^[MF]$")
    observacoes: str | None = None
    # Comissario responsavel. Mandar null limpa o responsavel; nao mandar o
    # campo nao o toca — a diferenca sai de model_fields_set, no router.
    comissario_id: int | None = None
    # Sem dia aqui de proposito: mudar o dia de UMA crianca deixaria duas da
    # mesma escola em dias diferentes. O dia se muda na instituicao.


class CriancaOut(BaseModel):
    id: int
    edicao_id: int
    instituicao_id: int
    instituicao: str
    codigo: str
    nome: str
    idade: int
    sexo: str
    dia_evento_id: int | None
    dia_evento: date | None
    # Como o dia e chamado nesta edicao ("Sabado"); e o que as telas
    # mostram no lugar da data, que so aparece quando nao ha descricao.
    dia_evento_descricao: str | None = None
    observacoes: str | None
    checkin_em: datetime | None
    # Preenchido = desistiu de ir. Aparece riscada na planilha, mas continua nela.
    desistiu_em: datetime | None = None

    # Daqui para baixo, `None` quer dizer "nao e para voce": quem olha nao tem
    # a permissao que revela aquele campo, e o servidor nem chega a manda-lo.
    # Nao e a tela que esconde — ela so deixa de desenhar a coluna. Ver `_saida`
    # em routers/criancas.py, que e onde a decisao acontece.
    #
    # Quem responde por esta crianca. Nulo tambem quando ninguem do time pegou,
    # e os dois casos coincidem de proposito: nos dois a tela escreve a mesma
    # coisa, e nenhuma delas e informacao sobre a crianca.
    comissario_id: int | None = None
    comissario: str | None = None
    # O grupo dele na comunidade, do vinculo com ESTA edicao. Nulo quando nao
    # ha responsavel, ou quando ele ainda nao teve grupo nomeado.
    comissario_grupo: str | None = None

    # O panorama da crianca, para a tela ser um painel de controle e nao so
    # uma lista de nomes.
    # Apadrinhamento que VALE: tem pagamento registrado. Nulo = sem
    # `ver_padrinhos`.
    tem_padrinho_cesta: bool | None = None
    tem_padrinho_festa: bool | None = None
    # Prometido e ainda nao pago. Segura o lugar da crianca naquele tipo, mas
    # nao conta como apadrinhamento — ver servicos/apadrinhamento.py.
    promessa_cesta: bool | None = None
    promessa_festa: bool | None = None
    # Quanto custa apadrinhar esta crianca em cada tipo: o preco e da edicao
    # DELA, e o apadrinhar por codigo alcanca criancas de outra cidade. Nulo =
    # sem `ver_padrinhos`.
    valor_cesta: Decimal | None = None
    valor_festa: Decimal | None = None
    # Quantos cartoes ja foram digitalizados. Este fica de pe para todo mundo
    # que ve a crianca: e o andamento do trabalho da monitoria, e nao diz nada
    # sobre doador nenhum.
    cartoes: int = 0
    # A autorizacao do responsavel ja subiu. Como os cartoes, vale para todo
    # mundo que ve a crianca.
    autorizacao: bool = False
    # Nulo = sem `gerenciar_kits`.
    kit_status: str | None = None


class PaginaCriancas(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    itens: list[CriancaOut]
    # Quantas criancas ja fizeram check-in, no filtro inteiro e nao so nesta
    # pagina: a planilha so mostra a coluna de check-in quando ha o que
    # mostrar, e ela nao pode aparecer e sumir conforme a pessoa pagina.
    com_checkin: int = 0


class LinhaImportada(BaseModel):
    linha: int
    codigo: str
    nome: str
    idade: int | None
    sexo: str | None
    instituicao_id: int | None
    instituicao: str | None
    observacoes: str | None
    erros: list[str]
    avisos: list[str]
    valida: bool


class PreviaImportacao(BaseModel):
    id: str
    total: int
    validas: int
    com_erro: int
    com_aviso: int
    colunas_reconhecidas: dict[str, str]
    colunas_ignoradas: list[str]
    linhas: list[LinhaImportada]


class ResultadoImportacao(BaseModel):
    importadas: int
    ignoradas: int


class CriancasEmLote(BaseModel):
    """Mudanca aplicada a varias criancas de uma vez.

    O dia nao entra aqui: ele e da instituicao, e se muda em
    PUT /edicoes/{id}/instituicoes/{id}/dia.
    """

    criancas: list[int] = Field(min_length=1)
    instituicao_id: int | None = None
    # Comissario responsavel. Como em CriancaEditar, null limpa e ausente nao
    # toca: distribuir 200 criancas entre 3 comissarios uma a uma nao e
    # trabalho que alguem faca.
    comissario_id: int | None = None


class ResumoInstituicao(BaseModel):
    """Uma aba da tela de criancas."""

    instituicao_id: int
    instituicao: str
    criancas: int
    # Nulos pelo mesmo motivo do CriancaOut: quem nao tem `ver_padrinhos` nao
    # recebe nem a conta. Somar o que nao se pode ver crianca a crianca ainda
    # e ver — "3 sem padrinho" numa instituicao de 4 diz quem sao.
    sem_padrinho: int | None = None
    sem_cartao: int
    sem_comissario: int | None = None
    # O dia marcado para esta instituicao nesta edicao.
    dia_evento_id: int | None = None
    dia_evento: date | None = None
    dia_evento_descricao: str | None = None


class DesistenciaIn(BaseModel):
    """Marca ou desmarca que a crianca desistiu de ir ao evento."""

    desistiu: bool


class RenumerarIn(BaseModel):
    """Refaz os codigos de uma instituicao inteira."""

    edicao_id: int
    instituicao_id: int
    # Em branco mantem a sigla atual da instituicao.
    sigla: str | None = Field(default=None, min_length=1, max_length=6)


class PadrinhoDaCrianca(BaseModel):
    """Um padrinho desta crianca, para a ficha."""

    apadrinhamento_id: int
    tipo: str
    valor: Decimal
    pago: bool
    padrinho_id: int
    nome: str
    # So preenchidos para quem tem ver_padrinhos.
    whatsapp: str | None = None
    email: str | None = None


class CartaoDaCrianca(BaseModel):
    id: int
    tipo: str
    status: str
    criado_em: datetime
    enviado_em: datetime | None


class CriancaDetalhe(BaseModel):
    """Ficha da crianca: tudo o que se sabe dela, numa tela so."""

    id: int
    edicao_id: int
    edicao: str
    instituicao_id: int
    instituicao: str
    codigo: str
    nome: str
    idade: int
    sexo: str
    dia_evento: date | None
    dia_evento_descricao: str | None = None
    observacoes: str | None
    checkin_em: datetime | None
    desistiu_em: datetime | None = None

    comissario_id: int | None = None
    comissario: str | None = None
    comissario_grupo: str | None = None

    # Vazia para quem nao tem `ver_padrinhos`: nem os nomes, nem os valores,
    # nem QUANTOS sao. A tela mostra no lugar uma linha dizendo que esta parte
    # nao e daquele perfil.
    padrinhos: list[PadrinhoDaCrianca]
    cartoes: list[CartaoDaCrianca]
    # Nulos para quem nao tem `gerenciar_kits`.
    kit_status: str | None = None
    kit_montado_em: datetime | None = None
    # Quando a autorizacao do responsavel subiu. Nulo = ainda nao subiu.
    autorizacao_em: datetime | None = None
    # O que o monitor marcou ao conferir a autorizacao. Nulos enquanto ela nao
    # subiu, e o "qual" so vem quando a resposta e sim.
    necessidade_especial: bool | None = None
    necessidade_especial_qual: str | None = None
    restricao_alimentar: bool | None = None
    restricao_alimentar_qual: str | None = None
    tem_observacao: bool | None = None
    observacao_autorizacao: str | None = None
    # Quantas vezes ela apareceu no convite de oracao do dia, somando todo
    # mundo. Vai para qualquer perfil que ve a ficha: nao diz nada de doador.
    ave_marias: int = 0

    # A resposta da pergunta que decidiu tudo acima: este usuario tem
    # `ver_padrinhos` nesta edicao? A tela usa a MESMA resposta para esconder a
    # secao de padrinhos e a linha do comissario, em vez de perguntar de novo
    # por conta propria e arriscar divergir do que o servidor mandou.
    ve_captacao: bool


class ComissarioDoTime(BaseModel):
    """Alguem que pode ser posto como responsavel por uma crianca da edicao.

    Quase sempre e um comissario. Coordenacao e administracao geral tambem
    entram — elas fazem o que a equipe faz — e por isso o `papel`: a tela
    precisa dizer quem e quem, senao um nome de coordenacao no meio do time
    pareceria um comissario a mais.
    """

    id: int
    nome: str
    # "Comissario", "Coordenacao" ou "Administracao geral".
    papel: str
    # As instituicoes da edicao que esta pessoa alcanca. A tela usa para montar
    # um so seletor por instituicao sem voltar ao servidor a cada aba. Para
    # coordenacao e administracao geral sao todas as da cidade.
    instituicoes: list[int]
