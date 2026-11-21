#!/usr/bin/env bash
# ARASAKA TECHIE // desinstalador
set -uo pipefail
APP_ID=arasaka-techie
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_ID"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
rm -f "$HOME/.local/bin/$APP_ID" "$APPS/$APP_ID.desktop" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps/$APP_ID.svg" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/icons/Arasaka/scalable/apps/$APP_ID.svg"
rm -rf "$DATA/app" "$DATA/venv" "${XDG_CACHE_HOME:-$HOME/.cache}/$APP_ID"
update-desktop-database -q "$APPS" 2>/dev/null
echo "■ Arasaka Techie removido. Sua montagem salva fica em ~/.config/arasaka-techie."
