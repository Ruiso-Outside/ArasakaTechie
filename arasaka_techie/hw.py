"""
ARASAKA TECHIE // le as pecas do PC (sem root) e casa com a base de pecas.

Fontes (Linux): /proc/cpuinfo, /sys/class/dmi/id (placa-mae), udev (pentes de memoria: tipo, tamanho e
velocidade configurada), lsblk (discos), nvidia-smi e lspci (placa de video). Fonte, gabinete e cooler o
sistema nao enxerga: ficam como estao na montagem.
O que nao esta na base (ex.: uma placa-mae diferente) vira uma peca "do seu PC" montada com o que foi lido.
As funcoes parse_* recebem o texto dos comandos, para dar para testar sem o hardware.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from . import core

VARIANTS = {"ti", "super", "xt", "xtx", "x3d", "k", "kf", "f", "g", "gre", "x"}
MEM_CL = {"DDR3": 11, "DDR4": 16, "DDR5": 40}
DISK_READ = {"nvme": 3500, "sata": 550, "hdd": 150}


def sh(args: list[str], timeout: float = 10) -> str:
    if not shutil.which(args[0]):
        return ""
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def read(path: str) -> str:
    try:
        return Path(path).read_text(errors="ignore")
    except OSError:
        return ""


def tokens(text: str) -> list[str]:
    t = core.norm(re.sub(r"\(r\)|\(tm\)|®|™", " ", text, flags=re.I))
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return t.split()


# ================================================================ leitura
def parse_cpuinfo(text: str) -> str:
    m = re.search(r"^model name\s*:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def parse_udev_memory(text: str) -> dict:
    """Pentes de memoria do 'udevadm info -e' (dmi/memory): tipo, tamanho, velocidade, registrada?"""
    dev: dict[str, dict] = {}
    info = {}
    for k, v in re.findall(r"^E: (MEMORY_[A-Z0-9_]+)=(.*)$", text, re.M):
        m = re.match(r"MEMORY_DEVICE_(\d+)_(.+)", k)
        if m:
            dev.setdefault(m.group(1), {})[m.group(2)] = v.strip()
        elif k.startswith("MEMORY_ARRAY_"):
            info[k[13:]] = v.strip()
    sticks = [d for d in dev.values() if d.get("SIZE", "0").isdigit() and int(d.get("SIZE", "0")) > 0 and d.get("PRESENT") != "0"]
    if not sticks:
        return {}
    types = [d.get("TYPE", "") for d in sticks if d.get("TYPE", "").startswith("DDR")]
    speeds = [int(d[k]) for d in sticks for k in ("CONFIGURED_SPEED_MTS", "SPEED_MTS") if d.get(k, "").isdigit()][:1] or [0]
    parts = sorted({d.get("PART_NUMBER", "") for d in sticks} - {"", "Unknown"})
    return {"type": types[0] if types else "", "gb": round(sum(int(d["SIZE"]) for d in sticks) / 1024 ** 3), "sticks": len(sticks),
            "speed": speeds[0], "part": parts[0] if parts else "", "reg": any("Registered (Buffered)" in d.get("TYPE_DETAIL", "") for d in sticks),
            "slots": int(info["NUM_DEVICES"]) if info.get("NUM_DEVICES", "").isdigit() else 0,
            "max_gb": round(int(info["MAX_CAPACITY"]) / 1024 ** 3) if info.get("MAX_CAPACITY", "").isdigit() else 0}


def parse_lsblk(text: str) -> list[dict]:
    """'lsblk -d -b -n -o NAME,ROTA,TRAN,SIZE,MODEL' -> discos (sem loop, cdrom, zram)."""
    out = []
    for ln in text.splitlines():
        p = ln.split(None, 4)
        if len(p) < 4 or p[0].startswith(("loop", "sr", "zram", "ram")):
            continue
        name, rota, tran, size = p[:4]
        if not size.isdigit() or int(size) < 16 * 1024 ** 3:
            continue
        kind = "hdd" if rota == "1" else ("nvme" if name.startswith("nvme") or tran == "nvme" else "sata")
        if tran == "usb":
            continue
        out.append({"name": name, "kind": kind, "gb": round(int(size) / 1e9), "model": (p[4] if len(p) > 4 else "").strip()})
    order = {"nvme": 0, "sata": 1, "hdd": 2}
    out.sort(key=lambda x: (order[x["kind"]], -x["gb"]))
    return out


def parse_nvidia_smi(text: str) -> list[dict]:
    out = []
    for ln in text.strip().splitlines():
        p = [x.strip() for x in ln.split(",")]
        if p and p[0]:
            vram = re.search(r"(\d+)", p[1]) if len(p) > 1 else None
            out.append({"name": p[0], "vram": round(int(vram.group(1)) / 1024) if vram else 0, "vendor": "nvidia"})
    return out


def parse_lspci(text: str) -> list[dict]:
    """'lspci -mm' -> placas de video (VGA/3D/Display)."""
    out = []
    for ln in text.splitlines():
        p = re.findall(r'"([^"]*)"', ln)
        if len(p) >= 3 and re.search(r"VGA|3D|Display", p[0]):
            vend = p[1].lower()
            vendor = "nvidia" if "nvidia" in vend else "amd" if ("amd" in vend or "ati" in vend) else "intel" if "intel" in vend else "outro"
            out.append({"name": p[2], "vendor": vendor, "vram": 0})
    return out


def read_system() -> dict:
    """Le o PC de verdade. Devolve o texto/infos brutos (para casar depois)."""
    dmi = "/sys/class/dmi/id/"
    gpus = parse_nvidia_smi(sh(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]))
    others = [g for g in parse_lspci(sh(["lspci", "-mm"])) if g["vendor"] != "nvidia" or not gpus]
    return {"cpu": parse_cpuinfo(read("/proc/cpuinfo")), "board": read(dmi + "board_name").strip(), "board_vendor": read(dmi + "board_vendor").strip(),
            "mem": parse_udev_memory(sh(["udevadm", "info", "-e"], 20)), "disks": parse_lsblk(sh(["lsblk", "-d", "-b", "-n", "-o", "NAME,ROTA,TRAN,SIZE,MODEL"])),
            "gpus": gpus + others}


# ================================================================ casar com a base
def _model_ok(db_name: str, found: list[str]) -> tuple[bool, int]:
    """A peca da base casa se todos os numeros/variantes do nome dela estao no texto lido e nao sobra variante."""
    want = [t for t in tokens(db_name) if re.search(r"\d", t) or t in VARIANTS]
    # tamanho de memoria (ex.: "12 GB") nao aparece no lspci: nao exige
    toks = tokens(db_name)
    want = [t for i, t in enumerate(toks) if t in want and not (i + 1 < len(toks) and toks[i + 1] == "gb")]
    if not want or not all(t in found for t in want):
        return False, 0
    for i, t in enumerate(found):
        if t in want and re.search(r"\d", t) and i + 1 < len(found) and found[i + 1] in VARIANTS and found[i + 1] not in want:
            return False, 0
    return True, len(want)


def match(cat: str, text: str, vram: int = 0, d: core.DB | None = None) -> tuple[dict | None, bool]:
    """(peca, ambigua). Ambigua = mais de uma peca da base serve (ex.: lspci "RX 7700 XT / 7800 XT")."""
    d = d or core.db()
    if not text:
        return None, False
    found = tokens(text)
    hits = []
    for p in d.parts[cat]:
        ok, n = _model_ok(p["name"], found)
        if ok:
            bonus = 5 if vram and p.get("vram") == vram else 0
            hits.append((n + bonus, p))
    if not hits:
        return None, False
    hits.sort(key=lambda h: -h[0])
    amb = len(hits) > 1 and hits[0][0] == hits[1][0]
    return hits[0][1], amb


def match_board(name: str, d: core.DB | None = None) -> dict | None:
    d = d or core.db()
    found = set(tokens(name))
    brand = {"asus", "msi", "gigabyte", "asrock", "rog", "prime", "tuf", "gaming", "wifi", "aorus", "pro", "plus", "ac", "d4", "ii"}
    for p in d.parts["mobo"]:
        key = [t for t in tokens(p["name"]) if t not in brand and len(t) >= 3]
        if key and all(t in found for t in key) and len(found & set(tokens(p["name"]))) >= 2:
            return p
    return None


def board_part(name: str, socket: str, mem: dict) -> dict:
    """Placa-mae que nao esta na base, montada com o que foi lido."""
    up = name.upper()
    chip = re.search(r"\b([ABHXZQ]\d{2,3}[EM]?)\b", up)
    form = "ITX" if re.search(r"-I\b|\bITX\b", up) else "mATX" if re.search(r"\b[ABHXZ]\d{3}M\b|\bMATX\b|MICRO", up) else "ATX"
    return {"id": "pc:mobo", "name": re.sub(r"\s*\(MS-\w+\)", "", name).strip() or "Placa-mãe do seu PC", "socket": socket or "?",
            "chipset": chip.group(1).rstrip("M") if chip else "?", "form": form, "mem": mem.get("type") or "DDR4",
            "slots": mem.get("slots") or max(2, mem.get("sticks", 2)), "max_mem": mem.get("max_gb") or 128, "m2": 2,
            "reg": bool(mem.get("reg")), "detected": True}


def ram_part(mem: dict) -> dict:
    t = mem["type"] or "DDR4"
    name = f"{mem['gb']} GB ({mem['sticks']}x{mem['gb'] // max(1, mem['sticks'])}) {t}-{mem['speed']}" + (f" · {mem['part']}" if mem.get("part") else "")
    return {"id": "pc:ram", "name": name, "type": t, "gb": mem["gb"], "sticks": mem["sticks"], "speed": mem["speed"] or core.MEM_REF.get(t, 3200),
            "cl": MEM_CL.get(t, 16), "reg": bool(mem.get("reg")), "detected": True}


def disk_part(disk: dict) -> dict:
    return {"id": "pc:storage", "name": f"{disk['model'] or disk['name']} ({disk['gb']} GB, {disk['kind'].upper()})", "kind": disk["kind"],
            "gb": disk["gb"], "read": DISK_READ[disk["kind"]], "power": 7 if disk["kind"] == "hdd" else 5, "detected": True}


def detect(raw: dict | None = None, d: core.DB | None = None) -> dict:
    """Le o PC e devolve {'parts': {cat: id}, 'custom': {cat: peca}, 'found': {cat: texto lido}, 'notes': [...]}"""
    d = d or core.db()
    raw = raw if raw is not None else read_system()
    parts, custom, found, notes = {}, {}, {}, []
    cpu, amb = match("cpu", raw.get("cpu", ""), d=d)
    found["cpu"] = raw.get("cpu", "")
    if cpu:
        parts["cpu"] = cpu["id"]
        if amb:
            notes.append(f"Processador: confira se é mesmo o {cpu['name']}.")
    elif found["cpu"]:
        notes.append(f"Processador \"{found['cpu']}\" não está na base: escolha o mais parecido na aba Montagem.")
    mem = raw.get("mem") or {}
    found["board"] = raw.get("board", "")
    board = match_board(found["board"], d) if found["board"] else None
    if board:
        parts["mobo"] = board["id"]
    elif found["board"]:
        custom["mobo"] = board_part(found["board"], cpu["socket"] if cpu else "", mem)
        parts["mobo"] = "pc:mobo"
        if not cpu:
            notes.append("Placa-mãe lida, mas sem o processador o soquete fica desconhecido.")
    if mem.get("gb"):
        custom["ram"] = ram_part(mem)
        parts["ram"] = "pc:ram"
        found["ram"] = custom["ram"]["name"]
        ref = core.MEM_REF.get(custom["ram"]["type"])
        if ref and custom["ram"]["speed"] and custom["ram"]["speed"] < ref * 0.8:
            notes.append(f"A memória está rodando a {custom['ram']['speed']} MT/s: ativar o perfil EXPO/XMP na BIOS (se o pente aguentar) dá FPS de graça.")
    gpus = [g for g in raw.get("gpus", []) if g["vendor"] in ("nvidia", "amd", "intel")]
    gpu_hit = None
    for g in gpus:
        p, amb = match("gpu", g["name"], g.get("vram", 0), d)
        if p:
            gpu_hit = (p, amb, g)
            break
    if gpu_hit:
        parts["gpu"] = gpu_hit[0]["id"]
        found["gpu"] = gpu_hit[2]["name"]
        if gpu_hit[1]:
            notes.append(f"Placa de vídeo: \"{gpu_hit[2]['name']}\" pode ser mais de um modelo. Confira se é a {gpu_hit[0]['name']}.")
    else:
        dgpu = [g for g in gpus if not re.search(r"Granite Ridge|Raphael|Radeon Graphics|UHD|Iris|HD Graphics|Renoir|Cezanne|Phoenix", g["name"], re.I)]
        if dgpu:
            found["gpu"] = dgpu[0]["name"]
            notes.append(f"Placa de vídeo \"{dgpu[0]['name']}\" não reconhecida: escolha na aba Montagem.")
        else:
            parts["gpu"] = ""
    disks = raw.get("disks") or []
    if disks:
        custom["storage"] = disk_part(disks[0])
        parts["storage"] = "pc:storage"
        found["storage"] = custom["storage"]["name"] + (f" + {len(disks) - 1} disco(s)" if len(disks) > 1 else "")
    notes.append("Fonte, gabinete e cooler o sistema não informa: ficaram os da montagem atual. Confira na aba Montagem.")
    return {"parts": parts, "custom": custom, "found": found, "notes": notes}


def apply(b: dict, det: dict, d: core.DB | None = None) -> dict:
    """Montagem nova com as pecas lidas do PC (fonte, gabinete e cooler continuam os da montagem atual)."""
    import copy
    d = d or core.db()
    nb = copy.deepcopy(b)
    nb.setdefault("custom", {})
    for cat in ("cpu", "mobo", "ram", "gpu", "storage"):
        if cat in det["parts"]:
            nb["parts"][cat] = det["parts"][cat]
    nb["custom"] = {k: v for k, v in nb["custom"].items() if nb["parts"].get(k, "").startswith("pc:")}
    nb["custom"].update(det["custom"])
    nb["from_pc"] = True
    core.sanitize_fans(nb, d)
    return nb
