"""
ARASAKA TECHIE // nucleo: base de pecas, compatibilidade, estimativa de FPS, airflow, fonte e upgrade.

Tudo aqui e ESTIMATIVA feita com um modelo simples e documentado (veja README e MODELO abaixo).
Nao le nada do sistema: so a base local em data/parts.json. Nao depende do Qt, para dar para testar.

MODELO
- FPS limitado pela GPU = fps_gpu_do_jogo x (score_gpu / 100)^0,85 x fator_resolucao x fator_qualidade
  (fps_gpu_do_jogo = RTX 4090 em 1080p alto). Falta de VRAM derruba o FPS (e causa engasgos).
- FPS limitado pela CPU = fps_cpu_do_jogo x (score_cpu / 100) x fator_memoria x fator_qualidade_cpu
  (fps_cpu_do_jogo = Ryzen 7 7800X3D). Nao depende da resolucao.
- FPS final = combinacao suave dos dois ((g^-8 + c^-8)^(-1/8)): fica perto do menor, um pouco abaixo
  quando os dois estao parecidos. O menor dos dois e o gargalo. Limite do motor do jogo (cap) por cima.
- Airflow: cada fan tem uma vazao tipica (CFM) pelo tamanho, reduzida pela restricao do painel e por um
  radiador. Entrada - saida = pressao. Vazao util = min(entrada, saida) + metade da diferenca (o resto
  entra/sai pelas frestas). Ar do gabinete = ambiente + calor / (vazao x 0,569 W/K por CFM) x mistura.
- CPU = ar que chega no cooler + offset do chip + 55 C x (consumo / capacidade do cooler).
- GPU = ar do gabinete + 42 C x (consumo / consumo de projeto).
- Fonte recomendada = maior entre a recomendacao da GPU e pico do sistema x 1,3 (picos rapidos e folga).
"""
from __future__ import annotations

import copy
import json
import math
import os
import unicodedata
from pathlib import Path

APP_ID = "arasaka-techie"
APP_NAME = "ARASAKA TECHIE"
VERSION = "1.1.0"

HOME = Path.home()
PKG = Path(__file__).resolve().parent
ASSETS = PKG / "assets"
DATA_FILE = PKG / "data" / "parts.json"
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
BUILD_FILE = CONFIG_HOME / APP_ID / "montagem.json"

CATS = ["cpu", "mobo", "ram", "gpu", "storage", "psu", "case", "cooler"]
CAT_NAME = {"cpu": "Processador", "mobo": "Placa-mãe", "ram": "Memória RAM", "gpu": "Placa de vídeo",
            "storage": "Armazenamento", "psu": "Fonte", "case": "Gabinete", "cooler": "Cooler do processador"}
REQUIRED = ["cpu", "mobo", "ram", "storage", "psu", "case", "cooler"]

RES = {"1080p": 1.0, "1440p": 0.7, "4K": 0.38}
RES_VRAM = {"1080p": 1.0, "1440p": 1.2, "4K": 1.5}
QUALITY = ["baixo", "medio", "alto", "ultra"]
QUALITY_NAME = {"baixo": "Baixo", "medio": "Médio", "alto": "Alto", "ultra": "Ultra"}
Q_GPU = {"baixo": 1.9, "medio": 1.4, "alto": 1.0, "ultra": 0.8}
Q_CPU = {"baixo": 1.15, "medio": 1.07, "alto": 1.0, "ultra": 0.95}
Q_VRAM = {"baixo": -2.0, "medio": -1.0, "alto": 0.0, "ultra": 1.5}
SMOOTH_K = 8

POSITIONS = ["front", "top", "rear", "bottom", "side"]
POS_NAME = {"front": "Frente", "top": "Topo", "rear": "Traseira", "bottom": "Fundo", "side": "Lateral"}
FAN_SIZES = [80, 92, 120, 140, 200]
FAN_CFM = {80: 30, 92: 40, 120: 55, 140: 68, 200: 110}
RADIATOR = {240: (120, 2), 280: (140, 2), 360: (120, 3)}
RAD_PREF = ["top", "front", "side", "bottom"]
W_PER_CFM_K = 0.000471947 * 1.2 * 1005      # 1 CFM de ar leva ~0,569 W por grau
TJMAX = {"AM5": 95, "AM4": 90, "AM3+": 75, "AM3": 75, "FM2+": 80}
CHIP_OFFSET = {"AM5": 15, "AM4": 10, "AM3+": -20, "AM3": -18, "FM2+": -10}   # FX/Phenom medem bem mais baixo
GPU_CURVE = 0.85        # pontuacao efetiva = 100 x (score/100)^0.85: placas fracas escalam melhor que linear
MEM_REF = {"DDR3": 1600, "DDR4": 3200, "DDR5": 6000}
PSU_SIZES = [450, 550, 650, 750, 850, 1000, 1200, 1500, 1600]
LOAD_FACTOR = {"nvme": 1.0, "sata": 1.15, "hdd": 2.6}


