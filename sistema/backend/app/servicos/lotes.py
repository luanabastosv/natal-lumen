"""A planilha de um grupo que apadrinhou junto, e os nomes do ZIP do grupo.

A planilha e a do grupo, e nao a da instituicao: cada linha e uma pessoa, com
nome e telefone. Quem ela apadrinha nao vem da planilha. A administracao
escolhe a instituicao na tela, o sistema sugere uma crianca por linha, e a
pessoa confere e troca o que quiser antes de gravar (routers/lotes.py).

A leitura reaproveita o que o importador de criancas ja resolveu de planilha
real: CSV do Excel brasileiro, Windows-1252, titulo em cima do cabecalho.
"""

import re
from dataclasses import dataclass, field
from io import BytesIO

import pandas as pd

from app.servicos.arquivos import limpar_texto
from app.servicos.importador import SEPARADORES, _chave, _limpar_celula, _linhas_do_csv
from app.servicos.nomes import nome_proprio

# Os cabecalhos que um grupo usa para cada coluna, ja na forma de _chave().
COLUNAS = {
    "nome": (
        "nome", "nome do padrinho", "nome da madrinha", "nome completo",
        "padrinho", "madrinha", "padrinho/madrinha", "padrinhos", "doador",
        "doadora", "participante", "membro", "integrante",
    ),
    "whatsapp": (
        "whatsapp", "whats", "zap", "telefone", "celular", "contato", "fone",
        "tel", "telefone/whatsapp", "numero", "telefone do padrinho",
    ),
}

LINHAS_PARA_PROCURAR_CABECALHO = 10

# Um grupo grande da campanha tem algumas dezenas de pessoas. O teto existe
# para uma planilha errada (a lista de criancas inteira, por exemplo) parar na
# leitura, e nao virar mil padrinhos numa tela.
MAXIMO_DE_LINHAS = 400


@dataclass
class LinhaPadrinho:
    linha: int
    nome: str
    whatsapp: str | None
    erros: list[str] = field(default_factory=list)


def _contem(chave: str, termo: str) -> bool:
    return re.search(rf"(^|\W){re.escape(termo)}($|\W)", chave) is not None


def _mapear(colunas: list[str]) -> dict[str, int]:
    """Qual coluna (pela posicao) e o nome e qual e o telefone.

    Primeiro o cabecalho igual a um aceito; depois o que contem um deles,
    do termo mais longo para o mais curto. O telefone e procurado antes do
    nome no segundo passe: "Nome e telefone do padrinho" nao existe, mas
    "Telefone do padrinho" contem "padrinho".
    """
    chaves = [_chave(c) for c in colunas]
    achadas: dict[str, int] = {}
    for campo, aceitos in COLUNAS.items():
        for i, chave in enumerate(chaves):
            if i not in achadas.values() and chave in aceitos:
                achadas[campo] = i
                break
    for campo in ("whatsapp", "nome"):
        if campo in achadas:
            continue
        for termo in sorted(COLUNAS[campo], key=len, reverse=True):
            i = next(
                (i for i, c in enumerate(chaves) if i not in achadas.values() and _contem(c, termo)),
                None,
            )
            if i is not None:
                achadas[campo] = i
                break
    return achadas


def _ler_csv(conteudo: bytes):
    """O CSV do grupo, com o separador que reconhece mais colunas DO GRUPO.

    O leitor do importador escolhe o separador pelas colunas de crianca, e
    "Telefone" nao e coluna de crianca: num "Nome,Telefone" o ponto e virgula
    empatava com a virgula e vencia, e a linha inteira virava uma coluna so
    (27/11/2026, a planilha do grupo Fraternos). Aqui a nota e a deste
    arquivo: nome e telefone.
    """
    texto = None
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = conteudo.decode(codificacao)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if texto is None:
        raise ValueError("Nao foi possivel ler o arquivo. No Excel, use Salvar como > CSV UTF-8.")

    melhor, melhor_nota = None, -1
    for separador in SEPARADORES:
        tabela = _linhas_do_csv(texto, separador)
        if tabela is None:
            continue
        nota = 0
        for i in range(min(LINHAS_PARA_PROCURAR_CABECALHO, len(tabela))):
            mapa = _mapear([_limpar_celula(v) for v in tabela.iloc[i].tolist()])
            if "nome" in mapa:
                nota = max(nota, len(mapa))
        if nota > melhor_nota:
            melhor, melhor_nota = tabela, nota
    if melhor is None:
        raise ValueError("Nao foi possivel ler o arquivo. Confira se e mesmo uma planilha.")
    return melhor


