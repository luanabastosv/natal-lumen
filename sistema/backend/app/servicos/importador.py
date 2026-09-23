"""Leitura das listas de criancas enviadas pelas instituicoes.

As listas chegam em planilha, cada instituicao com o seu jeito de nomear as
colunas. Aqui elas viram linhas normalizadas, com os problemas ja apontados:
codigo repetido, crianca que ja existe na base, nome parecido com outro.

Nada e gravado nesta etapa. A conferencia acontece na tela, e so depois a
importacao e confirmada.
"""

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from io import BytesIO, StringIO

import pandas as pd
from rapidfuzz import fuzz, process

# Quao parecidos dois nomes precisam ser para virar um aviso de possivel
# duplicata. Abaixo de 88 aparecem muitos falsos positivos entre irmaos.
SEMELHANCA_MINIMA = 88

IDADE_MAXIMA = 21

# Cada campo e os cabecalhos que as instituicoes usam. Tudo e comparado depois
# de _chave(), que tira acento, baixa a caixa e normaliza espacos — entao
# "NOME", "Nome" e "nome" sao a mesma coisa e nao precisam estar repetidos.
COLUNAS = {
    "codigo": (
        "codigo", "cod", "n", "no", "num", "numero", "matricula", "registro",
        "id", "ordem", "item", "codigo da crianca", "cod crianca",
        "numero de ordem", "n de ordem",
    ),
    "nome": (
        "nome", "nome completo", "nome da crianca", "nome do aluno",
        "nome da danca", "nome e sobrenome", "nome sobrenome",
        "nome do beneficiario", "nome da beneficiaria", "nome completo da crianca",
        "crianca", "aluno", "aluna", "beneficiario", "beneficiaria", "participante",
    ),
    "idade": ("idade", "anos", "idade anos", "idade em anos", "qtd anos"),
    "sexo": (
        "sexo", "genero", "m/f", "sexo (m/f)", "sexo m/f", "f/m",
        "masculino/feminino", "menino/menina", "sexo da crianca",
    ),
    "instituicao": (
        "instituicao", "escola", "entidade", "creche", "abrigo", "unidade",
        "ong", "projeto", "local", "nome da instituicao", "nome da escola",
        "instituicao/escola",
    ),
    "observacoes": (
        "observacoes", "observacao", "obs", "obs.", "comentario", "comentarios",
        "nota", "notas", "detalhes",
    ),
}

# No segundo passe, os campos sao procurados nesta ordem. "nome" fica por
# ultimo de proposito: uma coluna "Nome da Instituicao" tem de ser reconhecida
# como instituicao, e nao como o nome da crianca.
ORDEM_DO_SEGUNDO_PASSE = ("instituicao", "codigo", "idade", "sexo", "observacoes", "nome")


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


def _contem_termo(chave_coluna: str, termo: str) -> bool:
    """Se o termo aparece no cabecalho como palavra inteira.

    Palavra inteira, e nao pedaco: assim "codigo" nao casa com "codigos
    postais", e "no" nao casa com "nome".
    """
    return re.search(rf"(^|\W){re.escape(termo)}($|\W)", chave_coluna) is not None


def _mapear_colunas(colunas: list[str]) -> tuple[dict[str, str], list[str]]:
    """Descobre qual coluna da planilha corresponde a cada campo.

    Dois passes. O primeiro exige o cabecalho igual a um dos aceitos. O segundo
    aceita o cabecalho que CONTENHA um deles — e o que resgata coisas como
    "Nome Completo da Crianca (sem abreviar)", que nenhuma lista preveria.
    """
    encontradas: dict[str, str] = {}
    usadas: set[str] = set()
    chaves = {coluna: _chave(coluna) for coluna in colunas}

    # 1. Cabecalho exatamente igual a um dos aceitos.
    for campo, aceitos in COLUNAS.items():
        for coluna in colunas:
            if coluna in usadas:
                continue
            if chaves[coluna] in aceitos:
                encontradas[campo] = coluna
                usadas.add(coluna)
                break

    # 2. Cabecalho que contem um dos aceitos. Do termo mais longo para o mais
    # curto, para "nome da instituicao" ganhar de "nome".
    for campo in ORDEM_DO_SEGUNDO_PASSE:
        if campo in encontradas:
            continue

        candidatos = sorted(COLUNAS[campo], key=len, reverse=True)
        achou = False
        for termo in candidatos:
            for coluna in colunas:
                if coluna in usadas:
                    continue
                if _contem_termo(chaves[coluna], termo):
                    encontradas[campo] = coluna
                    usadas.add(coluna)
                    achou = True
                    break
            if achou:
                break

    ignoradas = [c for c in colunas if c not in usadas]
    return encontradas, ignoradas