# ================================================================ base de pecas
class DB:
    def __init__(self, path: Path = DATA_FILE):
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.version = raw.get("versao", 1)
        self.parts = {c: raw[c] for c in CATS}
        self.games = raw["games"]
        self.presets = raw["presets"]
        self._ix = {c: {p["id"]: p for p in self.parts[c]} for c in CATS}

    def get(self, cat: str, pid: str | None):
        return self._ix[cat].get(pid) if pid else None

    def name(self, cat: str, pid: str | None) -> str:
        p = self.get(cat, pid)
        return p["name"] if p else "—"


_DB: DB | None = None


def db() -> DB:
    global _DB
    if _DB is None:
        _DB = DB()
    return _DB


# ================================================================ montagem
def new_build(parts: dict | None = None, d: DB | None = None) -> dict:
    d = d or db()
    b = {"parts": {c: "" for c in CATS}, "fans": {}, "radiator": "", "ambient": 25, "res": "1440p", "quality": "alto"}
    b["parts"].update(parts or {})
    reset_fans(b, d)
    return b


def from_preset(pid: str, d: DB | None = None) -> dict:
    d = d or db()
    p = next(x for x in d.presets if x["id"] == pid)
    return new_build(p["parts"], d)


def part(b: dict, cat: str, d: DB | None = None):
    return (d or db()).get(cat, b["parts"].get(cat))


def reset_fans(b: dict, d: DB | None = None):
    """Fans de fabrica do gabinete; com water cooler, poe os fans do radiador se a posicao estiver vazia."""
    d = d or db()
    case = part(b, "case", d)
    b["fans"] = copy.deepcopy(case.get("fans", {})) if case else {}
    b["radiator"] = ""
    cool = part(b, "cooler", d)
    if case and cool and cool["kind"] == "aio":
        pos = radiator_pos(b, d)
        if pos:
            size, n = RADIATOR[cool["radiator"]]
            if b["fans"].get(pos, {}).get("count", 0) < n or b["fans"][pos]["size"] != size:
                b["fans"][pos] = {"count": n, "size": size, "dir": "out" if pos in ("top", "rear") else "in"}


def sanitize_fans(b: dict, d: DB | None = None):
    """Tira posicoes e tamanhos que o gabinete nao aceita."""
    case = part(b, "case", d)
    if not case:
        b["fans"] = {}
        return
    out = {}
    for pos, f in b["fans"].items():
        slot = case["slots"].get(pos)
        if not slot or not f.get("count"):
            continue
        sizes = {int(k): v for k, v in slot["sizes"].items()}
        size = int(f.get("size", 120))
        if size not in sizes:
            size = max(sizes)
        out[pos] = {"count": max(0, min(int(f["count"]), sizes[size])), "size": size, "dir": "out" if f.get("dir") == "out" else "in"}
    b["fans"] = {k: v for k, v in out.items() if v["count"]}


def fits_radiator(case: dict, pos: str, radiator: int) -> bool:
    size, n = RADIATOR[radiator]
    slot = case["slots"].get(pos)
    return bool(slot) and slot["sizes"].get(str(size), 0) >= n


def radiator_pos(b: dict, d: DB | None = None) -> str:
    case, cool = part(b, "case", d), part(b, "cooler", d)
    if not case or not cool or cool["kind"] != "aio":
        return ""
    if b.get("radiator") and fits_radiator(case, b["radiator"], cool["radiator"]):
        return b["radiator"]
    return next((p for p in RAD_PREF if fits_radiator(case, p, cool["radiator"])), "")


def fan_count(b: dict) -> int:
    return sum(f["count"] for f in b["fans"].values())


# ================================================================ energia
def power(b: dict, d: DB | None = None) -> dict:
    d = d or db()
    cpu, gpu, ram, st, cool, psu = (part(b, c, d) for c in ("cpu", "gpu", "ram", "storage", "cooler", "psu"))
    rest = 40 + (3 * ram["sticks"] if ram else 0) + (st["power"] if st else 0) + 2 * fan_count(b) + (5 if cool and cool["kind"] == "aio" else 0)
    peak = (cpu["max_w"] if cpu else 0) + (gpu["power"] if gpu else 0) + rest
    game = (cpu["game_w"] if cpu else 0) + (gpu["power"] * 0.9 if gpu else 0) + rest
    need = peak * 1.3
    rec = next((s for s in PSU_SIZES if s >= need), PSU_SIZES[-1])
    if gpu:
        rec = max(rec, gpu["rec_psu"])
    eff = psu["eff"] if psu else 0.87
    return {"peak": round(peak), "game": round(game), "recommended": rec, "wall_game": round(game / eff),
            "load_pct": round(100 * game / psu["watts"]) if psu else None}


# ================================================================ compatibilidade
def issue(level: str, code: str, text: str, parts: list[str] = ()) -> dict:
    return {"level": level, "code": code, "text": text, "parts": list(parts)}


