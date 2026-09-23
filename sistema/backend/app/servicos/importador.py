"""Leitura das listas de criancas enviadas pelas instituicoes.

As listas chegam em planilha, cada instituicao com o seu jeito de nomear as
colunas. Aqui elas viram linhas normalizadas, com os problemas ja apontados:
codigo repetido, crianca que ja existe na base, nome parecido com outro.

Nada e gravado nesta etapa. A conferencia acontece na tela, e so depois a
importacao e confirmada.
"""

import unicodedata
from dataclasses import dataclass, field
from io import BytesIO

import pandas as pd
from rapidfuzz import fuzz, process

# Quao parecidos dois nomes precisam ser para virar um aviso de possivel
# duplicata. Abaixo de 88 aparecem muitos falsos positivos entre irmaos.
SEMELHANCA_MINIMA = 88

IDADE_MAXIMA = 21

# Cada campo e os nomes de coluna que ja vimos as instituicoes usarem.
COLUNAS = {
    "codigo": ("codigo", "cod", "matricula", "numero", "n", "id"),
    "nome": ("nome", "nome completo", "crianca", "aluno", "nome da crianca"),
    "idade": ("idade", "anos"),
    "sexo": ("sexo", "genero", "m/f", "sexo (m/f)"),
    "instituicao": ("instituicao", "escola", "entidade", "creche", "instituição"),
    "observacoes": ("observacoes", "observacao", "obs", "observações"),
}


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in normalizado if not unicodedata.combining(c))


# Caracteres invisiveis que planilha real carrega e que ninguem enxerga:
# BOM (o Excel grava ao salvar como "CSV UTF-8"), espaco inquebravel e
# marcadores de largura zero. Sem limpar, "Codigo" com BOM na frente nao casa
# com "codigo" — e a mensagem de erro fica sem sentido, porque na tela os dois
# parecem iguais.
INVISIVEIS = dict.fromkeys(map(ord, "\ufeff\u200b\u200c\u200d\u2060"), None)


def _chave(texto: str) -> str:
    """Forma comparavel de um texto: sem acento, sem invisiveis, minusculo."""
    limpo = str(texto).translate(INVISIVEIS).replace("\xa0", " ")
    return " ".join(_sem_acento(limpo).lower().split())


def _normalizar_sexo(valor) -> str | None:
    bruto = _chave(valor)
    if bruto.startswith(("m", "masc")):
        return "M"
    if bruto.startswith(("f", "fem")):
        return "F"
    return None


def _normalizar_idade(valor) -> int | None:
    try:
        idade = int(float(str(valor).strip().replace(",", ".")))
    except (TypeError, ValueError):
        return None
    return idade if 0 <= idade <= IDADE_MAXIMA else None


@dataclass
class LinhaLida:
    """Uma linha da planilha, ja normalizada e conferida."""

    linha: int
    codigo: str
    nome: str
    idade: int | None
    sexo: str | None
    instituicao_nome: str | None
    observacoes: str | None
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    instituicao_id: int | None = None

    @property
    def valida(self) -> bool:
        return not self.erros


@dataclass
class Leitura:
    linhas: list[LinhaLida]
    colunas_encontradas: dict[str, str]
    colunas_ignoradas: list[str]

    @property
    def validas(self) -> list[LinhaLida]:
        return [l for l in self.linhas if l.valida]


def _mapear_colunas(colunas: list[str]) -> tuple[dict[str, str], list[str]]:
    """Descobre qual coluna da planilha corresponde a cada campo."""
    encontradas: dict[str, str] = {}
    usadas: set[str] = set()

    for campo, aceitos in COLUNAS.items():
        for coluna in colunas:
            if coluna in usadas:
                continue
            if _chave(coluna) in aceitos:
                encontradas[campo] = coluna
                usadas.add(coluna)
                break

    ignoradas = [c for c in colunas if c not in usadas]
    return encontradas, ignoradas


