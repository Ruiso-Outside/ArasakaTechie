<?php
/*
 * ARASAKA TECHIE // coletor de precos: funcoes comuns (casar oferta com peca, historico, indice, lojas).
 *
 * Fluxo: o cron roda coletar.php 1x por dia -> para cada peca de parts.json, pergunta as lojas configuradas
 * (AliExpress pela API de afiliados, feeds de produtos da Awin/Lomadee, links fixos do Mercado Livre e da
 * Amazon que voce cadastrar) -> guarda o menor preco do dia no historico -> api.php serve isso para o app.
 */

declare(strict_types=1);

const TECHIE_UA = 'ArasakaTechieColetor/1.1 (+https://piphin.online/techie/)';
const MAX_OFFERS = 12;
const HISTORY_DAYS = 400;

function techie_config(): array {
    $f = __DIR__ . '/config.php';
    $cfg = is_file($f) ? require $f : [];
    return is_array($cfg) ? $cfg : [];
}

function data_dir(string $sub = ''): string {
    $base = getenv('TECHIE_DATA') ?: __DIR__ . '/techie-data';
    $d = $sub === '' ? $base : "$base/$sub";
    if (!is_dir($d)) {
        @mkdir($d, 0700, true);
    }
    if (!is_file("$base/.htaccess")) {
        @file_put_contents("$base/.htaccess", "Require all denied\nDeny from all\n");
    }
    return $d;
}

function read_json(string $f, $default = null) {
    if (!is_file($f)) {
        return $default;
    }
    $v = json_decode((string)file_get_contents($f), true);
    return $v === null ? $default : $v;
}