def check(b: dict, d: DB | None = None) -> list[dict]:
    """Lista de problemas: level erro (nao monta/nao liga), aviso (funciona mal) ou info."""
    d = d or db()
    P = {c: part(b, c, d) for c in CATS}
    cpu, mobo, ram, gpu, st, psu, case, cool = (P[c] for c in CATS)
    out = []
    for c in REQUIRED:
        if not P[c]:
            out.append(issue("info", "missing", f"Falta escolher: {CAT_NAME[c].lower()}.", [c]))
    if cpu and mobo and cpu["socket"] not in mobo_sockets(mobo):
        extra = " (8ª/9ª geração e 6ª/7ª geração usam o mesmo encaixe, mas placas diferentes)" if {cpu["socket"], mobo["socket"]} == {"LGA1151", "LGA1151-v2"} else ""
        out.append(issue("erro", "socket", f"O {cpu['name']} usa soquete {cpu['socket']} e a placa-mãe é {mobo['socket']}{extra}.", ["mobo", "cpu"]))
    if ram and mobo and ram["type"] != mobo["mem"]:
        out.append(issue("erro", "ram_type", f"A placa-mãe aceita {mobo['mem']} e a memória escolhida é {ram['type']}.", ["ram", "mobo"]))
    if ram and cpu and ram["type"] not in cpu["mem"]:
        out.append(issue("erro", "cpu_mem", f"O {cpu['name']} não suporta {ram['type']}.", ["ram", "cpu"]))
    if ram and mobo and ram.get("reg") and not mobo.get("reg"):
        out.append(issue("erro", "ram_reg", "Memória de servidor (ECC registrada) só funciona em placas de Xeon (X79/X99): esta placa não liga com ela.", ["ram", "mobo"]))
    if ram and mobo and ram["sticks"] > mobo["slots"]:
        out.append(issue("erro", "ram_slots", f"São {ram['sticks']} pentes e a placa-mãe tem {mobo['slots']} slots.", ["ram"]))
    if ram and mobo and ram["gb"] > mobo["max_mem"]:
        out.append(issue("erro", "ram_max", f"A placa-mãe aceita até {mobo['max_mem']} GB de RAM.", ["ram"]))
    if mobo and case and mobo["form"] not in case["forms"]:
        out.append(issue("erro", "form", f"Placa-mãe {mobo['form']} não cabe no {case['name']} ({', '.join(case['forms'])}).", ["case", "mobo"]))
    if gpu and case:
        if gpu["length"] > case["gpu_max"]:
            out.append(issue("erro", "gpu_len", f"A placa de vídeo tem {gpu['length']} mm e o gabinete aceita até {case['gpu_max']} mm.", ["case", "gpu"]))
        elif gpu["length"] > case["gpu_max"] - 15:
            out.append(issue("aviso", "gpu_tight", f"Placa de vídeo apertada: {gpu['length']} de {case['gpu_max']} mm (sem espaço para fan na frente, confira o modelo exato).", []))
    if not gpu and cpu and not cpu["igpu"]:
        out.append(issue("erro", "no_video", f"O {cpu['name']} não tem vídeo integrado: precisa de uma placa de vídeo.", ["gpu"]))
    if not gpu and cpu and cpu["igpu"]:
        out.append(issue("info", "igpu", f"Sem placa de vídeo: os jogos rodam no vídeo integrado ({cpu.get('igpu_name', 'integrado')}).", []))
    if cool and cpu and cpu["socket"] not in cool["sockets"]:
        out.append(issue("erro", "cooler_socket", f"O {cool['name']} não tem suporte para o soquete {cpu['socket']}.", ["cooler"]))
    if cool and case:
        if cool["kind"] != "aio" and cool["height"] > case["cooler_max"]:
            out.append(issue("erro", "cooler_h", f"O cooler tem {cool['height']} mm de altura e o gabinete aceita {case['cooler_max']} mm.", ["cooler", "case"]))
        if cool["kind"] == "aio":
            pos = radiator_pos(b, d)
            size, n = RADIATOR[cool["radiator"]]
            if not pos:
                out.append(issue("erro", "radiator", f"O radiador de {cool['radiator']} mm não cabe em nenhuma posição do {case['name']}.", ["case", "cooler"]))
            else:
                f = b["fans"].get(pos)
                if not f or f["size"] != size or f["count"] < n:
                    out.append(issue("aviso", "rad_fans", f"O radiador fica em {POS_NAME[pos].lower()}: coloque {n} fans de {size} mm lá (no airflow).", []))
    if cool and cpu and cool["capacity"] < cpu["max_w"]:
        lvl = "erro" if cool["capacity"] < cpu["game_w"] * 1.1 else "aviso"
        out.append(issue(lvl, "cooler_cap", f"O cooler dissipa ~{cool['capacity']} W e o processador chega a {cpu['max_w']} W: "
                         + ("esquenta e perde desempenho até jogando." if lvl == "erro" else "em carga total (render, compilar) ele reduz a frequência."), ["cooler"]))
    if psu and case:
        if psu["form"] == "ATX" and case["psu"] == "SFX":
            out.append(issue("erro", "psu_form", f"O {case['name']} só aceita fonte SFX.", ["psu", "case"]))
        elif psu["form"] == "SFX" and case["psu"] == "ATX":
            out.append(issue("info", "psu_sfx", "Fonte SFX em gabinete ATX: precisa do suporte adaptador (normalmente vem com a fonte).", []))
    if psu and cpu:
        pw = power(b, d)
        if psu["watts"] < pw["peak"]:
            out.append(issue("erro", "psu_w", f"A fonte de {psu['watts']} W é menor que o pico do sistema (~{pw['peak']} W): o PC pode desligar sozinho.", ["psu"]))
        elif psu["watts"] < pw["recommended"]:
            out.append(issue("aviso", "psu_rec", f"A fonte de {psu['watts']} W funciona, mas o recomendado é {pw['recommended']} W (folga para picos da GPU).", ["psu"]))
    if cpu and not cpu.get("avx", True):
        out.append(issue("aviso", "no_avx", f"O {cpu['name']} não tem instruções AVX: vários jogos lançados depois de 2020 nem abrem.", []))
    if cpu and cpu["threads"] <= 2:
        out.append(issue("aviso", "few_threads", f"{cpu['cores']} núcleo(s) e {cpu['threads']} threads: jogos atuais travam bastante (o mínimo hoje é 4 núcleos/8 threads).", []))
    elif cpu and cpu["threads"] <= 4:
        out.append(issue("info", "four_threads", "4 threads: roda, mas jogos novos e pesados engasgam (1% low ruim).", []))
    if ram:
        if ram["gb"] < 16:
            out.append(issue("aviso", "ram_low", f"{ram['gb']} GB de RAM é pouco para jogos atuais (16 GB no mínimo, 32 GB ideal).", []))
        if ram["sticks"] == 1:
            out.append(issue("aviso", "ram_single", "Um pente só roda em canal único: o processador perde FPS. Prefira 2 pentes.", []))
    if st and st["kind"] == "hdd":
        out.append(issue("aviso", "hdd", "HD como disco principal deixa o sistema e os jogos lentos para carregar. Use um SSD.", []))
    if case and P["cpu"]:
        fans = b["fans"]
        if not any(f["dir"] == "out" for f in fans.values()):
            out.append(issue("aviso", "no_exhaust", "Nenhum fan de saída: o ar quente fica parado dentro do gabinete.", []))
        if not any(f["dir"] == "in" for f in fans.values()):
            out.append(issue("aviso", "no_intake", "Nenhum fan de entrada: o ar entra só pelas frestas (e traz poeira).", []))
    return out


