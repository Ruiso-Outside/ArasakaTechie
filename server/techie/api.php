<?php
/*
 * ARASAKA TECHIE // API de precos que o app le (so leitura, JSON).
 *   GET api.php?index=1         menor preco de hoje, loja, foto e veredito de cada peca
 *   GET api.php?part=<id>       historico (um ponto por dia) e as ofertas da peca, com os links de afiliado
 *   GET api.php                 status
 */

declare(strict_types=1);
require __DIR__ . '/lib.php';

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: public, max-age=1800');

function out($v, int $code = 200): void {
    http_response_code($code);
    echo json_encode($v, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

if (isset($_GET['index'])) {
    $idx = read_json(data_dir() . '/index.json', null);
    out($idx ?: ['updated' => null, 'parts' => new stdClass()], $idx ? 200 : 503);
}
if (isset($_GET['part'])) {
    $pid = (string)$_GET['part'];
    if (!preg_match('/^[a-z0-9][a-z0-9.\-]{0,63}$/', $pid)) {
        out(['error' => 'id invalido'], 400);
    }
    $p = read_json(data_dir('parts') . "/$pid.json", null);
    out($p ?: ['error' => 'sem dados'], $p ? 200 : 404);
}
$idx = read_json(data_dir() . '/index.json', []);
out(['servico' => 'Arasaka Techie // precos', 'atualizado' => $idx['updated'] ?? null, 'pecas' => count($idx['parts'] ?? [])]);
