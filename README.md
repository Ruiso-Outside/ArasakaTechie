# ARASAKA TECHIE

Simulador de montagem de PC com o visual da Arasaka, para **Zorin OS e Ubuntu**. Escolha as peças passo a passo
e veja o FPS esperado em jogos populares, o airflow do gabinete, as temperaturas, a fonte certa, quanto um
upgrade rende (com as trocas que ele obriga) e o preço de cada peça com histórico e o link da loja mais barata.

Vai do PC de escritório de 2008 (Core 2 Quad, DDR3) e dos kits **Xeon X79/X99** ao topo de linha atual,
passando por AMD FX/Phenom (AM3/AM3+), APUs FM2+ e as gerações Intel de LGA1155 em diante.

> **Tudo é estimativa.** O Techie usa um modelo simples (explicado abaixo) com pontuações relativas de
> desempenho, não medições. Serve para comparar montagens e entender gargalos, não para prever o FPS exato.

## Abas

| Aba | O que tem |
|---|---|
| **01 Montagem** | Escolha **passo a passo** (processador → placa-mãe → memória → cooler → vídeo → gabinete → fonte → disco): cada passo só mostra o que encaixa no que já foi escolhido, com **busca** (`xeon`, `am3`, `lga1155`, `rtx 3060`, `ddr3`, `16gb`...), foto e preço. Trocar de plataforma desmarca o que deixou de servir. Modelos prontos: entrada, intermediário, topo, kit Xeon X99, PC antigo e AMD FX. Confere soquete (inclusive AM3 em placa AM3+ e LGA1151 de 6ª/7ª × 8ª/9ª geração), DDR3/DDR4/DDR5, memória de servidor ECC REG, slots e limite de RAM, tamanho da placa-mãe, comprimento da GPU, altura do cooler ou radiador, formato e potência da fonte, e avisa de processador sem AVX ou com poucos núcleos |
| **02 Desempenho** | FPS e 1% low em 20 jogos, por resolução (1080p, 1440p, 4K) e qualidade (baixo a ultra), quem limita (CPU ou GPU), o tamanho do gargalo e avisos de falta de VRAM |
| **03 Airflow** | Fans em cada posição (frente, topo, traseira, fundo, lateral), com quantidade, tamanho (80, 92, 120, 140 ou 200 mm, conforme o gabinete) e direção. Mostra pressão positiva/negativa, fluxo, ar interno, temperatura da CPU (jogando e em carga total) e da GPU, e um diagrama do gabinete. Com water cooler, escolhe onde fica o radiador |
| **04 Upgrade** | **Lê as peças deste PC** (processador, placa-mãe, memória com a velocidade real, discos e placa de vídeo, sem precisar de senha) e, com um clique, usa como montagem atual. Sugere **upgrades reais na mesma plataforma** (mesmo soquete e mesma memória): placa de vídeo, processador que serve na placa-mãe atual, memória (dual channel, mais GB), cooler e SSD, em níveis (passo pequeno, equilibrado, máximo e o melhor custo-benefício quando há preço), com o ganho de FPS, o custo e as trocas obrigatórias (ex.: fonte maior). O botão **Sugerir troca de plataforma** mostra processador + placa-mãe + memória de uma plataforma mais nova em três níveis, e avisa quando a placa de vídeo limita e a troca rende pouco agora. **Simular outra peça** continua para qualquer troca |
| **05 Preços** | Menor preço de cada peça hoje e a loja, total da montagem, **histórico** (gráfico de 90+ dias) e se o preço está **baixo, normal ou alto** para o histórico. Botão **Comprar** com o link de afiliado da loja mais barata. A aba Upgrade mostra o custo estimado do upgrade |
| **06 Relatório** | Peças, desempenho, temperaturas, consumo, fonte recomendada, preços e avisos num texto só, para copiar ou salvar em .txt |

A montagem fica salva em `~/.config/arasaka-techie/montagem.json`.

**Leitura do PC:** `/proc/cpuinfo`, `/sys/class/dmi/id` (placa-mãe), `udevadm info -e` (pentes de memória:
tipo, tamanho, quantidade e velocidade configurada), `lsblk` (discos), `nvidia-smi` e `lspci` (placa de vídeo).
O que não está na base (ex.: uma placa-mãe diferente) entra como peça "do seu PC", montada com o que foi lido.
Fonte, gabinete e cooler o sistema não informa: ficam os da montagem atual. Se a memória estiver bem abaixo da
velocidade normal do tipo, o Techie avisa que ativar o EXPO/XMP na BIOS dá FPS de graça.

## O modelo

As peças estão em [`arasaka_techie/data/parts.json`](arasaka_techie/data/parts.json), com especificações de
fábrica (soquete, memória, consumo, comprimento, altura, posições de fan) e uma **pontuação relativa**:
GPU com a RTX 4090 = 100 (rasterização), processador com o Ryzen 7 7800X3D = 100 (jogos).

