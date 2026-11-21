#!/usr/bin/env bash
# ARASAKA TECHIE // monta a pasta do coletor de precos para subir no site (ex.: public_html/techie/ do piphin.online).
#   ./server/empacotar.sh        -> dist/techie/ e dist/techie-coletor.zip
# Leva junto o parts.json do app, para o coletor saber quais pecas procurar. Rode de novo quando a base de pecas mudar.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/dist/techie"
rm -rf "$OUT" "$ROOT/dist/techie-coletor.zip"
mkdir -p "$OUT"
cp "$ROOT"/server/techie/{api.php,coletar.php,lib.php,config.example.php,ofertas-manuais.example.json,.htaccess,LEIA-ME.md} "$OUT/"
cp "$ROOT/arasaka_techie/data/parts.json" "$OUT/parts.json"
if command -v zip >/dev/null; then (cd "$ROOT/dist" && zip -qr techie-coletor.zip techie); else python3 -m zipfile -c "$ROOT/dist/techie-coletor.zip" "$OUT"; fi
echo "■ pronto: $OUT  (e dist/techie-coletor.zip)"
echo "  No servidor: crie config.php a partir do config.example.php. O config.php e os dados coletados nao sao sobrescritos pelo zip."