function write_json(string $f, $v): void {
    $tmp = $f . '.tmp' . getmypid();
    file_put_contents($tmp, json_encode($v, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    rename($tmp, $f);
}

function load_parts(): array {
    $db = read_json(__DIR__ . '/parts.json', []);
    $out = [];
    foreach (['cpu', 'gpu', 'mobo', 'ram', 'storage', 'psu', 'cooler', 'case'] as $cat) {
        foreach ($db[$cat] ?? [] as $p) {
            $p['cat'] = $cat;
            $out[$p['id']] = $p;
        }
    }
    return $out;
}

// ----------------------------------------------------------------------------- casar titulo com peca
function norm_text(string $s): string {
    $s = mb_strtolower($s, 'UTF-8');
    $t = @iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $s);
    $s = $t !== false ? $t : $s;
    $s = preg_replace('/[^a-z0-9+]+/', ' ', $s);
    $s = preg_replace('/(\d)(gb|tb|w|mhz|mm|mts)\b/', '$1 $2', $s);   // "16gb" -> "16 gb"
    return ' ' . trim(preg_replace('/\s+/', ' ', $s)) . ' ';
}

// palavras que mudam o modelo: "RTX 4060" nao pode casar com "RTX 4060 Ti"
const VARIANTS = ['ti', 'super', 'xt', 'xtx', 'x3d', 'k', 'kf', 'f', 'g', 'x', 'gre', 'le', 'v2', 'v3', 'v4', 'pro', 'max', 'plus', 'se', 'oc'];
const STOPWORDS = ['amd', 'intel', 'nvidia', 'geforce', 'radeon', 'core', 'ryzen', 'xeon', 'arc', 'the', 'de', 'gb', 'tb', 'e', 'com', 'sem'];
const NEG = [
    'cpu' => ['notebook', 'laptop', 'cooler para', 'kit placa', 'combo', 'usado com defeito', 'pc gamer', 'computador'],
    'gpu' => ['notebook', 'laptop', 'cooler para', 'ventoinha', 'fan para', 'backplate', 'suporte', 'riser', 'bracket', 'pc gamer', 'computador', 'waterblock'],
    'mobo' => ['kit ', 'combo', 'com processador', 'espelho', 'tampa', 'pc gamer'],
    'ram' => ['notebook', 'sodimm', 'so dimm', 'laptop'],
    'storage' => ['case para', 'gaveta', 'adaptador', 'externo', 'portatil', 'case usb'],
    'psu' => ['cabo', 'extensor', 'adaptador', 'notebook', 'carregador'],
    'cooler' => ['pasta termica', 'suporte', 'parafuso', 'bracket', 'kit de montagem'],
    'case' => ['vidro lateral', 'pe de borracha', 'filtro', 'adesivo'],
];

function part_query(array $p): string {
    if (!empty($p['q'])) {
        return $p['q'];
    }
    $name = preg_replace('/\([^)]*\)/', ' ', $p['name']);
    $name = str_replace(['"', '·'], ' ', $name);
    return trim(preg_replace('/\s+/', ' ', $name));
}

/** Tokens obrigatorios do nome: os que tem numero (modelo) e os que vem logo depois (variantes). */
function required_tokens(array $p): array {
    $words = array_values(array_filter(explode(' ', trim(norm_text(part_query($p))))));
    $req = [];
    foreach ($words as $i => $w) {
        if (in_array($w, STOPWORDS, true)) {
            continue;
        }
        if (preg_match('/\d/', $w) || in_array($w, VARIANTS, true) || ($p['cat'] !== 'cpu' && $p['cat'] !== 'gpu' && strlen($w) >= 3)) {
            $req[] = $w;
        }
    }
    return array_values(array_unique($req));
}

function title_matches(array $p, string $title): bool {
    $t = norm_text($title);
    foreach (NEG[$p['cat']] ?? [] as $bad) {
        if (str_contains($t, ' ' . trim(norm_text($bad)) . ' ') || str_contains($t, norm_text($bad))) {
            return false;
        }
    }
    $req = required_tokens($p);
    if (!$req) {
        return false;
    }
    foreach ($req as $w) {
        if (!str_contains($t, " $w ")) {
            return false;
        }
    }
    // variante a mais no titulo logo depois do numero do modelo ("4060 ti" quando a peca e "4060")
    $mine = array_flip($req);
    foreach ($req as $w) {
        if (!preg_match('/\d/', $w)) {
            continue;
        }
        if (preg_match_all('/ ' . preg_quote($w, '/') . ' ([a-z0-9]+) /', $t, $m)) {
            foreach ($m[1] as $next) {
                if (in_array($next, VARIANTS, true) && !isset($mine[$next])) {
                    return false;
                }
            }
        }
        // "4060ti" grudado
        foreach (VARIANTS as $v) {
            if (!isset($mine[$v]) && str_contains($t, " $w$v ")) {
                return false;
            }
        }
    }
    if (($p['cat'] === 'gpu' || $p['cat'] === 'ram') && isset($p['vram'])) {
        if (preg_match('/ (\d+) ?gb /', $t, $m) && (int)$m[1] !== (int)$p['vram'] && in_array((int)$m[1], [2, 3, 4, 6, 8, 10, 11, 12, 16, 20, 24, 32], true)) {
            return false;
        }
    }
    if ($p['cat'] === 'ram' && isset($p['gb']) && preg_match('/ (\d+) ?gb /', $t, $m) && (int)$m[1] !== (int)$p['gb']) {
        return false;
    }
    return true;
}

/** Tira precos absurdos (acessorio, anuncio errado): abaixo de 40% da mediana das ofertas. */
function drop_outliers(array $offers): array {
    $ps = array_values(array_filter(array_map(fn($o) => $o['price'], $offers), fn($v) => $v !== null && $v > 0));
    if (count($ps) < 3) {
        return $offers;
    }
    sort($ps);
    $med = $ps[intdiv(count($ps), 2)];
    return array_values(array_filter($offers, fn($o) => $o['price'] === null || ($o['price'] >= $med * 0.4 && $o['price'] <= $med * 3)));
}

// ----------------------------------------------------------------------------- historico e indice
function add_history(array $hist, string $day, float $min): array {
    $byDay = [];
    foreach ($hist as $h) {
        $byDay[$h['d']] = (float)$h['min'];
    }
    $byDay[$day] = isset($byDay[$day]) ? min($byDay[$day], $min) : $min;
    ksort($byDay);
    $cut = date('Y-m-d', strtotime("$day -" . HISTORY_DAYS . ' days'));
    $out = [];
    foreach ($byDay as $d => $v) {
        if ($d >= $cut) {
            $out[] = ['d' => $d, 'min' => round($v, 2)];
        }
    }
    return $out;
}

/** Mesmo criterio do app (prices.verdict): baixo, normal, alto ou curto, olhando os ultimos 90 dias. */
function verdict_level(array $hist, ?float $current, string $today): string {
    if ($current === null) {
        return 'curto';
    }
    $cut = date('Y-m-d', strtotime("$today -90 days"));
    $vals = array_map(fn($h) => (float)$h['min'], array_values(array_filter($hist, fn($h) => $h['d'] >= $cut && $h['min'] > 0)));
    if (count($vals) < 7) {
        return 'curto';
    }
    $below = count(array_filter($vals, fn($v) => $v < $current));
    $pct = 100 * $below / count($vals);
    if ($pct <= 25 || $current <= min($vals) * 1.02) {
        return 'baixo';
    }
    return $pct >= 75 ? 'alto' : 'normal';
}

function safe_https(?string $u): bool {
    return is_string($u) && strlen($u) < 2000 && preg_match('#^https://[^\s/]+#', $u) === 1;
}

// ----------------------------------------------------------------------------- HTTP
function http_get(string $url, int $timeout = 25, ?string $saveTo = null): ?string {
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        $fh = null;
        $opts = [CURLOPT_FOLLOWLOCATION => true, CURLOPT_TIMEOUT => $timeout, CURLOPT_USERAGENT => TECHIE_UA, CURLOPT_ENCODING => ''];
        if ($saveTo) {
            $fh = fopen($saveTo, 'wb');
            $opts[CURLOPT_FILE] = $fh;
            $opts[CURLOPT_TIMEOUT] = 600;
        } else {
            $opts[CURLOPT_RETURNTRANSFER] = true;
        }
        curl_setopt_array($ch, $opts);
        $r = curl_exec($ch);
        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        if ($fh) {
            fclose($fh);
        }
        if ($code < 200 || $code >= 300) {
            return null;
        }
        return $saveTo ? '' : (string)$r;
    }
    $ctx = stream_context_create(['http' => ['timeout' => $timeout, 'header' => 'User-Agent: ' . TECHIE_UA . "\r\n"]]);
    $r = @file_get_contents($url, false, $ctx);
    if ($r === false) {
        return null;
    }
    if ($saveTo) {
        file_put_contents($saveTo, $r);
        return '';
    }
    return $r;
}

