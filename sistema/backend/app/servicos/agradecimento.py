"""Agradecimento: a arte que o padrinho recebe no WhatsApp.

"Agradecimento", e nunca "cartao": cartao e so o de cesta e o de festa, o
papel que a crianca escreve (routers/cartoes.py). Esta e a arte que o
sistema monta.

Um agradecimento por crianca apadrinhada, com o nome dela, o codigo, a instituicao e
o dia em que ela estara no evento.

A arte em si NAO e desenhada aqui. Quem faz o template e o design, a mao, e
solta o arquivo em disco; este modulo so escreve os quatro campos por cima,
nas posicoes que o `layout.json` ao lado do template manda. Trocar a arte do
ano que vem e trocar um PNG — nao e mexer em Python.

Onde ficam os arquivos (o primeiro que existir vence):

    {ARQUIVOS_DIR}/agradecimento/{CIDADE}/{ano}/template.png   <- por edicao
    {ARQUIVOS_DIR}/agradecimento/template.png                  <- para todas

Sem nenhum dos dois, o sistema desenha uma arte simples com as cores da
marca, para a funcionalidade nao ficar esperando o design ficar pronto.
"""

import json
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import config
from app.servicos.arquivos import limpar_texto

PASTA_FONTES = Path(__file__).resolve().parent.parent / "recursos" / "fontes"

FONTES = {
    "regular": PASTA_FONTES / "Typold-Regular.otf",
    "bold": PASTA_FONTES / "Typold-Bold.otf",
    "extrabold": PASTA_FONTES / "Typold-ExtraBold.otf",
}

# Tamanho da arte que o sistema desenha quando ainda nao ha template. 1080
# de largura e o que o WhatsApp entrega sem recomprimir demais.
LARGURA_PADRAO = 1080
ALTURA_PADRAO = 1350

NAVY = "#153377"
NAVY_ESCURO = "#0d2352"
AMBER = "#ffb000"
CREME = "#fbf7ee"
BRANCO = "#ffffff"


@dataclass
class Campo:
    """Onde e como um texto entra na arte.

    x/y sao pixels DO TEMPLATE, contados do canto superior esquerdo. Com
    `ancora` terminando em "m" (centro) o x e o meio do texto, nao a borda.
    """

    x: int
    y: int
    tamanho: int = 40
    cor: str = NAVY
    fonte: str = "bold"
    # Ancoras do Pillow: "la" = esquerda/cima, "ma" = centro/cima.
    ancora: str = "la"
    maiusculas: bool = False
    # O texto encolhe ate caber nesta largura. Nome de crianca varia muito.
    largura_max: int | None = None
    # Texto fixo que aparece antes do valor (ex.: "Codigo ").
    prefixo: str = ""


@dataclass
class Layout:
    campos: dict[str, Campo] = field(default_factory=dict)


# Posicoes da arte que o sistema desenha sozinho. Quando houver template
# proprio, o layout.json dele manda — estas ficam so de reserva.
LAYOUT_PADRAO = Layout(
    campos={
        "nome": Campo(
            x=LARGURA_PADRAO // 2, y=560, tamanho=76, cor=NAVY, fonte="extrabold",
            ancora="ma", largura_max=900,
        ),
        "codigo": Campo(
            x=LARGURA_PADRAO // 2, y=670, tamanho=34, cor=AMBER, fonte="extrabold",
            ancora="ma", maiusculas=True, largura_max=900,
        ),
        "instituicao": Campo(
            x=LARGURA_PADRAO // 2, y=860, tamanho=40, cor=NAVY, fonte="bold",
            ancora="ma", largura_max=880,
        ),
        "dia": Campo(
            x=LARGURA_PADRAO // 2, y=1030, tamanho=48, cor=NAVY, fonte="extrabold",
            ancora="ma", largura_max=880,
        ),
    }
)

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def formatar_dia(dia: date | None) -> str:
    """15 de dezembro de 2026 — por extenso, que e como se le num convite."""
    if dia is None:
        return "data a confirmar"
    return f"{dia.day} de {MESES[dia.month - 1]} de {dia.year}"


def pasta_da_edicao(cidade: str, ano: int) -> Path:
    return config.caminho_arquivos / "agradecimento" / limpar_texto(cidade) / str(ano)


def achar_template(cidade: str, ano: int) -> Path | None:
    """Template da edicao; senao o geral; senao nenhum."""
    candidatos = [
        pasta_da_edicao(cidade, ano) / "template.png",
        config.caminho_arquivos / "agradecimento" / "template.png",
    ]
    for caminho in candidatos:
        if caminho.is_file():
            return caminho
    return None


def _carregar_layout(template: Path | None) -> Layout:
    """layout.json ao lado do template. Campo ausente cai no padrao."""
    if template is None:
        return LAYOUT_PADRAO

    arquivo = template.with_name("layout.json")
    if not arquivo.is_file():
        return LAYOUT_PADRAO

    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    campos = {
        nome: Campo(**valores)
        for nome, valores in dados.get("campos", {}).items()
    }
    return Layout(campos=campos)


def _fonte(nome: str, tamanho: int) -> ImageFont.FreeTypeFont:
    caminho = FONTES.get(nome, FONTES["bold"])
    return ImageFont.truetype(str(caminho), tamanho)