def ler_planilha(conteudo: bytes, nome_arquivo: str) -> tuple[list[LinhaPadrinho], dict[str, str]]:
    """As linhas da planilha do grupo e quais colunas foram reconhecidas.

    Levanta ValueError com uma frase para a tela quando nao da para ler.
    """
    if nome_arquivo.lower().endswith(".csv"):
        bruto = _ler_csv(conteudo)
    else:
        try:
            bruto = pd.read_excel(BytesIO(conteudo), dtype=str, keep_default_na=False, header=None)
        except Exception as erro:
            raise ValueError(
                "Nao foi possivel ler o arquivo. Envie uma planilha .xlsx ou .csv."
            ) from erro

    if bruto.empty:
        raise ValueError("A planilha esta vazia.")

    # O cabecalho e a primeira linha, entre as dez de cima, que tem o nome.
    cabecalho = None
    for i in range(min(LINHAS_PARA_PROCURAR_CABECALHO, len(bruto))):
        celulas = [_limpar_celula(v) for v in bruto.iloc[i].tolist()]
        mapa = _mapear(celulas)
        if "nome" in mapa:
            cabecalho = (i, celulas, mapa)
            if "whatsapp" in mapa:
                break
    if cabecalho is None:
        raise ValueError(
            "Nao encontrei a coluna do nome do padrinho. Deixe na primeira linha "
            "os titulos 'Nome' e 'Telefone'."
        )

    inicio, celulas, mapa = cabecalho
    reconhecidas = {campo: celulas[i] for campo, i in mapa.items()}

    linhas: list[LinhaPadrinho] = []
    for indice in range(inicio + 1, len(bruto)):
        valores = [_limpar_celula(v) for v in bruto.iloc[indice].tolist()]
        nome = nome_proprio(valores[mapa["nome"]])
        telefone = valores[mapa["whatsapp"]] if "whatsapp" in mapa else ""
        if not nome and not telefone:
            continue
        linha = LinhaPadrinho(
            linha=indice + 1, nome=nome, whatsapp=telefone[:30] or None
        )
        if not nome:
            linha.erros.append("sem nome")
        elif len(nome) < 3:
            linha.erros.append("nome muito curto")
        linhas.append(linha)

    if not linhas:
        raise ValueError("A planilha nao tem nenhum padrinho abaixo do cabecalho.")
    if len(linhas) > MAXIMO_DE_LINHAS:
        raise ValueError(
            f"A planilha tem {len(linhas)} linhas. Um lote aceita ate {MAXIMO_DE_LINHAS}: "
            "confira se e mesmo a lista do grupo."
        )
    return linhas, reconhecidas


def nome_no_zip(padrinho_nome: str, crianca_codigo: str, crianca_nome: str) -> str:
    """{NOME_COMPLETO_DO_PADRINHO}_{CODIGO}_{PRIMEIRO_NOME_DA_CRIANCA}.png

    O agradecimento avulso usa so o primeiro nome do padrinho, e no meio de
    oitenta pessoas do mesmo grupo isso da dois Jose e tres Maria. Aqui o
    arquivo vai para o grupo inteiro de uma vez, e cada pessoa procura o
    proprio nome: por isso ele vem completo e na frente, e a lista sai em
    ordem alfabetica.
    """
    primeiro = (crianca_nome or "").strip().split(" ")[0]
    partes = [limpar_texto(padrinho_nome), limpar_texto(crianca_codigo), limpar_texto(primeiro)]
    return "_".join(p for p in partes if p) + ".png"