// ----------------------------------------------------------------------------- lojas
/** AliExpress Portals (API de afiliados): busca por palavra-chave e devolve link de afiliado e foto. */
function aliexpress_sign(array $params, string $secret): string {
    ksort($params);
    $s = '';
    foreach ($params as $k => $v) {
        $s .= $k . $v;
    }
    return strtoupper(hash_hmac('sha256', $s, $secret));
}

function aliexpress_offers(array $p, array $cfg, ?callable $get = null): array {
    $ae = $cfg['aliexpress'] ?? [];
    if (empty($ae['app_key']) || empty($ae['app_secret']) || empty($ae['tracking_id'])) {
        return [];
    }
    $params = [
        'method' => 'aliexpress.affiliate.product.query', 'app_key' => $ae['app_key'], 'sign_method' => 'sha256',
        'timestamp' => (string)round(microtime(true) * 1000), 'keywords' => part_query($p), 'target_currency' => 'BRL',
        'target_language' => 'PT', 'ship_to_country' => 'BR', 'tracking_id' => $ae['tracking_id'], 'page_size' => '20',
        'sort' => 'SALE_PRICE_ASC', 'fields' => 'product_title,target_sale_price,promotion_link,product_main_image_url',
    ];
    $params['sign'] = aliexpress_sign($params, $ae['app_secret']);
    $url = 'https://api-sg.aliexpress.com/sync?' . http_build_query($params);
    $raw = $get ? $get($url) : http_get($url);
    $j = json_decode((string)$raw, true);
    $list = $j['aliexpress_affiliate_product_query_response']['resp_result']['result']['products']['product'] ?? [];
    $out = [];
    foreach ($list as $it) {
        $title = (string)($it['product_title'] ?? '');
        $price = parse_price((string)($it['target_sale_price'] ?? '0'));
        $link = $it['promotion_link'] ?? '';
        if ($price > 0 && safe_https($link) && title_matches($p, $title)) {
            $out[] = ['store' => 'AliExpress', 'title' => $title, 'price' => round($price, 2), 'url' => $link,
                      'image' => safe_https($it['product_main_image_url'] ?? '') ? $it['product_main_image_url'] : ''];
        }
    }
    return $out;
}

