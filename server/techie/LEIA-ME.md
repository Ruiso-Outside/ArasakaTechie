# Coletor de preços do ARASAKA TECHIE

Roda no seu site (ex.: `piphin.online/techie/`), uma vez por dia. Consulta as lojas pelos programas de afiliado,
guarda o menor preço de cada peça por dia (o histórico) e entrega tudo para o app em `api.php`. Como o histórico
fica no servidor, todo mundo que usa o Techie vê o mesmo histórico desde o primeiro dia.

## Lojas

| Loja | Como entra | Preço automático | Seu link de afiliado |
|---|---|---|---|
| **AliExpress** | API do AliExpress Portals (App Key, App Secret, Tracking ID) | sim | sim (o `promotion_link` da API) |
| **KaBuM!, Pichau, Terabyte...** | Feed de produtos da **Awin** ou da **Lomadee** (URL do feed CSV) | sim | sim (os links do feed já vêm com o seu ID) |
| **Mercado Livre** | Links que você gera no painel de Afiliados e cola em `ofertas-manuais.json` | só se você informar | sim |
| **Amazon** | Sua tag de Associado: o app mostra "Buscar na Amazon" com a tag | não | sim |

Por que o Mercado Livre e a Amazon são assim:
- A busca pública da API do Mercado Livre (`/sites/MLB/search`) responde **403** para aplicativos desde o
  começo de 2026, e o link de afiliado do ML só sai pelo painel (Ferramentas > Gerador de links).
- A API de produtos da Amazon (a antiga PA-API 5, agora **Creators API**) só libera depois que a conta de
  Associado faz vendas. Quando liberar, dá para acrescentar o preço automático da Amazon.

## Subir no site (Hostinger)

1. No PC, rode `./server/empacotar.sh`: ele monta `dist/techie/` (com o `parts.json` do app) e o `dist/techie-coletor.zip`.
2. No painel da Hostinger: **Gerenciador de arquivos** > `public_html` > crie a pasta `techie` e envie o zip
   (extraia lá dentro). A raiz do site continua com o relay do HOLO.
3. Copie `config.example.php` para `config.php` e preencha as chaves (veja abaixo). Invente uma `cron_key` longa.
4. (Opcional) Copie `ofertas-manuais.example.json` para `ofertas-manuais.json` com os seus links do Mercado Livre.
5. **Avançado > Cron Jobs**: crie um cron diário (ex.: 06:00) com o comando
   `/usr/bin/php /home/SEU_USUARIO/public_html/techie/coletar.php`
   (ou, se o painel só aceitar URL: `https://piphin.online/techie/coletar.php?chave=SUA_CRON_KEY`).
6. Teste uma peça: no terminal SSH, `php coletar.php --so=rtx-4060`, ou pela URL com `&so=rtx-4060`.
   Depois abra `https://piphin.online/techie/api.php?index=1`: tem que aparecer o JSON com os preços.

O coletor cria a pasta `techie-data/` (com `.htaccess` que bloqueia o acesso pelo navegador). O `config.php`, o
`parts.json` e o `ofertas-manuais.json` também ficam bloqueados pelo `.htaccess` desta pasta.

## Chaves

- **AliExpress Portals**: portals.aliexpress.com > cadastro > *Ferramentas / API* > crie o app (App Key e App Secret)
  e copie o **Tracking ID**. Sem o Tracking ID a API devolve lista vazia.
- **Awin**: depois de aprovado pela loja, *Toolbox > Create-a-Feed* > escolha a loja e o formato CSV (gzip) e copie a URL.
- **Lomadee** (ou outro feed CSV): coloque a URL e, em `columns`, os nomes das colunas de título, preço, link e foto.
- **Amazon**: a tag de Associado (termina em `-20`).

## Como o coletor acha a peça certa

Para cada peça ele busca pelo nome (ou pelo campo `q` do `parts.json`) e só aceita anúncios que tenham **todos**
os números do modelo e nenhuma variante a mais. Uma "RTX 4060" não pega anúncio de "4060 Ti", um "Ryzen 5 7600"
não pega "7600X" e uma memória de 16 GB não pega a de 8 GB. Acessórios ("cooler para", "suporte", "notebook")
ficam de fora, assim como preços abaixo de 40% da mediana das ofertas. Peças genéricas (gabinete "típico", coolers
box) têm `"noprice": true` e não são coletadas.

## Aviso de afiliado

O app mostra em toda a aba de preços que os links são de afiliado. Mantenha isso: é exigência do CONAR, do
Mercado Livre, da Amazon e das redes de afiliados.

## Testar no seu PC

```bash
php tests/test_coletor.php
php -S 127.0.0.1:8099 -t dist/techie     # depois de rodar o coletor
ARASAKA_TECHIE_PRECOS=http://127.0.0.1:8099/api.php arasaka-techie
```
