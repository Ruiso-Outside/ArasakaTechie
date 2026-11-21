<?php
// Coletor de precos (server/techie): casar titulo com peca, precos, feeds, AliExpress, historico e veredito.
//   php tests/test_coletor.php
declare(strict_types=1);
$tmp = sys_get_temp_dir() . '/techie-test-' . getmypid();
putenv("TECHIE_DATA=$tmp");
require __DIR__ . '/../server/techie/lib.php';

$fails = 0;
function ok(bool $c, string $msg): void { global $fails; if (!$c) { $fails++; echo "FALHOU: $msg\n"; } }

$db = json_decode(file_get_contents(__DIR__ . '/../arasaka_techie/data/parts.json'), true);
$P = [];
foreach (['cpu', 'gpu', 'mobo', 'ram', 'storage', 'psu', 'cooler', 'case'] as $c) {
    foreach ($db[$c] as $p) { $p['cat'] = $c; $P[$p['id']] = $p; }
}

// casar titulo
ok(title_matches($P['rtx-4060'], 'Placa de Vídeo RTX 4060 Ventus 2X Black 8GB GDDR6 MSI'), '4060 casa');
ok(!title_matches($P['rtx-4060'], 'Placa de Vídeo MSI RTX 4060 Ti Ventus 2X 8GB'), '4060 nao casa com 4060 Ti');
ok(!title_matches($P['rtx-4060'], 'Placa RTX 4060TI 8GB'), '4060 nao casa com 4060TI grudado');
ok(title_matches($P['rtx-4060ti8'], 'Placa de Vídeo MSI RTX 4060 Ti Ventus 2X 8GB'), '4060 Ti 8 GB casa');
ok(!title_matches($P['rtx-4060ti8'], 'RTX 4060 Ti 16GB Gaming'), '4060 Ti 8 GB nao casa com 16 GB');
ok(!title_matches($P['rtx-4060'], 'Cooler para RTX 4060 ventoinha reposição'), 'acessorio nao casa');
ok(title_matches($P['r5-7600'], 'Processador AMD Ryzen 5 7600, 3.8GHz (5.1GHz Turbo), AM5'), '7600 casa');
ok(!title_matches($P['r5-7600'], 'Processador AMD Ryzen 5 7600X AM5'), '7600 nao casa com 7600X');
ok(title_matches($P['i5-13400f'], 'Processador Intel Core i5-13400F 2.5GHz LGA1700'), 'i5-13400F casa');
ok(!title_matches($P['i5-13400f'], 'Processador Intel Core i5-13400 2.5GHz'), '13400F nao casa com 13400');
ok(title_matches($P['e5-2666v3'], 'Intel Xeon E5 2666 V3 CPU Processador 2.9GHz 10 Núcleos LGA 2011-3'), 'xeon casa');
ok(!title_matches($P['e5-2666v3'], 'Intel Xeon E5 2667 V3 LGA2011-3'), 'xeon 2667 nao casa com 2666');
ok(title_matches($P['ddr4-1x16-3200'], 'Memória Kingston Fury Beast 16GB DDR4 3200MHz CL16 KF432C16BB1/16'), 'ram casa');
ok(!title_matches($P['ddr4-1x16-3200'], 'Memória Kingston Fury Beast 8GB DDR4 3200MHz CL16'), 'ram de outro tamanho nao casa');
ok(title_matches($P['rtx-3060'], 'Placa de Video Galax RTX 3060 12GB GDDR6'), '3060 12 GB casa');

// precos
ok(abs(parse_price('1.799,90') - 1799.90) < 0.001, 'preco BR');
ok(abs(parse_price('R$ 2.399') - 2399) < 0.001, 'preco com milhar');
ok(abs(parse_price('2399.90') - 2399.90) < 0.001, 'preco com ponto');
ok(abs(parse_price('1,234.50') - 1234.50) < 0.001, 'preco US');
ok(parse_price('') === 0.0, 'preco vazio');

// feed (Awin)
$rows = parse_feed(__DIR__ . '/fixtures/coletor/awin.csv', ['url' => 'x']);
ok(count($rows) === 7, 'feed: 7 linhas');
$o = feed_offers($P['rtx-4060'], $rows);
ok(count($o) === 1 && abs($o[0]['price'] - 1799.90) < 0.01 && $o[0]['store'] === 'KaBuM!', 'feed: so a 4060 certa');
$o = feed_offers($P['r5-7600'], $rows);
ok(count($o) === 1 && str_starts_with($o[0]['url'], 'https://'), 'feed: link http e 7600X ficam de fora');