# Separadores que aparecem de verdade. O ponto e virgula vem primeiro porque e
# o que o Excel brasileiro usa.
SEPARADORES = (";", ",", "\t", "|")


def _ler_csv(conteudo: bytes):
    """Le o CSV tentando as codificacoes e separadores que aparecem na pratica.

    utf-8-sig e o utf-8 que descarta o BOM do Excel. Se o arquivo veio de um
    Excel mais antigo em portugues, costuma estar em Windows-1252 — e ai os
    acentos quebram em utf-8.

    O separador e testado um a um, e nao adivinhado pelo pandas: com sep=None
    ele olha a PRIMEIRA linha, e numa planilha que comeca com um titulo
    ("Relatorio da instituicao") ele acaba cortando por espacos.

    Vence o parse em que da para achar um cabecalho com mais campos.
    """
    texto = None
    ultimo_erro: Exception | None = None

    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = conteudo.decode(codificacao)
            break
        except (UnicodeDecodeError, LookupError) as erro:
            ultimo_erro = erro

    if texto is None:
        raise ValueError(
            "Nao foi possivel ler o arquivo: a codificacao nao foi reconhecida. "
            "No Excel, use Salvar como > CSV UTF-8."
        ) from ultimo_erro

    melhor = None
    melhor_nota = -1

    for separador in SEPARADORES:
        tentativa = _linhas_do_csv(texto, separador)
        if tentativa is None:
            continue

        nota = _nota_do_parse(tentativa)
        if nota > melhor_nota:
            melhor_nota, melhor = nota, tentativa

    if melhor is None:
        raise ValueError(
            "Nao foi possivel ler o arquivo. Confira se e mesmo uma planilha "
            "e se tem uma linha de cabecalho."
        )

    return melhor


def _linhas_do_csv(texto: str, separador: str):
    """Le o CSV com o modulo csv e iguala a largura das linhas.

    O pandas decide o numero de colunas pela PRIMEIRA linha. Numa planilha que
    comeca com um titulo — uma celula so — ele passa a esperar uma coluna, e
    quebra ao encontrar tres na linha do cabecalho. Lendo aqui e preenchendo o
    que falta, o titulo deixa de atrapalhar.
    """
    try:
        linhas = [linha for linha in csv.reader(StringIO(texto), delimiter=separador)]
    except csv.Error:
        return None

    linhas = [linha for linha in linhas if any(str(c).strip() for c in linha)]
    if not linhas:
        return None

    largura = max(len(linha) for linha in linhas)
    if largura < 1:
        return None

    emparelhadas = [linha + [""] * (largura - len(linha)) for linha in linhas]
    return pd.DataFrame(emparelhadas, dtype=str)


def _nota_do_parse(tabela) -> int:
    """Quantos campos o melhor cabecalho deste parse reconhece.

    E o criterio para escolher entre um separador e outro: o que "entende" mais
    colunas e o certo.
    """
    melhor = 0
    for i in range(min(LINHAS_PARA_PROCURAR_CABECALHO, len(tabela))):
        candidata = [_limpar_celula(v) for v in tabela.iloc[i].tolist()]
        reconhecidas, _ = _mapear_colunas([c for c in candidata if c])
        if "nome" in reconhecidas:
            melhor = max(melhor, len(reconhecidas))
    return melhor