def _ler_csv(conteudo: bytes):
    """Le o CSV tentando as codificacoes que aparecem na pratica.

    utf-8-sig e o utf-8 que descarta o BOM do Excel. Se o arquivo veio de um
    Excel mais antigo em portugues, costuma estar em Windows-1252 — e ai os
    acentos quebram em utf-8.

    sep=None deixa o pandas descobrir sozinho se o separador e virgula ou
    ponto e virgula (o padrao no Brasil).
    """
    ultimo_erro: Exception | None = None

    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(
                BytesIO(conteudo),
                dtype=str,
                sep=None,
                engine="python",
                keep_default_na=False,
                encoding=codificacao,
            )
        except (UnicodeDecodeError, LookupError) as erro:
            ultimo_erro = erro
            continue
        except Exception as erro:
            raise ValueError(
                "Nao foi possivel ler o arquivo. Confira se e mesmo uma planilha "
                "e se tem uma linha de cabecalho."
            ) from erro

    raise ValueError(
        "Nao foi possivel ler o arquivo: a codificacao nao foi reconhecida. "
        "No Excel, use Salvar como > CSV UTF-8."
    ) from ultimo_erro


def ler_planilha(conteudo: bytes, nome_arquivo: str) -> Leitura:
    """Le o arquivo e devolve as linhas normalizadas.

    Aceita .xlsx e .csv. Levanta ValueError com uma mensagem util quando o
    arquivo nao da para ler ou nao tem as colunas minimas.
    """
    minusculo = nome_arquivo.lower()

    if minusculo.endswith(".csv"):
        tabela = _ler_csv(conteudo)
    else:
        try:
            tabela = pd.read_excel(BytesIO(conteudo), dtype=str, keep_default_na=False)
        except Exception as erro:
            raise ValueError(
                "Nao foi possivel ler o arquivo. Envie uma planilha .xlsx ou .csv."
            ) from erro

    # O strip tira espaco; o translate tira os invisiveis que sobrariam.
    tabela.columns = [
        str(c).translate(INVISIVEIS).replace("\xa0", " ").strip() for c in tabela.columns
    ]
    encontradas, ignoradas = _mapear_colunas(list(tabela.columns))

    faltando = [c for c in ("codigo", "nome") if c not in encontradas]
    if faltando:
        quais = " e ".join(f"'{c}'" for c in faltando)
        achadas = ", ".join(f"'{c}'" for c in tabela.columns) or "(nenhuma)"
        aceitos = {c: " ou ".join(COLUNAS[c]) for c in faltando}
        raise ValueError(
            f"Nao encontrei a coluna {quais} na planilha. "
            f"Colunas encontradas: {achadas}. "
            + " ".join(f"Para {c}, aceito: {nomes}." for c, nomes in aceitos.items())
        )

    linhas: list[LinhaLida] = []
    for indice, registro in tabela.iterrows():
        def pegar(campo: str) -> str:
            coluna = encontradas.get(campo)
            return str(registro[coluna]).strip() if coluna else ""

        nome = " ".join(pegar("nome").split())
        codigo = pegar("codigo")

        # Linha totalmente vazia (comum no fim da planilha) e ignorada.
        if not nome and not codigo:
            continue

        linha = LinhaLida(
            linha=int(indice) + 2,  # +2: a linha 1 e o cabecalho e o indice comeca em 0
            codigo=codigo,
            nome=nome,
            idade=_normalizar_idade(pegar("idade")) if encontradas.get("idade") else None,
            sexo=_normalizar_sexo(pegar("sexo")) if encontradas.get("sexo") else None,
            instituicao_nome=pegar("instituicao") or None,
            observacoes=pegar("observacoes") or None,
        )

        if not linha.codigo:
            linha.erros.append("sem codigo")
        if not linha.nome:
            linha.erros.append("sem nome")
        elif len(linha.nome) < 3:
            linha.erros.append("nome muito curto")

        if encontradas.get("idade") and linha.idade is None:
            linha.erros.append("idade invalida")
        if encontradas.get("sexo") and linha.sexo is None:
            linha.erros.append("sexo invalido (use M ou F)")

        linhas.append(linha)

    return Leitura(linhas=linhas, colunas_encontradas=encontradas, colunas_ignoradas=ignoradas)


