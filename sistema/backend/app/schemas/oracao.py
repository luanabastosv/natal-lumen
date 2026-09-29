"""O convite de oracao do dia."""

from pydantic import BaseModel


class ConviteDoDia(BaseModel):
    """A crianca de hoje, ou o campo vazio quando nao ha nenhuma.

    `crianca` nulo nao e erro: e a edicao que ainda nao recebeu lista, ou o
    comissario que ainda nao tem crianca atribuida. O frontend simplesmente
    nao abre o convite — um convite a rezar sem nome por quem rezar nao tem
    o que dizer.
    """

    crianca: str | None = None
    instituicao: str | None = None