# Ate onde procurar o cabecalho. Planilha com titulo, subtitulo, logo e linha
# em branco antes da tabela e comum; dez linhas cobrem com folga.
LINHAS_PARA_PROCURAR_CABECALHO = 10


def _limpar_celula(valor) -> str:
    return str(valor).translate(INVISIVEIS).replace("\xa0", " ").strip()


def _com_cabecalho(bruto):
    """Descobre em qual linha esta o cabecalho e devolve a tabela a partir dela.

    Muita planilha comeca com "LISTA DE CRIANCAS 2026" na primeira linha, uma
    linha em branco, e so entao os cabecalhos. Assumir a primeira linha faria o
    titulo virar nome de coluna e a planilha inteira ser recusada.

    A linha escolhida e a que reconhece mais campos — e que reconhece o nome,
    sem o qual nao da para importar nada.
    """
    if bruto.empty:
        return bruto

    melhor_linha = None
    melhor_nota = 0

    for i in range(min(LINHAS_PARA_PROCURAR_CABECALHO, len(bruto))):
        candidata = [_limpar_celula(v) for v in bruto.iloc[i].tolist()]
        if not any(candidata):
            continue

        reconhecidas, _ = _mapear_colunas([c for c in candidata if c])
        if "nome" not in reconhecidas:
            continue

        nota = len(reconhecidas)
        if nota > melhor_nota:
            melhor_nota, melhor_linha = nota, i

    # Nenhuma linha parece cabecalho: fica a primeira, e a mensagem de erro
    # mais adiante explica o que faltou.
    if melhor_linha is None:
        melhor_linha = 0

    cabecalhos = [_limpar_celula(v) for v in bruto.iloc[melhor_linha].tolist()]
    tabela = bruto.iloc[melhor_linha + 1 :].copy()
    tabela.columns = cabecalhos
    tabela = tabela.reset_index(drop=True)

    # Colunas sem nome sobram de titulo em celula mesclada; nao servem.
    tabela = tabela.loc[:, [bool(c) for c in cabecalhos]]
    # Guardado para a numeracao das linhas bater com a que a pessoa ve no Excel.
    tabela.attrs["linha_do_cabecalho"] = melhor_linha
    return tabela


def ler_planilha(conteudo: bytes, nome_arquivo: str) -> Leitura:
    """Le o arquivo e devolve as linhas normalizadas.

    Aceita .xlsx e .csv. Levanta ValueError com uma mensagem util quando o
    arquivo nao da para ler ou nao tem as colunas minimas.
    """
    minusculo = nome_arquivo.lower()

    if minusculo.endswith(".csv"):
        bruto = _ler_csv(conteudo)
    else:
        try:
            bruto = pd.read_excel(
                BytesIO(conteudo), dtype=str, keep_default_na=False, header=None
            )
        except Exception as erro:
            raise ValueError(
                "Nao foi possivel ler o arquivo. Envie uma planilha .xlsx ou .csv."
            ) from erro

    tabela = _com_cabecalho(bruto)
    encontradas, ignoradas = _mapear_colunas(list(tabela.columns))

    # O codigo deixou de ser obrigatorio: as instituicoes mandam a lista sem
    # ele, e quem monta e a aplicacao, pela ordem do projeto.
    faltando = [c for c in ("nome",) if c not in encontradas]
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
            # +2 sobre o indice do cabecalho encontrado: a planilha conta a
            # partir de 1 e o cabecalho ocupa uma linha.
            linha=int(indice) + 2 + tabela.attrs.get("linha_do_cabecalho", 0),
            codigo=codigo,
            nome=nome,
            idade=_normalizar_idade(pegar("idade")) if encontradas.get("idade") else None,
            sexo=_normalizar_sexo(pegar("sexo")) if encontradas.get("sexo") else None,
            instituicao_nome=pegar("instituicao") or None,
            observacoes=pegar("observacoes") or None,
        )

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
    """Aponta codigos repetidos dentro da propria planilha.

    So vale quando a planilha traz codigo. Sem codigo, quem numera e a
    aplicacao, e repeticao nao existe.
    """
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