// AliExpress (resposta de exemplo, sem rede)
$cfg = ['aliexpress' => ['app_key' => '123', 'app_secret' => 'segredo', 'tracking_id' => 'techie']];
$asked = '';
$o = aliexpress_offers($P['e5-2666v3'], $cfg, function ($url) use (&$asked) { $asked = $url; return file_get_contents(__DIR__ . '/fixtures/coletor/aliexpress.json'); });
ok(count($o) === 1 && $o[0]['price'] == 89.90 && $o[0]['url'] === 'https://s.click.aliexpress.com/e/_abc', 'aliexpress: so o xeon certo, sem o kit');
parse_str(parse_url($asked, PHP_URL_QUERY), $q);
ok($q['method'] === 'aliexpress.affiliate.product.query' && $q['tracking_id'] === 'techie' && strlen($q['sign']) === 64, 'aliexpress: parametros e assinatura');
$sig = $q['sign']; unset($q['sign']);
ok(aliexpress_sign($q, 'segredo') === $sig, 'aliexpress: assinatura confere');
ok(aliexpress_offers($P['e5-2666v3'], [], fn($u) => '') === [], 'aliexpress: sem config nao chama');

// manual, amazon e juncao
$m = manual_offers($P['rtx-4060'], [['part' => 'rtx-4060', 'store' => 'Mercado Livre', 'url' => 'https://mercadolivre.com/sec/abc', 'price' => 1750, 'date' => '2026-11-19'],
                                    ['part' => 'rtx-4060', 'store' => 'Velha', 'url' => 'https://x.example/a', 'price' => 10, 'date' => '2026-01-01'],
                                    ['part' => 'rtx-4060', 'url' => 'javascript:alert(1)']], '2026-11-20');
ok(count($m) === 2 && $m[0]['price'] == 1750 && $m[1]['price'] === null, 'manual: preco velho vira so link; link ruim some');
$a = amazon_offer($P['rtx-4060'], ['amazon' => ['tag' => 'arasaka-20']]);
ok(count($a) === 1 && str_contains($a[0]['url'], 'tag=arasaka-20') && $a[0]['price'] === null, 'amazon: link de busca com tag');
ok(amazon_offer($P['rtx-4060'], ['amazon' => ['tag' => 'x" onload']]) === [], 'amazon: tag invalida');
$all = merge_offers([[['store' => 'A', 'title' => 't', 'price' => 1900.0, 'url' => 'https://a', 'image' => '']], $m, $a,
                     [['store' => 'B', 'title' => 'acessorio', 'price' => 50.0, 'url' => 'https://b', 'image' => ''], ['store' => 'C', 'title' => 't', 'price' => 1800.0, 'url' => 'https://c', 'image' => '']]]);
ok($all[0]['price'] == 1750 && end($all)['price'] === null && !in_array('https://b', array_column($all, 'url'), true), 'juncao: mais barata primeiro, sem preco no fim, sem preco absurdo');

// historico e veredito
$h = [];
for ($i = 100; $i >= 1; $i--) { $h = add_history($h, date('Y-m-d', strtotime("2026-11-20 -$i days")), 1000 + ($i % 10) * 20); }
$h = add_history($h, '2026-11-20', 990);
$h = add_history($h, '2026-11-20', 1200);
ok(end($h)['min'] == 990 && count($h) === 101, 'historico: um ponto por dia, fica o menor');
ok(verdict_level($h, 990.0, '2026-11-20') === 'baixo', 'veredito baixo');
ok(verdict_level($h, 1185.0, '2026-11-20') === 'alto', 'veredito alto');
ok(verdict_level($h, 1090.0, '2026-11-20') === 'normal', 'veredito normal');
ok(verdict_level(array_slice($h, -3), 990.0, '2026-11-20') === 'curto', 'veredito com historico curto');

// gravar e indice
$row = store_part('rtx-4060', $all, '2026-11-20', '2026-11-20 06:00');
$saved = read_json("$tmp/parts/rtx-4060.json");
ok($row['price'] == 1750 && $row['store'] === 'Mercado Livre' && $saved['history'][0]['min'] == 1750 && count($saved['offers']) === count($all), 'store_part');
ok(is_file("$tmp/.htaccess"), 'pasta de dados protegida');
ok(required_tokens($P['office-matx']) !== [] || !empty($P['office-matx']['noprice']), 'pecas genericas ficam fora da coleta');

array_map('unlink', glob("$tmp/parts/*"));
@rmdir("$tmp/parts"); @unlink("$tmp/.htaccess"); @rmdir($tmp);
if ($fails) { echo "$fails teste(s) falharam\n"; exit(1); }
echo "■ coletor: tudo certo\n";
