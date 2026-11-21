# ARASAKA TECHIE

Simulador de montagem de PC com o visual da Arasaka, para **Zorin OS e Ubuntu**. Escolha as peças e veja
o FPS esperado em jogos populares, o airflow do gabinete, as temperaturas, a fonte certa e quanto um
upgrade rende, com as trocas que ele obriga.

> **Tudo é estimativa.** O Techie usa um modelo simples (explicado abaixo) com pontuações relativas de
> desempenho, não medições. Serve para comparar montagens e entender gargalos, não para prever o FPS exato.

## Abas

| Aba | O que tem |
|---|---|
| **01 Montagem** | Processador, placa-mãe, RAM, placa de vídeo, armazenamento, fonte, gabinete e cooler. Modelos prontos (entrada 1080p, intermediário 1440p, topo 4K). A compatibilidade é conferida na hora: soquete, DDR4/DDR5, slots e limite de RAM, tamanho da placa-mãe, comprimento da GPU, altura do cooler ou radiador, formato e potência da fonte |
| **02 Desempenho** | FPS e 1% low em 16 jogos, por resolução (1080p, 1440p, 4K) e qualidade (baixo a ultra), quem limita (CPU ou GPU), o tamanho do gargalo e avisos de falta de VRAM |
| **03 Airflow** | Fans em cada posição (frente, topo, traseira, fundo, lateral), com quantidade, tamanho (80, 92, 120, 140 ou 200 mm, conforme o gabinete) e direção. Mostra pressão positiva/negativa, fluxo, ar interno, temperatura da CPU (jogando e em carga total) e da GPU, e um diagrama do gabinete. Com water cooler, escolhe onde fica o radiador |
| **04 Upgrade** | Escolha a peça nova e veja o ganho médio e jogo a jogo, as **trocas obrigatórias** (CPU de outro soquete pede placa-mãe nova, DDR5 pede RAM nova, GPU grande pede fonte maior ou gabinete com espaço, processador forte pede cooler melhor) e as temperaturas e o consumo antes e depois. **Aplicar na montagem** leva tudo para a aba 01 |
| **05 Relatório** | Peças, desempenho, temperaturas, consumo, fonte recomendada e avisos num texto só, para copiar ou salvar em .txt |

A montagem fica salva em `~/.config/arasaka-techie/montagem.json`.

## O modelo

As peças estão em [`arasaka_techie/data/parts.json`](arasaka_techie/data/parts.json), com especificações de
fábrica (soquete, memória, consumo, comprimento, altura, posições de fan) e uma **pontuação relativa**:
GPU com a RTX 4090 = 100 (rasterização), processador com o Ryzen 7 7800X3D = 100 (jogos).

- **FPS da GPU** = referência do jogo (RTX 4090 em 1080p alto) × pontuação da GPU / 100 × resolução
  (1080p 1,0 · 1440p 0,7 · 4K 0,38) × qualidade (baixo 1,9 · médio 1,4 · alto 1,0 · ultra 0,8).
  Se a VRAM for menor que a necessária para o jogo na resolução e qualidade, o FPS cai e o 1% low piora.
- **FPS da CPU** = referência do jogo (7800X3D) × pontuação do processador / 100 × memória (velocidade,
  canal único, pouca RAM) × qualidade. Não depende da resolução.
- **FPS final** = combinação suave dos dois, `(g⁻⁸ + c⁻⁸)^(-1/8)`: fica perto do menor e um pouco abaixo
  quando estão parecidos. O menor é o **gargalo**. Jogos com limite próprio (Elden Ring 60, GTA V 187,
  Apex 300) param ali. 1% low ≈ 72% (CPU limitando) ou 80% (GPU limitando) do FPS médio.
- **Airflow**: vazão típica por tamanho (80 mm ≈ 30 CFM, 92 ≈ 40, 120 ≈ 55, 140 ≈ 68, 200 ≈ 110), menos a
  restrição do painel (tela, vidro, frente fechada) e 30% se houver radiador. Entrada − saída define a pressão.
  Fluxo útil = menor dos dois + metade da diferença (o resto passa pelas frestas).
- **Ar interno** = ambiente + calor (GPU, CPU e placa) / (fluxo × 0,569 W/K por CFM) × mistura
  (1,5 com caminho bom frente/baixo → trás/cima, 1,9 sem caminho claro, 2,2 contra a convecção).
  Radiador soprando para fora tira o calor da CPU do gabinete.
- **CPU** = ar que chega no cooler + offset do chip + 55 °C × consumo / capacidade do cooler, até o limite
  do chip (95 °C AM5, 90 °C AM4, 100 °C Intel), quando ele reduz a frequência e perde FPS.
  **GPU** = ar interno + 42 °C × consumo / consumo de projeto.
- **Fonte recomendada** = a maior entre a recomendação do fabricante da GPU e o pico do sistema × 1,3.

## Testes

```bash
python3 tests/test_simulador.py
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