def mobo_sockets(mobo: dict) -> list[str]:
    return mobo.get("accepts") or [mobo["socket"]]


def errors(issues: list[dict]) -> list[dict]:
    return [i for i in issues if i["level"] == "erro"]


# ================================================================ airflow e temperaturas
def airflow(b: dict, d: DB | None = None, full_load: bool = False) -> dict:
    d = d or db()
    case, cpu, gpu, cool = (part(b, c, d) for c in ("case", "cpu", "gpu", "cooler"))
    rad = radiator_pos(b, d)
    per = {}
    intake = exhaust = 0.0
    for pos, f in b["fans"].items():
        slot = (case or {}).get("slots", {}).get(pos)
        if not slot or not f["count"]:
            continue
        eff = f["count"] * FAN_CFM[f["size"]] * (1 - slot["restr"]) * (0.7 if pos == rad else 1.0)
        per[pos] = round(eff)
        if f["dir"] == "in":
            intake += eff
        else:
            exhaust += eff
    diff = intake - exhaust
    big = max(intake, exhaust)
    ratio = diff / big if big else 0.0
    if not big:
        pressure = "sem fans"
    elif ratio > 0.1:
        pressure = "positiva"
    elif ratio < -0.1:
        pressure = "negativa"
    else:
        pressure = "equilibrada"
    flow = min(intake, exhaust) + 0.5 * abs(diff) + 10    # +10: conveccao natural e frestas
    dirs = {p: f["dir"] for p, f in b["fans"].items() if f["count"]}
    good_in = any(dirs.get(p) == "in" for p in ("front", "bottom", "side"))
    good_out = any(dirs.get(p) == "out" for p in ("rear", "top"))
    against = any(dirs.get(p) == "in" for p in ("top", "rear")) and any(dirs.get(p) == "out" for p in ("front", "bottom"))
    if against:
        mix, path = 2.2, "contra a convecção (ar quente sobe e está sendo empurrado para baixo)"
    elif good_in and good_out:
        mix, path = 1.5, "bom (entra pela frente/baixo, sai por trás/cima)"
    else:
        mix, path = 1.9, "fraco (falta entrada ou saída num caminho limpo)"
    gpu_w = (gpu["power"] * (1.0 if full_load else 0.9)) if gpu else 0
    cpu_w = (cpu["max_w"] if full_load else cpu["game_w"]) if cpu else 0
    aio_out = bool(cool and cool["kind"] == "aio" and rad and dirs.get(rad) == "out")
    aio_in = bool(cool and cool["kind"] == "aio" and rad and dirs.get(rad) == "in")
    heat = gpu_w + (0 if aio_out else cpu_w) + 35
    rise = min(30.0, mix * heat / (flow * W_PER_CFM_K))
    amb = float(b.get("ambient", 25))
    case_air = amb + rise
    res = {"intake": round(intake), "exhaust": round(exhaust), "pressure": pressure, "ratio": round(ratio, 2),
           "flow": round(flow), "path": path, "case_air": round(case_air, 1), "heat": round(heat), "per": per,
           "radiator": rad, "cpu": None, "gpu": None, "cpu_throttle": False, "gpu_throttle": False}
    if cpu and cool:
        cap = cool["capacity"]
        if cool["kind"] == "aio":
            size, n = RADIATOR[cool["radiator"]]
            f = b["fans"].get(rad) if rad else None
            have = f["count"] if f and f["size"] == size else 0
            cap = cap * max(0.25, min(1.0, have / n)) if rad else cap * 0.25
        inlet = amb if aio_in else case_air
        t = inlet + 8 + CHIP_OFFSET.get(cpu["socket"], 5) + 55 * cpu_w / cap
        lim = TJMAX.get(cpu["socket"], 100)
        res["cpu"] = round(min(t, lim), 1)
        res["cpu_throttle"] = t >= lim
        res["cpu_limit"] = lim
    if gpu:
        starve = 0 if good_in else 4
        t = case_air + 42 * gpu_w / gpu["power"] + starve
        res["gpu"] = round(min(t, 90), 1)
        res["gpu_throttle"] = t > 87
    return res


