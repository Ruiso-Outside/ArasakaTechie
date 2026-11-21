<?php
// ARASAKA TECHIE // configuracao do coletor. Copie para config.php (no servidor) e preencha.
// O config.php NAO vai para o GitHub (tem chaves secretas).
return [
    // senha para rodar o coletor pela URL (coletar.php?chave=...). Invente uma longa.
    'cron_key' => '',

    // AliExpress Portals > Ferramentas > API: App Key, App Secret e o seu Tracking ID
    'aliexpress' => ['app_key' => '', 'app_secret' => '', 'tracking_id' => ''],

    // Amazon Associados: a sua tag (ex.: "seunome-20"). Gera links de busca com a tag (sem preco).
    'amazon' => ['tag' => ''],

    // Feeds de produtos (CSV ou CSV .gz). Na Awin: Toolbox > Create-a-Feed, escolha a loja (KaBuM!, Pichau...)
    // e cole a URL do feed. Os links do feed ja saem com o seu ID de afiliado.
    // Na Lomadee (ou outro feed), diga quais colunas tem titulo, preco, link e foto em "columns".
    'feeds' => [
        // ['store' => 'KaBuM!', 'url' => 'https://productdata.awin.com/datafeed/download/apikey/SUA_CHAVE/.../format/csv/compression/gzip/'],
        // ['store' => 'Loja X', 'url' => 'https://.../feed.csv', 'columns' => ['title' => 'nome', 'price' => 'preco', 'url' => 'link', 'image' => 'imagem']],
    ],
];