def marcar_repetidas_no_arquivo(linhas: list[LinhaLida]) -> None:
    """Aponta codigos repetidos dentro da propria planilha."""
    vistos: dict[str, int] = {}
    for linha in linhas:
        if not linha.codigo:
            continue
        chave = linha.codigo.strip().lower()
        if chave in vistos:
            linha.erros.append(f"codigo repetido (ja aparece na linha {vistos[chave]})")
        else:
            vistos[chave] = linha.linha


def marcar_ja_cadastradas(linhas: list[LinhaLida], codigos_na_base: set[str]) -> None:
    """Aponta quem ja esta na base, pela chave edicao + instituicao + codigo."""
    for linha in linhas:
        if linha.instituicao_id is None or not linha.codigo:
            continue
        if f"{linha.instituicao_id}|{linha.codigo.strip().lower()}" in codigos_na_base:
            linha.erros.append("ja cadastrada nesta edicao")


def marcar_nomes_parecidos(linhas: list[LinhaLida], nomes_na_base: list[str]) -> None:
    """Avisa quando o nome e muito parecido com o de outra crianca.

    E so aviso, nunca erro: irmaos com nomes parecidos existem, e quem confere
    decide. Compara tanto com a base quanto dentro da propria planilha.
    """
    referencia = [_chave(n) for n in nomes_na_base]
    vistos: dict[str, int] = {}

    for linha in linhas:
        if not linha.nome:
            continue

        chave = _chave(linha.nome)

        if referencia:
            achado = process.extractOne(chave, referencia, scorer=fuzz.token_sort_ratio)
            if achado and achado[1] >= SEMELHANCA_MINIMA:
                linha.avisos.append(
                    f"nome parecido com '{nomes_na_base[achado[2]]}', ja na base"
                )

        parecido_no_arquivo = process.extractOne(
            chave, list(vistos), scorer=fuzz.token_sort_ratio
        ) if vistos else None
        if parecido_no_arquivo and parecido_no_arquivo[1] >= SEMELHANCA_MINIMA:
            linha.avisos.append(
                f"nome parecido com a linha {vistos[parecido_no_arquivo[0]]} deste arquivo"
            )

        vistos[chave] = linha.linha


def casar_instituicoes(
    linhas: list[LinhaLida],
    instituicoes: dict[int, str],
    instituicao_padrao: int | None,
) -> None:
    """Liga cada linha a uma instituicao.

    Se a planilha traz o nome da instituicao, procura pelo nome (exato, e
    depois por semelhanca). Senao, usa a instituicao escolhida na tela.
    """
    por_chave = {_chave(nome): id_ for id_, nome in instituicoes.items()}
    chaves = list(por_chave)

    for linha in linhas:
        if not linha.instituicao_nome:
            linha.instituicao_id = instituicao_padrao
            if instituicao_padrao is None:
                linha.erros.append("sem instituicao")
            continue

        chave = _chave(linha.instituicao_nome)

        if chave in por_chave:
            linha.instituicao_id = por_chave[chave]
            continue

        achado = process.extractOne(chave, chaves, scorer=fuzz.token_sort_ratio) if chaves else None
        if achado and achado[1] >= SEMELHANCA_MINIMA:
            linha.instituicao_id = por_chave[achado[0]]
            linha.avisos.append(
                f"instituicao '{linha.instituicao_nome}' entendida como "
                f"'{instituicoes[linha.instituicao_id]}'"
            )
        elif instituicao_padrao is not None:
            linha.instituicao_id = instituicao_padrao
            linha.avisos.append(
                f"instituicao '{linha.instituicao_nome}' nao reconhecida; "
                "usando a instituicao escolhida"
            )
        else:
            linha.erros.append(f"instituicao '{linha.instituicao_nome}' nao cadastrada")
