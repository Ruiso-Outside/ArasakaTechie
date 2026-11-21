<?php
/*
 * ARASAKA TECHIE // coletor diario de precos.
 *
 *   php coletar.php                 coleta todas as pecas (rode 1x por dia pelo cron da hospedagem)
 *   php coletar.php --so=rtx-4060   so uma peca (para testar a configuracao)
 *   php coletar.php --limite=20     so as 20 primeiras
 * Pelo navegador (se o cron da hospedagem so aceitar URL): https://seu-site/techie/coletar.php?chave=<cron_key do config.php>
 */

declare(strict_types=1);
require __DIR__ . '/lib.php';

$cli = PHP_SAPI === 'cli';
$cfg = techie_config();
if (!$cli) {
    $key = (string)($cfg['cron_key'] ?? '');
    if ($key === '' || !hash_equals($key, (string)($_GET['chave'] ?? ''))) {
        http_response_code(403);
        exit("proibido\n");
    }
    header('Content-Type: text/plain; charset=utf-8');
}
$opt = $cli ? getopt('', ['so:', 'limite:']) : ['so' => $_GET['so'] ?? null];
@set_time_limit(0);
@ini_set('memory_limit', '512M');

$lock = fopen(data_dir() . '/coleta.lock', 'c');
if (!flock($lock, LOCK_EX | LOCK_NB)) {
    exit("outra coleta ja esta rodando\n");
}

$parts = load_parts();
if (!$parts) {
    exit("parts.json nao encontrado ao lado do coletar.php\n");
}
if (!empty($opt['so'])) {
    $parts = array_intersect_key($parts, [$opt['so'] => 1]);
}
if (!empty($opt['limite'])) {
    $parts = array_slice($parts, 0, (int)$opt['limite'], true);
}

$today = date('Y-m-d');
$stamp = date('Y-m-d H:i');
$manual = read_json(__DIR__ . '/ofertas-manuais.json', []);
$feedRows = [];
foreach ($cfg['feeds'] ?? [] as $feed) {
    if (!empty($feed['url'])) {
        $rows = feed_rows($feed);
        echo '■ feed ' . ($feed['store'] ?? $feed['url']) . ': ' . count($rows) . " produtos\n";
        $feedRows = array_merge($feedRows, $rows);
    }
}

$idxFile = data_dir() . '/index.json';
$index = read_json($idxFile, ['parts' => []]);
$n = 0;
foreach ($parts as $pid => $p) {
    if (!empty($p['noprice'])) {
        continue;
    }
    $offers = merge_offers([
        aliexpress_offers($p, $cfg),
        feed_offers($p, $feedRows),
        manual_offers($p, $manual, $today),
        amazon_offer($p, $cfg),
    ]);
    $index['parts'][$pid] = store_part($pid, $offers, $today, $stamp);
    $n++;
    $best = $index['parts'][$pid]['price'];
    echo sprintf("%-22s %s  (%d oferta(s))\n", $pid, $best !== null ? 'R$ ' . number_format($best, 2, ',', '.') : 'sem preco', count($offers));
    if (!empty($cfg['aliexpress']['app_key'])) {
        usleep(300000);     // gentil com a API
    }
}
$index['updated'] = $stamp;
write_json($idxFile, $index);
echo "■ $n peca(s) atualizada(s) em $stamp\n";
