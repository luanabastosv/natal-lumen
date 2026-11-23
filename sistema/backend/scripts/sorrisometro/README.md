# Recortar a arte do sorrisômetro

Os elementos de `app/recursos/sorrisometro/` saíram da arte que o design fechou
no Canva (PNG de 4563 × 6454 px, fundo azul, termômetro vazio, com números de
exemplo). Para trocar a arte, rode os dois scripts numa pasta de trabalho,
com o PNG do Canva salvo como `ref.png` e com `scipy` instalado:

1. `preparar_base.py`: apaga os números e os traços de exemplo e grava
   `assets/base.png`, os rótulos e as máscaras das faixas (`assets/faixa_*.png`
   saem de um flood fill dentro de cada faixa; veja o comentário no script).
2. `extrair_camadas.py`: separa título, termômetro e Estrela do fundo azul e
   grava tudo em `assets2/`, na metade do tamanho.

Depois, copie o conteúdo de `assets2/` para `app/recursos/sorrisometro/` e
rode `python -m tests.test_estrelinha`.

As coordenadas fixas (posição dos números de exemplo, da linha do meio, dos
tracinhos da régua) são as da arte de 2026. Uma arte nova com o termômetro em
outro lugar pede ajustar esses números nos dois scripts e em
`app/servicos/sorrisometro.py`.
