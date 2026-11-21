"""
ARASAKA TECHIE // precos: le o coletor do servidor (server/techie no piphin.online), guarda em cache e julga
se o preco de hoje esta alto ou baixo comparando com o historico.

O app so LE. Quem consulta as lojas e guarda o historico e o coletor no servidor (uma vez por dia), entao
todo mundo ve o mesmo historico. Sem internet, usa o ultimo cache. Nada aqui depende do Qt.

API do servidor (JSON):
  GET <base>?index=1     {"updated": "...", "parts": {"<id>": {"price": 999.9, "store": "...", "image": "https://..."}}}
  GET <base>?part=<id>   {"part": "<id>", "updated": "...", "history": [{"d": "2026-11-20", "min": 999.9}],
                          "offers": [{"store": "...", "title": "...", "price": 999.9 | null, "url": "https://...", "image": "..."}]}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .core import APP_ID, HOME, VERSION

BASE = os.environ.get("ARASAKA_TECHIE_PRECOS", "https://piphin.online/techie/api.php")
CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / APP_ID
INDEX_TTL = 6 * 3600
PART_TTL = 6 * 3600
WINDOW_DAYS = 90
MIN_POINTS = 7
DISCLOSURE = ("Links de afiliado: se você comprar por eles, o Arasaka Techie pode receber uma comissão da loja, "
              "sem custo a mais para você. Preços e estoque mudam: confira na loja antes de comprar.")
UA = f"ArasakaTechie/{VERSION}"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{0,63}$")


class Offline(Exception):
    pass


def _get(url: str, timeout: float = 12) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (so https/http do servidor configurado)
            return r.read(4 * 1024 * 1024)
    except Exception as e:  # noqa: BLE001
        raise Offline(str(e)) from e


def _cached(name: str, url: str, ttl: float, force: bool = False) -> tuple[dict | None, bool]:
    """(dados, veio_do_cache_velho). Busca no servidor se o cache venceu; sem internet, usa o cache."""
    f = CACHE / name
    fresh = f.exists() and time.time() - f.stat().st_mtime < ttl
    if fresh and not force:
        try:
            return json.loads(f.read_text(encoding="utf-8")), False
        except ValueError:
            pass
    try:
        data = json.loads(_get(url).decode("utf-8"))
        if not isinstance(data, dict):
            raise Offline("resposta inválida")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data, False
    except (Offline, ValueError, UnicodeDecodeError):
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8")), True
            except ValueError:
                return None, True
        return None, True


def index(force: bool = False) -> tuple[dict, bool]:
    data, stale = _cached("precos-index.json", f"{BASE}?index=1", INDEX_TTL, force)
    parts = (data or {}).get("parts") or {}
    return {k: v for k, v in parts.items() if isinstance(v, dict)}, stale or data is None


def part(pid: str, force: bool = False) -> tuple[dict | None, bool]:
    if not ID_RE.match(pid):
        return None, True
    data, stale = _cached(f"preco-{pid}.json", f"{BASE}?part={urllib.parse.quote(pid)}", PART_TTL, force)
    if data:
        data["offers"] = [o for o in data.get("offers", []) if isinstance(o, dict) and safe_url(o.get("url"))]
        data["offers"].sort(key=lambda o: (o.get("price") is None, o.get("price") or 0))
        data["history"] = [h for h in data.get("history", []) if isinstance(h, dict) and isinstance(h.get("min"), (int, float))]
    return data, stale


def safe_url(url) -> bool:
    """So abre links https de verdade (os links vem do servidor, nao do app)."""
    if not isinstance(url, str) or len(url) > 2000:
        return False
    u = urllib.parse.urlparse(url)
    return u.scheme == "https" and bool(u.netloc) and " " not in url


def image_file(url: str) -> Path:
    return CACHE / "img" / (hashlib.sha1(url.encode()).hexdigest() + ".img")


def fetch_image(url: str) -> bytes | None:
    """Baixa (ou le do cache) a foto da peca que a loja informou."""
    if not safe_url(url):
        return None
    f = image_file(url)
    if f.exists() and f.stat().st_size:
        return f.read_bytes()
    try:
        data = _get(url, 15)
    except Offline:
        return None
    if len(data) < 200:
        return None
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(data)
    return data


def brl(v) -> str:
    if v is None:
        return "—"
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def verdict(history: list[dict], current: float | None, today: str | None = None) -> dict:
    """Compara o menor preco de hoje com os ultimos 90 dias: baixo (bom momento), normal, alto ou historico curto."""
    pts = sorted((h for h in history if isinstance(h.get("min"), (int, float)) and h["min"] > 0), key=lambda h: h["d"])
    if today:
        cut = time.strftime("%Y-%m-%d", time.gmtime(time.mktime(time.strptime(today, "%Y-%m-%d")) - WINDOW_DAYS * 86400))
        pts = [h for h in pts if h["d"] >= cut]
    else:
        pts = pts[-WINDOW_DAYS:]
    vals = [h["min"] for h in pts]
    if current is None and vals:
        current = vals[-1]
    res = {"level": "curto", "current": current, "min": min(vals) if vals else None, "max": max(vals) if vals else None,
           "median": statistics.median(vals) if vals else None, "points": len(vals), "pct": None, "vs_median": None}
    if current is None:
        res["text"] = "Sem preço ainda."
        return res
    if len(vals) < MIN_POINTS:
        res["text"] = f"Histórico curto ({len(vals)} dia(s)): ainda não dá para dizer se está caro ou barato."
        return res
    below = sum(1 for v in vals if v < current)
    pct = 100 * below / len(vals)
    vs = (current / res["median"] - 1) * 100
    res.update(pct=round(pct), vs_median=round(vs, 1))
    if pct <= 25 or current <= res["min"] * 1.02:
        res["level"] = "baixo"
        res["text"] = f"Preço BAIXO: menor que {100 - round(pct)}% dos dias dos últimos {WINDOW_DAYS} ({vs:+.0f}% da mediana). Bom momento."
    elif pct >= 75:
        res["level"] = "alto"
        res["text"] = f"Preço ALTO: maior que {round(pct)}% dos dias dos últimos {WINDOW_DAYS} ({vs:+.0f}% da mediana). Se puder, espere."
    else:
        res["level"] = "normal"
        res["text"] = f"Preço normal para o histórico ({vs:+.0f}% da mediana de {brl(res['median'])})."
    return res


def build_total(parts: dict, idx: dict) -> tuple[float, list[str]]:
    """Soma do menor preco de cada peca escolhida; devolve tambem as categorias sem preco."""
    total, missing = 0.0, []
    for cat, pid in parts.items():
        if not pid:
            continue
        p = idx.get(pid)
        if p and isinstance(p.get("price"), (int, float)):
            total += p["price"]
        else:
            missing.append(cat)
    return total, missing


def report_section(parts: dict, idx: dict, cat_name: dict, part_name) -> str:
    """Bloco de precos para o relatorio (texto)."""
    if not idx:
        return "\nPREÇOS\n  Sem preços (servidor de preços fora do ar ou sem conexão).\n"
    L = ["", "PREÇOS (menor preço encontrado pelo coletor)"]
    for cat, pid in parts.items():
        if not pid:
            continue
        p = idx.get(pid) or {}
        tag = {"baixo": "  · preço baixo", "alto": "  · preço alto"}.get(p.get("verdict"), "")
        L.append(f"  {cat_name[cat]:<24} {brl(p.get('price')) if p.get('price') is not None else 'sem preço':>14}  {p.get('store', '')}{tag}")
    total, missing = build_total(parts, idx)
    L.append(f"  {'TOTAL':<24} {brl(total):>14}" + (f"  (sem preço: {len(missing)} peça(s))" if missing else ""))
    L.append("  " + DISCLOSURE)
    return "\n".join(L) + "\n"
