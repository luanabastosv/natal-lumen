"""Os cuidados que a autorizacao de uma crianca avisa, numa frase.

Usado pela lista de criancas e pela lista do check-in, que mostram um icone
de atencao na crianca e esta frase na dica. Um lugar so, para as duas telas
dizerem a mesma coisa.
"""

from app.models import Autorizacao


def resumo(a: Autorizacao) -> str | None:
    """"Necessidade especial: cadeirante · Alergia ou restrição: amendoim".

    So o que foi respondido "Sim". Nulo quando nao ha nada a avisar.
    """
    avisos = [
        f"{rotulo}: {qual}"
        for rotulo, sim, qual in (
            ("Necessidade especial", a.necessidade_especial, a.necessidade_especial_qual),
            ("Alergia ou restrição", a.restricao_alimentar, a.restricao_alimentar_qual),
            ("Observação", a.tem_observacao, a.observacao),
        )
        if sim
    ]
    return " · ".join(avisos) or None