/**
 * Feeds de produtos (CSV, pode vir em .gz) da Awin e da Lomadee: um arquivo por loja, baixado 1x por dia.
 * As colunas padrao sao as da Awin; para outro feed, informe "columns" no config.
 */
function feed_rows(array $feed): array {
    $dir = data_dir('feeds');
    $key = substr(sha1($feed['url']), 0, 16);
    $file = "$dir/$key.csv";
    $gz = str_ends_with(parse_url($feed['url'], PHP_URL_PATH) ?? '', '.gz') || !empty($feed['gzip']);
    if (!is_file($file) || filemtime($file) < time() - 20 * 3600) {
        $tmp = "$file.dl";
        if (http_get($feed['url'], 600, $tmp) === null) {
            @unlink($tmp);
        } else {
            if ($gz) {
                $in = gzopen($tmp, 'rb');
                $out = fopen($file, 'wb');
                while (!gzeof($in)) {
                    fwrite($out, gzread($in, 1 << 16));
                }
                gzclose($in);
                fclose($out);
                unlink($tmp);
            } else {
                rename($tmp, $file);
            }
        }
    }
    return is_file($file) ? parse_feed($file, $feed) : [];
}

function parse_feed(string $file, array $feed): array {
    $cols = ($feed['columns'] ?? []) + ['title' => 'product_name', 'price' => 'search_price', 'url' => 'aw_deep_link',
                                        'image' => 'aw_image_url', 'store' => 'merchant_name'];
    $fh = fopen($file, 'rb');
    $first = fgets($fh);
    $sep = substr_count($first, "\t") > substr_count($first, ',') ? "\t" : (substr_count($first, ';') > substr_count($first, ',') ? ';' : ',');
    $head = array_map(fn($h) => trim($h, " \"\xEF\xBB\xBF\r\n"), str_getcsv(trim($first), $sep));
    $ix = [];
    foreach ($cols as $k => $name) {
        $pos = array_search($name, $head, true);
        $ix[$k] = $pos === false ? null : $pos;
    }
    $rows = [];
    if ($ix['title'] === null || $ix['price'] === null || $ix['url'] === null) {
        fclose($fh);
        return [];
    }
    while (($r = fgetcsv($fh, 0, $sep)) !== false) {
        $price = parse_price((string)($r[$ix['price']] ?? ''));
        if ($price <= 0) {
            continue;
        }
        $rows[] = ['title' => (string)$r[$ix['title']], 'price' => $price, 'url' => (string)$r[$ix['url']],
                   'image' => $ix['image'] !== null ? (string)($r[$ix['image']] ?? '') : '',
                   'store' => $feed['store'] ?? ($ix['store'] !== null ? (string)($r[$ix['store']] ?? 'Loja') : 'Loja')];
    }
    fclose($fh);
    return $rows;
}

/** "1.234,56", "1234,56", "1234.56", "R$ 1.234" -> float */
function parse_price(string $raw): float {
    $s = preg_replace('/[^\d,.]/', '', $raw);
    if ($s === '') {
        return 0.0;
    }
    if (str_contains($s, ',') && str_contains($s, '.')) {
        $s = strrpos($s, ',') > strrpos($s, '.') ? str_replace(['.', ','], ['', '.'], $s) : str_replace(',', '', $s);
    } elseif (str_contains($s, ',')) {
        $s = str_replace(',', '.', $s);
    } elseif (substr_count($s, '.') > 1 || preg_match('/\.\d{3}$/', $s)) {
        $s = str_replace('.', '', $s);
    }
    return (float)$s;
}