# ================================================================ desempenho
def mem_factor(ram: dict | None, heavy: bool = False) -> float:
    if not ram:
        return 0.8
    ref = MEM_REF.get(ram["type"], 3200)
    if ram["type"] == "DDR5":
        f = 1 + max(-0.12, min(0.04, (ram["speed"] - ref) / ref * 0.2))
    else:
        f = 1 + max(-0.15, min(0.06, (ram["speed"] - ref) / ref * 0.25))
    if ram["sticks"] == 1:
        f *= 0.88
    if ram["gb"] < 16:
        f *= 0.8
    elif ram["gb"] < 32 and heavy:
        f *= 0.97
    return f


def estimate(b: dict, game: dict, res: str | None = None, quality: str | None = None, d: DB | None = None, air: dict | None = None) -> dict:
    d = d or db()
    res = res or b.get("res", "1440p")
    quality = quality or b.get("quality", "alto")
    cpu, gpu, ram = part(b, "cpu", d), part(b, "gpu", d), part(b, "ram", d)
    if not cpu:
        return {"fps": 0, "low": 0, "gpu_fps": 0, "cpu_fps": 0, "limit": "—", "bottleneck": 0, "vram_short": False, "tier": "sem processador"}
    air = air or airflow(b, d)
    if gpu:
        gscore, vram = gpu["score"], gpu["vram"]
    else:
        gscore, vram = cpu["igpu"], min(4, (ram["gb"] if ram else 8) / 4)
    g = game["gpu_fps"] * gpu_eff(gscore) / 100 * RES[res] * Q_GPU[quality]
    need = max(1.0, game["vram"] * RES_VRAM[res] + Q_VRAM[quality])
    short = vram < need
    if short:
        g *= max(0.6, vram / need)
    if air.get("gpu_throttle"):
        g *= 0.93
    c = game["cpu_fps"] * cpu["score"] / 100 * mem_factor(ram, game["vram"] >= 7) * Q_CPU[quality]
    if air.get("cpu_throttle"):
        c *= 0.88
    fps = (g ** -SMOOTH_K + c ** -SMOOTH_K) ** (-1 / SMOOTH_K) if g > 0 and c > 0 else 0
    if game.get("cap"):
        fps = min(fps, game["cap"])
    limit = "GPU" if g < c else "CPU"
    if game.get("cap") and min(g, c) >= game["cap"]:
        limit = "limite do jogo"
    bott = round(100 * (1 - min(g, c) / max(g, c))) if max(g, c) else 0
    low = fps * (0.72 if limit == "CPU" else 0.8) * (0.75 if short else 1)
    return {"fps": round(fps), "low": round(low), "gpu_fps": round(g), "cpu_fps": round(c), "limit": limit,
            "bottleneck": bott, "vram_short": short, "vram_need": round(need, 1), "tier": tier(fps)}


def gpu_eff(score: float) -> float:
    return 100 * (max(score, 0.1) / 100) ** GPU_CURVE


def tier(fps: float) -> str:
    if fps >= 144:
        return "competitivo"
    if fps >= 60:
        return "fluido"
    if fps >= 30:
        return "jogável"
    return "travando"


def estimate_all(b: dict, res: str | None = None, quality: str | None = None, d: DB | None = None) -> list[tuple[dict, dict]]:
    d = d or db()
    air = airflow(b, d)
    return [(g, estimate(b, g, res, quality, d, air)) for g in d.games]