def _largura(desenho: ImageDraw.ImageDraw, texto: str, fonte) -> int:
    esquerda, _, direita, _ = desenho.textbbox((0, 0), texto, font=fonte)
    return direita - esquerda


def _escrever(desenho: ImageDraw.ImageDraw, texto: str, campo: Campo) -> None:
    """Escreve um campo, encolhendo a fonte ate caber em largura_max.

    Sem isto "Escola Municipal Professora Maria das Dores" atravessaria a arte
    inteira — e e justamente o tipo de nome que as instituicoes tem.
    """
    if not texto:
        return

    texto = f"{campo.prefixo}{texto}"
    if campo.maiusculas:
        texto = texto.upper()

    tamanho = campo.tamanho
    fonte = _fonte(campo.fonte, tamanho)

    if campo.largura_max:
        # 60% do tamanho original e o piso: abaixo disso nao da para ler, e e
        # melhor deixar transbordar de leve do que entregar algo ilegivel.
        minimo = max(12, int(campo.tamanho * 0.6))
        while tamanho > minimo and _largura(desenho, texto, fonte) > campo.largura_max:
            tamanho -= 2
            fonte = _fonte(campo.fonte, tamanho)

    desenho.text((campo.x, campo.y), texto, font=fonte, fill=campo.cor, anchor=campo.ancora)


def _arte_de_reserva() -> Image.Image:
    """Arte simples, so com as cores da marca.

    Existe para a funcionalidade rodar antes de o design ficar pronto — nao
    para substituir o template de verdade.
    """
    imagem = Image.new("RGB", (LARGURA_PADRAO, ALTURA_PADRAO), CREME)
    desenho = ImageDraw.Draw(imagem)

    desenho.rectangle([0, 0, LARGURA_PADRAO, 300], fill=NAVY)
    desenho.rectangle([0, 300, LARGURA_PADRAO, 316], fill=AMBER)
    desenho.rectangle([0, ALTURA_PADRAO - 90, LARGURA_PADRAO, ALTURA_PADRAO], fill=NAVY)

    meio = LARGURA_PADRAO // 2
    desenho.text((meio, 120), "NATAL LUMEN", font=_fonte("extrabold", 46),
                 fill=BRANCO, anchor="ma")
    desenho.text((meio, 190), "obrigado por apadrinhar", font=_fonte("regular", 34),
                 fill=CREME, anchor="ma")

    desenho.text((meio, 470), "VOCÊ APADRINHOU", font=_fonte("bold", 28),
                 fill=NAVY_ESCURO, anchor="ma")
    desenho.text((meio, 790), "INSTITUIÇÃO", font=_fonte("bold", 26),
                 fill=NAVY_ESCURO, anchor="ma")
    desenho.text((meio, 960), "ELA ESTARÁ NO EVENTO EM", font=_fonte("bold", 26),
                 fill=NAVY_ESCURO, anchor="ma")

    desenho.text((meio, ALTURA_PADRAO - 58), "natallumen.com.br",
                 font=_fonte("bold", 26), fill=CREME, anchor="ma")
    return imagem


def gerar(
    *,
    crianca_nome: str,
    crianca_codigo: str,
    instituicao: str,
    dia_evento: date | None,
    cidade: str,
    ano: int,
) -> bytes:
    """Devolve o PNG do agradecimento, pronto para baixar e mandar no WhatsApp."""
    template = achar_template(cidade, ano)

    if template is None:
        imagem = _arte_de_reserva()
    else:
        # convert: um template em CMYK ou com paleta indexada quebraria o
        # desenho do texto.
        imagem = Image.open(template).convert("RGB")

    layout = _carregar_layout(template)
    desenho = ImageDraw.Draw(imagem)

    valores = {
        "nome": crianca_nome,
        "codigo": crianca_codigo,
        "instituicao": instituicao,
        "dia": formatar_dia(dia_evento),
    }

    for nome, campo in layout.campos.items():
        _escrever(desenho, valores.get(nome, ""), campo)

    saida = BytesIO()
    imagem.save(saida, format="PNG", optimize=True)
    return saida.getvalue()


def nome_do_arquivo(codigo: str, crianca_nome: str, padrinho_nome: str) -> str:
    """{CODIGO}_{PRIMEIRO_NOME_DA_CRIANCA}_PAD_{PRIMEIRO_NOME_DO_PADRINHO}.png

    "ES01_ANA_PAD_JOSE.png": o codigo casa o arquivo com a planilha, e os dois
    primeiros nomes dizem de quem para quem, sem abrir a imagem — e o que o
    comissario procura na pasta de downloads com varios padrinhos no mesmo dia.

    Passa pelo limpar_texto, como o nome dos cartoes digitalizados: sem acento
    e sem espaco o arquivo atravessa WhatsApp, Windows e Drive sem virar
    "ES01_Ana%20A%CC%81vila".
    """
    def primeiro(nome: str) -> str:
        return limpar_texto((nome or "").strip().split(" ")[0])

    partes = [limpar_texto(codigo), primeiro(crianca_nome)]
    base = "_".join(p for p in partes if p) or "AGRADECIMENTO"
    padrinho = primeiro(padrinho_nome)
    return f"{base}_PAD_{padrinho}.png" if padrinho else f"{base}.png"