- **FPS da GPU** = referência do jogo (RTX 4090 em 1080p alto) × (pontuação da GPU / 100)^0,85 × resolução
  (1080p 1,0 · 1440p 0,7 · 4K 0,38) × qualidade (baixo 1,9 · médio 1,4 · alto 1,0 · ultra 0,8).
  Se a VRAM for menor que a necessária para o jogo na resolução e qualidade, o FPS cai (até 40%) e o 1% low piora.
  O expoente 0,85 compensa que placas fracas rendem mais do que a conta linear indica.
- **FPS da CPU** = referência do jogo (7800X3D) × pontuação do processador / 100 × memória (velocidade,
  canal único, pouca RAM) × qualidade. Não depende da resolução.
- **FPS final** = combinação suave dos dois, `(g⁻⁸ + c⁻⁸)^(-1/8)`: fica perto do menor e um pouco abaixo
  quando estão parecidos. O menor é o **gargalo**. Jogos com limite próprio (Elden Ring 60, GTA V 187,
  Apex 300) param ali. 1% low ≈ 72% (CPU limitando) ou 80% (GPU limitando) do FPS médio.
- **Airflow**: vazão típica por tamanho (80 mm ≈ 30 CFM, 92 ≈ 40, 120 ≈ 55, 140 ≈ 68, 200 ≈ 110), menos a
  restrição do painel (tela, vidro, frente fechada) e 30% se houver radiador. Entrada − saída define a pressão.
  Fluxo útil = menor dos dois + metade da diferença + 10 CFM de convecção e frestas.
- **Ar interno** = ambiente + calor (GPU, CPU e placa) / (fluxo × 0,569 W/K por CFM) × mistura
  (1,5 com caminho bom frente/baixo → trás/cima, 1,9 sem caminho claro, 2,2 contra a convecção).
  Radiador soprando para fora tira o calor da CPU do gabinete.
- **CPU** = ar que chega no cooler + offset do chip + 55 °C × consumo / capacidade do cooler, até o limite
  do chip (95 °C AM5, 90 °C AM4, 100 °C Intel), quando ele reduz a frequência e perde FPS.
  **GPU** = ar interno + 42 °C × consumo / consumo de projeto.
- **Fonte recomendada** = a maior entre a recomendação do fabricante da GPU e o pico do sistema × 1,3.

## Preços e links de afiliado

Os preços vêm do **coletor** em [`server/techie`](server/techie/LEIA-ME.md), que roda uma vez por dia no
piphin.online e guarda o histórico para todo mundo. Ele usa a API do **AliExpress Portals**, os feeds de
produtos da **Awin/Lomadee** (KaBuM!, Pichau, Terabyte...), links do **Mercado Livre** que você cadastra
e a busca da **Amazon** com a sua tag. O app só lê `https://piphin.online/techie/api.php` (troque com a
variável `ARASAKA_TECHIE_PRECOS`), guarda em cache em `~/.cache/arasaka-techie` e funciona sem internet com
o último cache. As fotos das peças são as que as lojas informam; sem foto, aparece um desenho da categoria.

**Preço baixo/alto:** compara o menor preço de hoje com os menores preços diários dos últimos 90 dias. Baixo =
entre os 25% dias mais baratos (ou a 2% do mínimo); alto = acima de 75% dos dias; com menos de 7 dias de
histórico, "histórico curto". A aba avisa que os links são de afiliado (o Techie pode receber comissão, sem
custo a mais para quem compra).

## Testes

```bash
python3 tests/test_simulador.py
python3 tests/test_upgrade_pc.py
python3 tests/test_precos.py
php tests/test_coletor.php
```

## Instalar

Pela **Arasaka Central** (Loja → Apps), ou:

```bash
./install.sh
```

Rode **sem sudo**. Para remover: `./uninstall.sh`.

---

Arasaka é marca da CD PROJEKT RED (projeto de fã, sem fins comerciais). Os nomes de peças e jogos são de
seus fabricantes e estúdios. A fonte `cedge1` usa a licença FontStruct Non-Commercial.

### Windows 10/11

Pela **Arasaka Central** (Loja → Apps), ou extraia o `ArasakaTechie-vX.Y.Z-windows.zip` e dê dois cliques em **`install.bat`**. O instalador instala o Python 3.12 pelo winget (se ainda não houver), cria os atalhos no Menu Iniciar e na Área de Trabalho e o comando `arasaka-techie`. Não precisa de administrador. No Windows as peças do seu PC são lidas pelo WMI (processador, placa-mãe, memória, discos e placa de vídeo, com a VRAM da NVIDIA pelo nvidia-smi).
Para remover: `powershell -ExecutionPolicy Bypass -File uninstall.ps1` (os seus dados são mantidos).
