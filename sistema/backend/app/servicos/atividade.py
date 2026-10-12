"""A atividade da equipe, lida do log em frases que a coordenacao entende.

O log (`log_atividades`) foi feito para auditoria: guarda ids e nomes de campo,
nao frases. Aqui ele vira "Apadrinhou Ana Clara (cesta) para Maria Silva" —
com os nomes buscados de uma vez para a pagina inteira, e nao um por linha.

Fica de fora o que nao e trabalho: entrar e sair, busca, senha errada, a copia
do comprovante no Drive (que repete o "subiu comprovante"). Entrar e sair
continuam visiveis, mas como "ultimo acesso", na lista da equipe.
"""

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Crianca, Instituicao, LogAtividade, Padrinho, Pagamento

# O que nao conta como trabalho, nem na contagem nem na linha do tempo.
IGNORADAS = frozenset({
    "login",
    "logout",
    "login_falhou",
    "login_bloqueado",
    "conta_bloqueada",
    "busca_por_codigo",
    "esqueci_senha",
    "definir_senha_token_invalido",
    "reconfirmacao_recusada",
    "comprovante_no_drive",
    "comprovante_drive_falhou",
    "importacao_analisada",
})

TIPO = {"cesta": "cesta", "festa": "festa", "autorizacao": "autorização"}