def bottleneck_summary(rows: list[tuple[dict, dict]]) -> str:
    if not rows:
        return ""
    n_cpu = sum(1 for _, e in rows if e["limit"] == "CPU")
    n_gpu = sum(1 for _, e in rows if e["limit"] == "GPU")
    if n_cpu > n_gpu * 2:
        return f"O processador limita na maioria dos jogos ({n_cpu} de {len(rows)}): GPU melhor rende pouco nesta resolução."
    if n_gpu > n_cpu * 2:
        return f"A placa de vídeo limita na maioria dos jogos ({n_gpu} de {len(rows)}): é a peça que mais rende num upgrade."
    return f"Equilibrado: a GPU limita em {n_gpu} jogos e o processador em {n_cpu}."


# ================================================================ upgrade
def _closeness(cat: str, old: dict | None, new: dict, mobo: dict | None = None, ram: dict | None = None) -> float:
    """Menor = mais parecido com a peca antiga (para sugerir a troca mais natural)."""
    if not old:
        return new.get("score", 0) or new.get("watts", 0) or 0
    if cat in ("cpu", "gpu"):
        return abs(new["score"] - old["score"]) + (30 if new["score"] < old["score"] else 0)
    if cat == "psu":
        return new["watts"] + (500 if new["form"] != old["form"] else 0)
    if cat == "mobo":
        return (0 if new["form"] == old["form"] else 10) + (0 if ram and new["mem"] == ram["type"] else 5)
    if cat == "ram":
        return abs(new["gb"] - old["gb"]) * 0.5 + abs(new["speed"] - old["speed"]) / 400 + (6 if new["sticks"] == 1 and old["sticks"] > 1 else 0) + (20 if new["gb"] < old["gb"] else 0)
    if cat == "cooler":
        return abs(new["capacity"] - old["capacity"]) / 20 + (0 if new["kind"] == old["kind"] else 4) + (30 if new["capacity"] < old["capacity"] else 0)
    if cat == "case":
        return 0 if set(new["forms"]) >= set(old["forms"]) else 5
    return 0


FIXABLE = {"socket", "ram_type", "ram_reg", "cpu_mem", "ram_slots", "ram_max", "form", "gpu_len", "no_video", "cooler_socket",
           "cooler_h", "radiator", "psu_w", "psu_form", "psu_rec", "cooler_cap"}
REASON = {"socket": "o soquete do processador mudou", "ram_type": "o tipo de memória (DDR3/DDR4/DDR5) não bate", "ram_reg": "memória de servidor só funciona em placa de Xeon", "cpu_mem": "o processador não aceita esta memória",
          "ram_slots": "faltam slots de memória", "ram_max": "a placa-mãe não aceita tanta RAM", "form": "a placa-mãe não cabe no gabinete",
          "gpu_len": "a placa de vídeo não cabe no gabinete", "no_video": "o processador não tem vídeo integrado", "cooler_socket": "o cooler não encaixa no soquete novo",
          "cooler_h": "o cooler é alto demais para o gabinete", "radiator": "o radiador não cabe no gabinete", "psu_w": "a fonte não aguenta o pico de consumo",
          "psu_form": "o gabinete pede outro formato de fonte", "psu_rec": "a fonte fica sem folga para a peça nova", "cooler_cap": "o cooler não dá conta do processador novo"}


REASON_BY_TARGET = {("socket", "cpu"): "a placa-mãe nova usa outro soquete", ("ram_type", "mobo"): "a memória nova é de outro tipo (DDR3/DDR4/DDR5)", ("ram_reg", "mobo"): "a memória nova é de servidor (ECC REG)",
                    ("cpu_mem", "cpu"): "a memória nova não é aceita pelo processador", ("form", "mobo"): "o gabinete novo não aceita este tamanho de placa-mãe",
                    ("gpu_len", "gpu"): "o gabinete novo é curto para a placa de vídeo", ("cooler_h", "case"): "o cooler novo não cabe no gabinete",
                    ("radiator", "cooler"): "o gabinete novo não tem lugar para o radiador", ("psu_form", "case"): "a fonte nova não cabe no gabinete"}


def _reason(code: str, target: str, text: str) -> str:
    return REASON_BY_TARGET.get((code, target)) or REASON.get(code, text)


def _fixables(b: dict, d: DB) -> list[dict]:
    return [i for i in check(b, d) if i["code"] in FIXABLE and i["level"] in ("erro", "aviso")]


