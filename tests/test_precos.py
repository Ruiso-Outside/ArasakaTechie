"""Precos no app: veredito pelo historico, links seguros, cache e servidor fora do ar.

    python tests/test_precos.py
"""
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

T = Path(tempfile.mkdtemp())
os.environ.update(HOME=str(T), XDG_CONFIG_HOME=str(T / ".config"), XDG_CACHE_HOME=str(T / ".cache"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fake_price_server  # noqa: E402

srv = fake_price_server.serve(0)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["ARASAKA_TECHIE_PRECOS"] = f"http://127.0.0.1:{port}/api.php"
from arasaka_techie import prices as P  # noqa: E402

# veredito
hist = [{"d": f"2026-08-{d:02d}", "min": 1000 + (d % 10) * 20} for d in range(1, 32)] + \
       [{"d": f"2026-09-{d:02d}", "min": 1000 + (d % 10) * 20} for d in range(1, 31)]
v = P.verdict(hist, 990, today="2026-09-30")
assert v["level"] == "baixo" and v["min"] == 1000 and v["points"] == 61, v
assert P.verdict(hist, 1185, today="2026-09-30")["level"] == "alto"
assert P.verdict(hist, 1090, today="2026-09-30")["level"] == "normal"
assert P.verdict(hist[:3], 990)["level"] == "curto"
assert P.verdict([], None)["level"] == "curto"
old = [{"d": "2025-01-01", "min": 10}] * 30
assert P.verdict(old + hist, 990, today="2026-09-30")["min"] == 1000, "so os ultimos 90 dias contam"
# formato e links
assert P.brl(1234.5) == "R$ 1.234,50" and P.brl(None) == "—"
assert P.safe_url("https://s.click.aliexpress.com/e/_x")
for bad in ("http://loja.example", "javascript:alert(1)", "file:///etc/passwd", "https://", None, "https://a b", "x" * 3000):
    assert not P.safe_url(bad), bad
assert P.build_total({"cpu": "a", "gpu": "b", "ram": ""}, {"a": {"price": 100.0}, "b": {"price": None}}) == (100.0, ["gpu"])

# servidor (falso) e cache
idx, stale = P.index()
assert not stale and idx["rtx-4070s"]["verdict"] == "baixo" and idx["b650m-mortar"]["verdict"] == "alto"
d, stale = P.part("rtx-4070s")
assert not stale and len(d["history"]) == 120 and d["offers"][0]["price"] is not None and d["offers"][-1]["price"] is None
assert P.verdict(d["history"], d["offers"][0]["price"])["level"] == "baixo"
assert P.part("../../etc/passwd") == (None, True), "id invalido nem chega no servidor"
assert P.part("peca-que-nao-existe")[0] is None
srv.shutdown()
srv.server_close()
idx2, stale = P.index(force=True)         # servidor caiu: usa o cache
assert stale and idx2 == idx
d2, stale = P.part("rtx-4070s", force=True)
assert stale and d2["history"] == d["history"]
P.CACHE.joinpath("precos-index.json").unlink()
assert P.index(force=True) == ({}, True), "sem servidor e sem cache"
txt = P.report_section({"gpu": "rtx-4070s", "cpu": "r5-7600"}, idx, {"gpu": "Placa de vídeo", "cpu": "Processador"}, lambda c, p: p)
assert "TOTAL" in txt and "afiliado" in txt and "preço baixo" in txt
print("■ precos: tudo certo")
