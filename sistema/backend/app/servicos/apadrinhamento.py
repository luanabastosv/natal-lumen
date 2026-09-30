"""O que faz um apadrinhamento valer.

Regra da campanha, decidida em 30/09/2026: **promessa nao e apadrinhamento.**
Enquanto nao ha dinheiro registrado, a ligacao entre a crianca e o padrinho
existe e SEGURA a crianca — ninguem mais pode apadrinha-la naquele tipo — mas
ela nao conta como apadrinhada em lugar nenhum: nem no painel, nem na lista de
criancas, nem para mandar o cartao de agradecimento.

Por que a promessa continua existindo, em vez de so se poder criar o
apadrinhamento junto com o pagamento: nem sempre as duas coisas acontecem no
mesmo momento — o padrinho assume a crianca e paga depois. O comissario promete
quando fecha com o doador, e confirma quando o dinheiro entra.

Quem confirma e o proprio comissario: ele tem `registrar_pagamentos_padrinho`,
que alcanca os pagamentos dos padrinhos que ele ja alcanca. O que continua com a
coordenacao e a aba Recebimentos do financeiro (`registrar_pagamentos`), mais
CONFERIR e APAGAR pagamento — quem registra o dinheiro nao audita o proprio
registro.

Soltar uma promessa que nunca virou dinheiro e apagar o apadrinhamento — a rota
de apagar recusa os que ja tem pagamento, entao ela so alcanca promessa. Vale
para o comissario dentro do alcance dele e para a coordenacao na cidade toda.

`pago` nao e coluna: um apadrinhamento esta pago quando tem um `Pagamento`
ligado. Estas duas condicoes existem para que essa definicao fique num lugar
so — se um dia ela mudar (uma data de confirmacao, um pagamento parcial), muda
aqui e o painel, as listas e os cartoes acompanham juntos.
"""

from app.models import Apadrinhamento

# Vale como apadrinhamento: tem dinheiro registrado.
CONFIRMADO = Apadrinhamento.pagamento_id.is_not(None)

# Existe e segura a crianca, mas ainda nao conta.
PROMETIDO = Apadrinhamento.pagamento_id.is_(None)


def confirmado(apadrinhamento: Apadrinhamento) -> bool:
    """A mesma pergunta sobre um registro ja carregado."""
    return apadrinhamento.pagamento_id is not None