def upgrade(b: dict, cat: str, new_id: str, d: DB | None = None) -> dict:
    """Troca uma peca e resolve as trocas obrigatorias (outras pecas que precisam mudar junto)."""
    d = d or db()
    nb = copy.deepcopy(b)
    nb["parts"][cat] = new_id
    if cat in ("case", "cooler"):
        reset_fans(nb, d)
    locked = {cat}
    changes = []
    before_fix = {i["code"] for i in _fixables(b, d)}       # problemas que ja existiam nao entram como "obrigatorio"
    for _ in range(8):
        todo = [i for i in _fixables(nb, d) if i["code"] not in before_fix or i["level"] == "erro"]
        todo.sort(key=lambda i: i["level"] != "erro")
        fixed = False
        for iss in todo:
            target = next((c for c in iss["parts"] if c not in locked), None)
            if not target:
                continue
            old = part(nb, target, d)
            best, best_key = None, None
            for cand in d.parts[target]:
                if cand["id"] == nb["parts"][target]:
                    continue
                tb = copy.deepcopy(nb)
                tb["parts"][target] = cand["id"]
                if target in ("case", "cooler"):
                    reset_fans(tb, d)
                left = _fixables(tb, d)
                if any(x["code"] == iss["code"] for x in left):
                    continue
                n_err = len(errors(check(tb, d)))
                key = (n_err, len(left), _closeness(target, old, cand, part(tb, "mobo", d), part(tb, "ram", d)))
                if best_key is None or key < best_key:
                    best, best_key = cand, key
            if best:
                changes.append({"cat": target, "old": nb["parts"][target], "new": best["id"], "reason": _reason(iss["code"], target, iss["text"])})
                nb["parts"][target] = best["id"]
                if target in ("case", "cooler"):
                    reset_fans(nb, d)
                locked.add(target)
                fixed = True
                break
        if not fixed:
            break
    sanitize_fans(nb, d)
    before = estimate_all(b, d=d)
    after = estimate_all(nb, d=d)
    gains = []
    for (g, e0), (_, e1) in zip(before, after):
        gains.append({"game": g, "before": e0, "after": e1, "gain": (e1["fps"] / e0["fps"] - 1) * 100 if e0["fps"] else 0.0})
    vals = [x["gain"] for x in gains if x["before"]["fps"]]
    avg = (math.prod(1 + v / 100 for v in vals) ** (1 / len(vals)) - 1) * 100 if vals else 0.0
    return {"build": nb, "changed": {"cat": cat, "old": b["parts"].get(cat), "new": new_id}, "changes": changes,
            "issues": check(nb, d), "games": gains, "avg_gain": avg,
            "air_before": airflow(b, d), "air_after": airflow(nb, d), "power_before": power(b, d), "power_after": power(nb, d)}


# ================================================================ escolha passo a passo e busca
STEPS = ["cpu", "mobo", "ram", "cooler", "gpu", "case", "psu", "storage"]


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return " ".join(t.replace("-", " ").replace("_", " ").split())


def haystack(cat: str, p: dict) -> str:
    keys = ("name", "id", "socket", "mem", "type", "form", "chipset", "kind", "rating", "year")
    bits = [p.get(k) for k in keys if p.get(k) is not None]
    bits += p.get("accepts", []) + (p["mem"] if isinstance(p.get("mem"), list) else [])
    if cat == "gpu":
        bits.append(f"{p['vram']}gb {p['vram']} gb")
    if cat == "ram":
        bits.append(f"{p['gb']}gb {p['gb']} gb" + (" ecc reg servidor" if p.get("reg") else ""))
    if cat == "psu":
        bits.append(f"{p['watts']}w {p['watts']} w")
    if cat == "cpu" and p["socket"] in ("LGA2011", "LGA2011-3", "LGA1366"):
        bits.append("xeon servidor kit x99 x79 chines" if p["socket"] != "LGA1366" else "xeon servidor x58")
    if cat == "mobo" and p.get("reg"):
        bits.append("xeon kit chines")
    return norm(" ".join(str(b) for b in bits if not isinstance(b, list)))


def matches(cat: str, p: dict, query: str) -> bool:
    q = norm(query)
    if not q:
        return True
    hs = haystack(cat, p)
    return all(tok in hs for tok in q.split())


def option_problems(b: dict, cat: str, pid: str, d: DB | None = None) -> list[dict]:
    """Erros que esta peca causaria com as que ja foram escolhidas."""
    d = d or db()
    tb = copy.deepcopy(b)
    tb["parts"][cat] = pid
    if cat in ("case", "cooler"):
        reset_fans(tb, d)
    mine = [i for i in errors(check(tb, d)) if cat in i["parts"] or (cat == "gpu" and i["code"] == "psu_w")]
    before = {i["code"] for i in errors(check(b, d))}
    return [i for i in mine if i["code"] not in before or b["parts"].get(cat) == pid]


def options(b: dict, cat: str, query: str = "", d: DB | None = None) -> list[dict]:
    """Pecas da categoria que batem com a busca, compativeis primeiro (e as mais fortes/novas no topo)."""
    d = d or db()
    out = []
    for p in d.parts[cat]:
        if not matches(cat, p, query):
            continue
        probs = option_problems(b, cat, p["id"], d)
        out.append({"part": p, "ok": not probs, "why": "; ".join(i["text"] for i in probs)})
    key = {"cpu": lambda p: -p["score"], "gpu": lambda p: -p["score"], "psu": lambda p: p["watts"], "ram": lambda p: (-p["gb"], -p["speed"]),
           "cooler": lambda p: -p["capacity"], "storage": lambda p: -p["read"]}.get(cat, lambda p: 0)
    out.sort(key=lambda o: (not o["ok"], key(o["part"])))
    return out