def _dinheiro(valor) -> str:
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError):
        return ""
    texto = f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _plural(n, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


class _Nomes:
    """Os nomes que as frases de uma pagina precisam, buscados de uma vez."""

    def __init__(self, db: Session, logs: Iterable[LogAtividade]):
        criancas, padrinhos, pagamentos, instituicoes = set(), set(), set(), set()
        for log in logs:
            d = log.detalhes or {}
            if isinstance(d.get("crianca_id"), int):
                criancas.add(d["crianca_id"])
            if isinstance(d.get("crianca"), int):
                criancas.add(d["crianca"])
            if isinstance(d.get("padrinho_id"), int):
                padrinhos.add(d["padrinho_id"])
            if isinstance(d.get("instituicao_id"), int):
                instituicoes.add(d["instituicao_id"])
            if log.registro_id is not None:
                {"criancas": criancas, "padrinhos": padrinhos, "pagamentos": pagamentos,
                 "instituicoes": instituicoes}.get(log.tabela, set()).add(log.registro_id)

        self.pagamento_padrinho = dict(
            db.execute(select(Pagamento.id, Pagamento.padrinho_id).where(Pagamento.id.in_(pagamentos))).all()
        ) if pagamentos else {}
        padrinhos |= set(self.pagamento_padrinho.values())

        self.criancas = {
            i: f"{n} ({c})" if c else n
            for i, n, c in db.execute(
                select(Crianca.id, Crianca.nome, Crianca.codigo).where(Crianca.id.in_(criancas))
            ).all()
        } if criancas else {}
        self.padrinhos = dict(
            db.execute(select(Padrinho.id, Padrinho.nome).where(Padrinho.id.in_(padrinhos))).all()
        ) if padrinhos else {}
        self.instituicoes = dict(
            db.execute(select(Instituicao.id, Instituicao.nome).where(Instituicao.id.in_(instituicoes))).all()
        ) if instituicoes else {}

    def crianca(self, i) -> str:
        return self.criancas.get(i, "uma criança que já foi apagada")

    def padrinho(self, i) -> str:
        return self.padrinhos.get(i, "um padrinho que já foi apagado")

    def o_padrinho(self, i) -> str:
        """"o padrinho Fulano", ou "um padrinho que já foi apagado"."""
        nome = self.padrinhos.get(i)
        return f"o padrinho {nome}" if nome else "um padrinho que já foi apagado"

    def instituicao(self, i) -> str:
        return self.instituicoes.get(i, "uma instituição")


def _campos(d: dict) -> str:
    """'idade e nome' a partir de {'campos': [...]} — o que foi mexido."""
    nomes = {
        "comissario_id": "responsável", "dia_evento_id": "dia do evento",
        "interesse_mensal": "interesse mensal", "membro_ser_feliz": "membro Ser Feliz",
        "observacoes": "observações", "instituicoes": "instituições",
        "valor_total": "valor", "vai_ao_evento": "vai ao evento",
        "endereco": "endereço", "responsavel": "responsável", "whatsapp": "WhatsApp",
        "email": "e-mail", "descricao": "descrição", "observacao": "observação",
    }
    campos = [nomes.get(c, c.replace("_", " ")) for c in (d.get("campos") or [])]
    if not campos:
        return ""
    if len(campos) == 1:
        return f" ({campos[0]})"
    return f" ({', '.join(campos[:-1])} e {campos[-1]})"


def _data(texto) -> str:
    """2026-12-06 -> 06/12/2026."""
    partes = str(texto or "").split("-")
    return "/".join(reversed(partes)) if len(partes) == 3 else str(texto or "")


def descrever(log: LogAtividade, nomes: _Nomes) -> str:
    d = log.detalhes or {}
    a = log.acao
    rid = log.registro_id
    crianca = nomes.crianca(d.get("crianca_id") or d.get("crianca") or (rid if log.tabela == "criancas" else None))
    tipo = TIPO.get(d.get("tipo"), d.get("tipo") or "")

    match a:
        case "padrinho_criado":
            return f"Cadastrou o padrinho {d.get('nome') or nomes.padrinho(rid)}"
        case "padrinho_editado":
            return f"Editou {nomes.o_padrinho(rid)}{_campos(d)}"
        case "padrinho_apagado":
            return f"Apagou o padrinho {d.get('nome', '')}".rstrip()
        case "apadrinhamento_criado":
            return f"Apadrinhou a {tipo} de {crianca} para {nomes.padrinho(d.get('padrinho_id'))}"
        case "apadrinhamento_editado":
            return f"Editou o apadrinhamento de {crianca}{_campos(d)}"
        case "apadrinhamento_apagado":
            return f"Desfez o apadrinhamento de {tipo} de {crianca}"
        case "pagamento_registrado":
            return (f"Registrou pagamento de {_dinheiro(d.get('valor'))} de "
                    f"{nomes.padrinho(d.get('padrinho_id'))}")
        case "pagamento_editado":
            if d.get("campos") == ["conferido"]:
                return f"Conferiu o pagamento de {nomes.padrinho(nomes.pagamento_padrinho.get(rid))}"
            return f"Editou o pagamento de {nomes.padrinho(nomes.pagamento_padrinho.get(rid))}{_campos(d)}"
        case "pagamento_apagado":
            return f"Desfez um pagamento de {_dinheiro(d.get('valor'))}"
        case "comprovante_subido":
            if log.tabela == "pagamentos":
                return f"Subiu o comprovante de {nomes.padrinho(nomes.pagamento_padrinho.get(rid))}"
            return "Subiu o comprovante de um recebimento"
        case "cartao_enviado":
            return "Enviou um agradecimento pelo WhatsApp"
        case "cartao_envio_falhou":
            return "Tentou enviar um agradecimento pelo WhatsApp (falhou)"
        case "cartoes_enviados":
            return f"Marcou {_plural(len(d.get('cartoes') or []), 'cartão', 'cartões')} como enviado(s)"
        case "cartoes_em_lote":
            n = d.get("gravados", 0)
            if d.get("tipo") == "autorizacao":
                return f"Subiu {_plural(n, 'autorização', 'autorizações')}"
            return f"Subiu {_plural(n, 'cartão', 'cartões')} de {tipo}"
        case "cartao_trocado":
            return f"Trocou a imagem do cartão de {tipo} de {crianca}"
        case "cartao_apagado":
            return f"Apagou o cartão de {tipo} de {crianca}"
        case "autorizacao_trocada":
            return f"Trocou a imagem da autorização de {crianca}"
        case "autorizacao_apagada":
            return f"Apagou a autorização de {crianca}"
        case "crianca_criada":
            return f"Cadastrou a criança {crianca}"
        case "crianca_editada":
            return f"Editou {crianca}{_campos(d)}"
        case "crianca_apagada":
            return f"Apagou a criança {d.get('nome', '')} ({d.get('codigo', '')})"
        case "crianca_desistiu":
            return f"Marcou a desistência de {crianca}"
        case "crianca_voltou":
            return f"Desfez a desistência de {crianca}"
        case "crianca_observacao_comissario":
            return f"Escreveu uma observação sobre {crianca}"
        case "criancas_em_lote":
            return f"Editou {_plural(d.get('quantas', 0), 'criança', 'crianças')} de uma vez{_campos(d)}"
        case "criancas_renumeradas":
            return f"Renumerou {_plural(d.get('quantas', 0), 'criança', 'crianças')} ({d.get('sigla', '')})"
        case "criancas_nova_sigla":
            return f"Trocou a sigla de {d.get('de')} para {d.get('para')} ({_plural(d.get('quantas', 0), 'criança', 'crianças')})"
        case "importacao_confirmada":
            return f"Importou {_plural(d.get('importadas', 0), 'criança', 'crianças')} de uma planilha"
        case "checkin":
            return f"Fez o check-in de {crianca}"
        case "checkin_falta":
            return f"Marcou a falta de {crianca}"
        case "checkin_desfeito":
            return f"Desfez o check-in de {crianca}"
        case "kits_atualizados":
            n = len(d.get("criancas") or [])
            estado = "montado(s)" if d.get("status") == "montado" else "a montar"
            return f"Marcou {_plural(n, 'kit', 'kits')} como {estado}"
        case "kit_conferido":
            return f"Conferiu o kit de {crianca}"
        case "kits_conferidos":
            return f"Conferiu {_plural(len(d.get('criancas') or []), 'kit', 'kits')}"
        case "kits_montagem":
            return f"Registrou montagem e conferência dos kits de {nomes.instituicao(d.get('instituicao_id'))}"
        case "compra_registrada":
            return f"Registrou a saída \"{d.get('descricao', '')}\" de {_dinheiro(d.get('valor_total'))}"
        case "compra_editada":
            return f"Editou uma saída{_campos(d)}"
        case "compra_apagada":
            return f"Apagou a saída \"{d.get('descricao', '')}\""
        case "recebimento_registrado":
            return f"Registrou a entrada \"{d.get('descricao', '')}\" de {_dinheiro(d.get('valor'))}"
        case "recebimento_editado":
            return f"Editou uma entrada{_campos(d)}"
        case "recebimento_apagado":
            return f"Apagou a entrada \"{d.get('descricao', '')}\""
        case "instituicao_criada":
            return f"Cadastrou a instituição {d.get('nome', '')}"
        case "instituicao_editada":
            return f"Editou a instituição {nomes.instituicao(rid)}{_campos(d)}"
        case "instituicao_apagada":
            return f"Apagou a instituição {d.get('nome', '')}"
        case "dia_da_instituicao":
            return f"Definiu o dia do evento de {nomes.instituicao(d.get('instituicao_id'))}"
        case "dia_criado":
            return f"Criou o dia do evento {_data(d.get('data'))}"
        case "dia_apagado":
            return f"Apagou o dia do evento {_data(d.get('data'))}"
        case "usuario_criado":
            return f"Cadastrou o usuário {d.get('email', '')}"
        case "usuario_editado":
            return f"Editou um usuário{_campos(d)}"
        case "usuario_apagado":
            return f"Apagou o usuário {d.get('nome', '')}"
        case "vinculo_criado" | "vinculo_editado":
            return f"Mudou o perfil ou o alcance de um usuário{_campos(d)}"
        case "link_de_acesso_gerado":
            return "Gerou um link de acesso para um usuário"
        case "senha_definida":
            return "Criou a própria senha"
        case "edicao_criada" | "edicao_editada" | "edicao_apagada":
            verbo = {"edicao_criada": "Criou", "edicao_editada": "Editou", "edicao_apagada": "Apagou"}[a]
            return f"{verbo} a edição {d.get('nome', '')}".rstrip()
        case "cidade_criada" | "cidade_editada" | "cidade_apagada":
            verbo = {"cidade_criada": "Criou", "cidade_editada": "Editou", "cidade_apagada": "Apagou"}[a]
            return f"{verbo} a cidade {d.get('nome', '')}".rstrip()
        case "programacao_salva":
            return "Atualizou a programação do evento"
        case "nucleos_organizados":
            n = len(d.get("mudancas") or [])
            return f"Organizou os núcleos e as batas ({_plural(n, 'instituição alterada', 'instituições alteradas')})"
        case "operacao_da_edicao_limpa":
            return "Apagou os lançamentos de teste da edição"
        case "admin_criado":
            return "Criou a conta da administração geral"
        case _:
            return a.replace("_", " ").capitalize()


def descrever_varios(db: Session, logs: list[LogAtividade]) -> list[str]:
    nomes = _Nomes(db, logs)
    return [descrever(log, nomes) for log in logs]
