"""Compatibilidade, estimativa de FPS, airflow, fonte e upgrade (sem Qt).

    python tests/test_simulador.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

T = Path(tempfile.mkdtemp())
os.environ.update(HOME=str(T), XDG_CONFIG_HOME=str(T / ".config"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from arasaka_techie import core as C  # noqa: E402

D = C.db()


def codes(b):
    return {i["code"] for i in C.check(b)}


def errs(b):
    return {i["code"] for i in C.errors(C.check(b))}


# ---------------------------------------------------------------- base de pecas
ids = set()
for cat in C.CATS:
    assert D.parts[cat], f"categoria vazia: {cat}"
    for p in D.parts[cat]:
        assert p["id"] not in ids, f"id repetido: {p['id']}"
        ids.add(p["id"])
for p in D.parts["case"]:
    for pos, slot in p["slots"].items():
        assert pos in C.POSITIONS and all(int(s) in C.FAN_SIZES for s in slot["sizes"]), p["id"]
    for pos, f in p["fans"].items():
        assert slot and str(f["size"]) in p["slots"][pos]["sizes"] and f["count"] <= p["slots"][pos]["sizes"][str(f["size"])], p["id"]
for p in D.parts["cooler"]:
    assert (p["kind"] == "aio") == ("radiator" in p), p["id"]
for pr in D.presets:
    b = C.from_preset(pr["id"])
    assert not C.errors(C.check(b)), (pr["id"], C.check(b))
assert D.get("gpu", "rtx-4090")["score"] == 100 and D.get("cpu", "r7-7800x3d")["score"] == 100, "referencias do modelo"

# ---------------------------------------------------------------- compatibilidade
b = C.from_preset("medio")                      # AM5 / DDR5 / mATX
x = json.loads(json.dumps(b))
x["parts"]["cpu"] = "r5-5600"                    # AM4
assert "socket" in errs(x)
x = json.loads(json.dumps(b))
x["parts"]["ram"] = "ddr4-2x16-3200"
assert "ram_type" in errs(x)
x = json.loads(json.dumps(b))
x["parts"]["case"] = "nr200p"                    # so ITX e SFX
C.reset_fans(x)
assert {"form", "psu_form"} <= errs(x)
x = json.loads(json.dumps(b))
x["parts"]["gpu"] = "rtx-4090"                   # 336 mm, Fractal North aceita 355
x["parts"]["case"] = "office-matx"               # aceita 250 mm
C.reset_fans(x)
assert "gpu_len" in errs(x)
x = json.loads(json.dumps(b))
x["parts"]["cooler"] = "drp5"                    # 168 mm
x["parts"]["case"] = "nr200p"
assert "cooler_h" in errs(x)
x = json.loads(json.dumps(b))
x["parts"]["cooler"] = "laminar-rm1"             # so Intel
assert "cooler_socket" in errs(x)
x = json.loads(json.dumps(b))
x["parts"]["cooler"] = "lf3-360"
x["parts"]["case"] = "nr200p"                    # nao tem 3x120
x["parts"]["mobo"] = "strix-b650e-i"
x["parts"]["psu"] = "sf750"
C.reset_fans(x)
assert "radiator" in errs(x) and "form" not in errs(x) and "psu_form" not in errs(x)
x = json.loads(json.dumps(b))
x["parts"]["gpu"] = "rtx-5090"
x["parts"]["psu"] = "cx550"
assert "psu_w" in errs(x)
x["parts"]["psu"] = "rm850x"                     # aguenta o pico mas fica abaixo do recomendado (1000 W)
assert "psu_w" not in errs(x) and "psu_rec" in codes(x)
x = json.loads(json.dumps(b))
x["parts"]["gpu"] = ""
x["parts"]["cpu"] = "r5-7600"                    # tem iGPU
assert "no_video" not in errs(x) and "igpu" in codes(x)
x = C.from_preset("entrada")
x["parts"]["gpu"] = ""                           # Ryzen 5 5600 nao tem iGPU
assert "no_video" in errs(x)
x = C.from_preset("medio")
x["parts"]["ram"] = "ddr5-1x16-5600"
assert {"ram_single"} <= codes(x)
x["parts"]["cpu"] = "i9-14900k"
x["parts"]["mobo"] = "b760-gaming-x"
x["parts"]["case"] = "4000d-airflow"
x["parts"]["cooler"] = "ak400"                   # 200 W para 253 W
C.reset_fans(x)
assert "cooler_cap" in codes(x) and "socket" not in errs(x)
x = C.from_preset("medio")
x["parts"]["mobo"] = "prime-b760m-a-d4"          # LGA1700 aceita DDR4 nesta placa
x["parts"]["cpu"] = "i5-13400f"
x["parts"]["ram"] = "ddr4-2x16-3200"
assert not errs(x), C.check(x)

# ---------------------------------------------------------------- estimativa
g = next(x for x in D.games if x["id"] == "cyberpunk")
b = C.from_preset("medio")
e1, e2, e4 = (C.estimate(b, g, r, "alto") for r in ("1080p", "1440p", "4K"))
assert e1["fps"] >= e2["fps"] > e4["fps"] > 0, "mais resolucao, menos FPS"
assert C.estimate(b, g, "1440p", "baixo")["fps"] > C.estimate(b, g, "1440p", "ultra")["fps"]
assert e4["limit"] == "GPU", "em 4K a placa de video limita"
top = C.from_preset("topo")
assert C.estimate(top, g, "1080p", "baixo")["limit"] == "CPU", "RTX 5090 em 1080p baixo fica presa no processador"
# a combinacao fica perto do menor e nunca acima dele
for r in ("1080p", "1440p", "4K"):
    e = C.estimate(top, g, r, "alto")
    assert e["fps"] <= min(e["gpu_fps"], e["cpu_fps"]) and e["fps"] >= 0.9 * min(e["gpu_fps"], e["cpu_fps"])
# limite do motor do jogo
er = next(x for x in D.games if x["id"] == "eldenring")
assert C.estimate(top, er, "1080p", "alto")["fps"] == 60
# GPU mais forte nunca piora; VRAM curta derruba
low = json.loads(json.dumps(b))
low["parts"]["gpu"] = "rtx-4060"
assert C.estimate(low, g, "1440p", "alto")["fps"] < e2["fps"]
hw = next(x for x in D.games if x["id"] == "hogwarts")
assert C.estimate(low, hw, "4K", "ultra")["vram_short"] and not C.estimate(top, hw, "4K", "ultra")["vram_short"]
# memoria: um pente so e DDR mais lenta reduzem o FPS de CPU
one = json.loads(json.dumps(b))
one["parts"]["ram"] = "ddr5-1x16-5600"
assert C.estimate(one, g, "1080p", "baixo")["cpu_fps"] < C.estimate(b, g, "1080p", "baixo")["cpu_fps"]
# video integrado roda, mas bem mais lento
ig = json.loads(json.dumps(b))
ig["parts"]["gpu"] = ""
ig["parts"]["cpu"] = "r7-8700g"
assert 0 < C.estimate(ig, g, "1080p", "baixo")["fps"] < C.estimate(low, g, "1080p", "baixo")["fps"]
assert C.tier(200) == "competitivo" and C.tier(70) == "fluido" and C.tier(40) == "jogável" and C.tier(10) == "travando"

# ---------------------------------------------------------------- airflow
b = C.from_preset("medio")                        # Fractal North: 2x140 entrada, 1x120 saida
a = C.airflow(b)
assert a["pressure"] == "positiva" and a["intake"] > a["exhaust"] > 0
assert a["case_air"] > b["ambient"] and a["cpu"] > a["case_air"] and a["gpu"] > a["case_air"]
neg = json.loads(json.dumps(b))
neg["fans"] = {"front": {"count": 1, "size": 120, "dir": "in"}, "top": {"count": 3, "size": 120, "dir": "out"}, "rear": {"count": 1, "size": 120, "dir": "out"}}
assert C.airflow(neg)["pressure"] == "negativa"
none = json.loads(json.dumps(b))
none["fans"] = {}
an = C.airflow(none)
assert an["pressure"] == "sem fans" and an["case_air"] > a["case_air"] and an["gpu"] > a["gpu"]
assert {"no_exhaust", "no_intake"} <= codes(none)
more = json.loads(json.dumps(b))
more["fans"]["top"] = {"count": 2, "size": 140, "dir": "out"}
assert C.airflow(more)["case_air"] < a["case_air"], "mais saida, ar interno mais frio"
bad = json.loads(json.dumps(b))
bad["fans"] = {"front": {"count": 2, "size": 140, "dir": "out"}, "rear": {"count": 1, "size": 120, "dir": "in"}}   # os mesmos fans, invertidos
assert C.airflow(bad)["case_air"] > a["case_air"], "contra a conveccao esquenta mais"
hot = json.loads(json.dumps(b))
hot["ambient"] = 35
assert C.airflow(hot)["cpu"] > a["cpu"]
# frente fechada (H510) restringe a entrada
h510 = json.loads(json.dumps(b))
h510["parts"]["case"] = "nzxt-h510"
h510["fans"] = {"front": {"count": 2, "size": 140, "dir": "in"}, "rear": {"count": 1, "size": 120, "dir": "out"}}
assert C.airflow(h510)["intake"] < a["intake"]
# carga total esquenta mais que jogando; cooler fraco chega no limite
assert C.airflow(b, full_load=True)["cpu"] > a["cpu"]
weak = C.from_preset("medio")
weak["parts"].update(cpu="i9-14900k", mobo="b760-gaming-x", cooler="laminar-rm1")
assert C.airflow(weak, full_load=True)["cpu_throttle"]
# water cooler: os fans do radiador entram sozinhos e o radiador soprando para fora tira o calor da CPU do gabinete
t = C.from_preset("topo")
assert C.radiator_pos(t) == "top" and t["fans"]["top"] == {"count": 3, "size": 120, "dir": "out"}
at = C.airflow(t)
assert at["heat"] < C.part(t, "gpu")["power"] + C.part(t, "cpu")["game_w"]
t2 = json.loads(json.dumps(t))
t2["fans"].pop("top")
assert "rad_fans" in codes(t2) and C.airflow(t2)["cpu"] > at["cpu"]
# sanitize: tamanhos e posicoes que o gabinete nao aceita somem
s = json.loads(json.dumps(b))
s["fans"] = {"bottom": {"count": 2, "size": 120, "dir": "in"}, "front": {"count": 9, "size": 200, "dir": "in"}}
C.sanitize_fans(s)
assert "bottom" not in s["fans"] and s["fans"]["front"]["count"] <= 2

# ---------------------------------------------------------------- fonte
p = C.power(C.from_preset("topo"))
assert p["peak"] > 700 and p["recommended"] >= 1000 and p["game"] < p["peak"]
p = C.power(C.from_preset("entrada"))
assert 400 <= p["recommended"] <= 650

# ---------------------------------------------------------------- upgrade
b = C.from_preset("entrada")                      # Ryzen 5 5600 (AM4/DDR4) + RX 6600 + CX550
u = C.upgrade(b, "gpu", "rtx-4090")
assert u["avg_gain"] > 50, u["avg_gain"]
assert any(c["cat"] == "psu" for c in u["changes"]), "GPU nova pede fonte maior"
assert C.part(u["build"], "psu")["watts"] >= C.power(u["build"])["recommended"]
assert not C.errors(u["issues"])
u = C.upgrade(b, "cpu", "r7-9800x3d")             # AM5 -> placa-mae nova e DDR5
cats = {c["cat"] for c in u["changes"]}
assert {"mobo", "ram"} <= cats, u["changes"]
assert C.part(u["build"], "mobo")["socket"] == "AM5" and C.part(u["build"], "ram")["type"] == "DDR5"
assert not C.errors(u["issues"])
assert u["build"]["parts"]["cpu"] == "r7-9800x3d" and b["parts"]["cpu"] == "r5-5600", "a montagem original nao muda"
u = C.upgrade(b, "ram", "ddr5-2x16-6000")         # DDR5 -> placa-mae nova (e processador do soquete novo)
assert {"mobo", "cpu"} <= {c["cat"] for c in u["changes"]} and not C.errors(u["issues"])
u = C.upgrade(C.from_preset("medio"), "gpu", "rtx-5090")
assert any(c["cat"] == "psu" for c in u["changes"])
small = C.from_preset("medio")
small["parts"]["case"] = "office-matx"
small["parts"]["gpu"] = "rx-6600"
small["parts"]["cooler"] = "wraith-stealth"
C.reset_fans(small)
assert not C.errors(C.check(small)), C.check(small)
u = C.upgrade(small, "gpu", "rtx-4080s")          # 310 mm nao cabe em gabinete de 250 mm
assert any(c["cat"] == "case" for c in u["changes"]) and not C.errors(u["issues"])
u = C.upgrade(C.from_preset("medio"), "storage", "990pro-2tb")
assert not u["changes"] and abs(u["avg_gain"]) < 0.5, "SSD nao muda o FPS"
u = C.upgrade(C.from_preset("medio"), "cpu", "i9-14900k")
cats = {c["cat"] for c in u["changes"]}
assert "mobo" in cats and C.part(u["build"], "mobo")["socket"] == "LGA1700"
assert "cooler_cap" not in {i["code"] for i in u["issues"]} or C.part(u["build"], "cooler")["capacity"] >= 245


# ---------------------------------------------------------------- plataformas antigas e Xeon
b = C.new_build({"cpu": "phenom-965", "mobo": "m5a97-r2", "ram": "ddr3-2x8-1600"})
assert "socket" not in errs(b), "placa AM3+ aceita processador AM3"
assert "no_avx" in codes(b)
b = C.new_build({"cpu": "fx-8350", "mobo": "a68hm-k"})
assert "socket" in errs(b)
b = C.new_build({"cpu": "i5-6500", "mobo": "prime-z390-a"})
iss = [i for i in C.check(b) if i["code"] == "socket"]
assert iss and "6ª/7ª" in iss[0]["text"], "LGA1151 de 6a/7a geracao nao entra em placa Z390"
b = C.new_build({"cpu": "e5-2666v3", "mobo": "x99-mr9a-pro", "ram": "ddr4-2x16-2400-reg"})
assert not errs(b) - {"no_video"}, "memoria de servidor na placa de Xeon"
b["parts"]["mobo"] = "b550-tomahawk"
assert "ram_reg" in errs(b)
b = C.new_build({"cpu": "e5-2666v3", "mobo": "x99-ad3", "ram": "ddr3-2x8-1600"})
assert not {"ram_type", "cpu_mem"} & errs(b), "X99 de DDR3"
assert "few_threads" in codes(C.new_build({"cpu": "e8400"}))
for pr in ("xeon", "antigo", "fx"):
    assert not C.errors(C.check(C.from_preset(pr))), pr

# ---------------------------------------------------------------- escolha passo a passo e busca
b = C.new_build({})
assert {o["part"]["socket"] for o in C.options(b, "cpu", "xeon")} <= {"LGA2011", "LGA2011-3", "LGA1366", "LGA1150", "LGA1155"}
assert all(o["part"]["socket"] in ("AM3", "AM3+") for o in C.options(b, "cpu", "am3"))
assert [o["part"]["id"] for o in C.options(b, "gpu", "rtx 3060")] == ["rtx-3060"]
assert all(o["part"]["type"] == "DDR3" for o in C.options(b, "ram", "ddr3"))
assert C.options(b, "cpu", "processador que nao existe") == []
assert C.norm("Placa-Mãe ÁÉ") == "placa mae ae"
C.pick(b, "cpu", "fx-8350")
mobos = C.options(b, "mobo")
okm = [o["part"]["id"] for o in mobos if o["ok"]]
assert set(okm) == {"m5a97-r2", "78lmt-usb3"} and mobos[0]["ok"] and not mobos[-1]["ok"] and mobos[-1]["why"]
assert C.next_step(b, "cpu") == "mobo"
C.pick(b, "mobo", "m5a97-r2")
assert all(o["part"]["type"] == "DDR3" for o in C.options(b, "ram") if o["ok"])
C.pick(b, "ram", "ddr3-2x8-1600")
assert C.next_step(b, "ram") == "cooler"
cleared = C.pick(b, "cpu", "r5-5600")        # outra plataforma: placa e memoria saem
assert set(cleared) == {"mobo", "ram"} and not b["parts"]["mobo"] and not b["parts"]["ram"]
coolers = [o["part"]["id"] for o in C.options(b, "cooler") if o["ok"]]
assert "laminar-rm1" not in coolers and "ak400" in coolers

# ---------------------------------------------------------------- relatorio e salvar
r = C.report(C.from_preset("medio"))
for s in ("ESTIMATIVA", "DESEMPENHO ESPERADO", "AIRFLOW", "CONSUMO E FONTE", "AVISOS", "Cyberpunk 2077"):
    assert s in r, s
b = C.from_preset("topo")
b["ambient"] = 31
C.save_build(b)
assert C.load_build() == b
C.BUILD_FILE.write_text("{quebrado")
assert C.load_build()["parts"]["cpu"] == "r5-7600", "arquivo quebrado volta para o modelo intermediario"
print("■ simulador: tudo certo")