def pick(b: dict, cat: str, pid: str, d: DB | None = None) -> list[str]:
    """Escolhe a peca; desmarca as outras que ficaram incompativeis com ela. Devolve as categorias desmarcadas."""
    d = d or db()
    b["parts"][cat] = pid
    if cat in ("case", "cooler"):
        reset_fans(b, d)
    cleared = []
    for _ in range(4):
        bad = [i for i in errors(check(b, d)) if cat in i["parts"]]
        others = [c for i in bad for c in i["parts"] if c != cat and b["parts"].get(c) and c not in cleared]
        if not others:
            break
        for c in dict.fromkeys(others):
            b["parts"][c] = ""
            cleared.append(c)
            if c in ("case", "cooler"):
                reset_fans(b, d)
    return cleared


def next_step(b: dict, after: str | None = None) -> str | None:
    order = STEPS[STEPS.index(after) + 1:] + STEPS[:STEPS.index(after) + 1] if after else STEPS
    return next((c for c in order if not b["parts"].get(c) and c != after and (c != "gpu" or after != "gpu")), None)


# ================================================================ relatorio
def report(b: dict, d: DB | None = None) -> str:
    d = d or db()
    res, q = b.get("res", "1440p"), b.get("quality", "alto")
    L = [f"{APP_NAME} // RELATÓRIO DA MONTAGEM", "Tudo aqui é ESTIMATIVA de um modelo simples (veja o README), não medição.", ""]
    L.append("PEÇAS")
    for c in CATS:
        L.append(f"  {CAT_NAME[c]:<24} {d.name(c, b['parts'].get(c)) if b['parts'].get(c) else ('(vídeo integrado)' if c == 'gpu' else '—')}")
    rows = estimate_all(b, res, q, d)
    L += ["", f"DESEMPENHO ESPERADO · {res} · qualidade {QUALITY_NAME[q].lower()}"]
    for g, e in rows:
        L.append(f"  {g['name']:<32} {e['fps']:>4} FPS  (1% low ~{e['low']})  limita: {e['limit']}" + ("  · falta VRAM" if e["vram_short"] else ""))
    L.append("  " + bottleneck_summary(rows))
    air, full = airflow(b, d), airflow(b, d, full_load=True)
    L += ["", "AIRFLOW E TEMPERATURAS"]
    fans = [f"{POS_NAME[p]} {f['count']}x{f['size']} mm " + ("entrada" if f["dir"] == "in" else "saída") for p, f in b["fans"].items()]
    L.append(f"  Fans: {', '.join(fans) or 'nenhum'}")
    L.append(f"  Entrada {air['intake']} CFM · saída {air['exhaust']} CFM · pressão {air['pressure']} · fluxo útil ~{air['flow']} CFM")
    L.append(f"  Caminho do ar: {air['path']}")
    L.append(f"  Ambiente {b.get('ambient', 25)} °C · ar dentro do gabinete ~{air['case_air']} °C")
    if air["cpu"] is not None:
        L.append(f"  Processador: ~{air['cpu']} °C jogando, ~{full['cpu']} °C em carga total" + (" (no limite: reduz a frequência)" if full["cpu_throttle"] else ""))
    if air["gpu"] is not None:
        L.append(f"  Placa de vídeo: ~{air['gpu']} °C jogando")
    pw = power(b, d)
    psu = part(b, "psu", d)
    L += ["", "CONSUMO E FONTE"]
    L.append(f"  Jogando ~{pw['game']} W (~{pw['wall_game']} W na tomada) · pico ~{pw['peak']} W")
    L.append(f"  Fonte recomendada: {pw['recommended']} W" + (f" · escolhida: {psu['watts']} W ({psu['rating']}), {pw['load_pct']}% de carga jogando" if psu else ""))
    st = part(b, "storage", d)
    if st:
        f = LOAD_FACTOR[st["kind"]]
        L.append(f"  Carregamento: {'referência (NVMe)' if f == 1 else f'~{round((f - 1) * 100)}% mais lento que um NVMe'}")
    iss = check(b, d)
    L += ["", "AVISOS"]
    L += [f"  [{i['level'].upper()}] {i['text']}" for i in iss] or ["  Nenhum: tudo compatível."]
    return "\n".join(L) + "\n"


# ================================================================ salvar
def save_build(b: dict, path: Path = BUILD_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")


def load_build(path: Path = BUILD_FILE, d: DB | None = None) -> dict:
    d = d or db()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        b = new_build({c: v for c, v in raw.get("parts", {}).items() if c in CATS and d.get(c, v)}, d)
        for k in ("ambient", "res", "quality", "radiator"):
            if k in raw:
                b[k] = raw[k]
        if isinstance(raw.get("fans"), dict):
            b["fans"] = raw["fans"]
        sanitize_fans(b, d)
        if b["res"] not in RES:
            b["res"] = "1440p"
        if b["quality"] not in QUALITY:
            b["quality"] = "alto"
        return b
    except (OSError, ValueError, KeyError, TypeError):
        return from_preset("medio", d)