function feed_offers(array $p, array $rows): array {
    $out = [];
    foreach ($rows as $r) {
        if (safe_https($r['url']) && title_matches($p, $r['title'])) {
            $out[] = ['store' => $r['store'], 'title' => $r['title'], 'price' => round($r['price'], 2), 'url' => $r['url'],
                      'image' => safe_https($r['image']) ? $r['image'] : ''];
        }
    }
    return $out;
}

/**
 * Links que voce cadastra em ofertas-manuais.json (Mercado Livre: gere o link no painel de afiliados; o preco e opcional).
 * [{"part": "rtx-4060", "store": "Mercado Livre", "url": "https://mercadolivre.com/sec/xxxx", "price": 1799.9, "date": "2026-11-20"}]
 * Preco com mais de 3 dias deixa de contar como preco do dia (vira so "ver na loja").
 */
function manual_offers(array $p, array $manual, string $today): array {
    $out = [];
    foreach ($manual as $m) {
        if (($m['part'] ?? '') !== $p['id'] || !safe_https($m['url'] ?? '')) {
            continue;
        }
        $fresh = isset($m['price'], $m['date']) && $m['date'] >= date('Y-m-d', strtotime("$today -3 days"));
        $out[] = ['store' => $m['store'] ?? 'Loja', 'title' => $m['title'] ?? $p['name'], 'price' => $fresh ? round((float)$m['price'], 2) : null,
                  'url' => $m['url'], 'image' => safe_https($m['image'] ?? '') ? $m['image'] : ''];
    }
    return $out;
}

/** Amazon: link de busca com a sua tag de associado (sem preco: a API nova da Amazon pede vendas antes de liberar). */
function amazon_offer(array $p, array $cfg): array {
    $tag = $cfg['amazon']['tag'] ?? '';
    if ($tag === '' || !preg_match('/^[A-Za-z0-9\-]{3,40}$/', $tag)) {
        return [];
    }
    $url = 'https://www.amazon.com.br/s?' . http_build_query(['k' => part_query($p), 'tag' => $tag]);
    return [['store' => 'Amazon', 'title' => 'Buscar "' . part_query($p) . '" na Amazon', 'price' => null, 'url' => $url, 'image' => '']];
}

/** Junta as ofertas de uma peca, mais barata primeiro (as sem preco no fim). */
function merge_offers(array $lists): array {
    $all = array_merge(...array_values($lists ?: [[]]));
    $all = drop_outliers($all);
    usort($all, fn($a, $b) => [$a['price'] === null, $a['price'] ?? 0] <=> [$b['price'] === null, $b['price'] ?? 0]);
    $seen = [];
    $out = [];
    foreach ($all as $o) {
        $k = $o['url'];
        if (isset($seen[$k])) {
            continue;
        }
        $seen[$k] = 1;
        $out[] = $o;
        if (count($out) >= MAX_OFFERS) {
            break;
        }
    }
    return $out;
}

/** Atualiza o arquivo da peca e devolve a linha do indice. */
function store_part(string $pid, array $offers, string $today, string $stamp): array {
    $f = data_dir('parts') . "/$pid.json";
    $old = read_json($f, []);
    $hist = $old['history'] ?? [];
    $priced = array_values(array_filter($offers, fn($o) => $o['price'] !== null));
    $min = $priced ? $priced[0]['price'] : null;
    if ($min !== null) {
        $hist = add_history($hist, $today, (float)$min);
    }
    write_json($f, ['part' => $pid, 'updated' => $stamp, 'history' => $hist, 'offers' => $offers]);
    $img = '';
    foreach ($offers as $o) {
        if ($o['image'] !== '') {
            $img = $o['image'];
            break;
        }
    }
    return ['price' => $min, 'store' => $priced ? $priced[0]['store'] : ($offers[0]['store'] ?? ''), 'image' => $img ?: ($old['image'] ?? ''),
            'verdict' => verdict_level($hist, $min !== null ? (float)$min : null, $today)];
}
