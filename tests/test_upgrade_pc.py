"""Leitura do PC (com saidas de exemplo) e sugestoes de upgrade na mesma plataforma e de plataforma.

    python tests/test_upgrade_pc.py
"""
import os
import sys
import tempfile
from pathlib import Path

T = Path(tempfile.mkdtemp())
os.environ.update(HOME=str(T), XDG_CONFIG_HOME=str(T / ".config"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from arasaka_techie import core as C, hw  # noqa: E402

FX = Path(__file__).resolve().parent / "fixtures" / "hw"

# ---------------------------------------------------------------- leitura
mem = hw.parse_udev_memory((FX / "udev-ddr5.txt").read_text())
assert mem == {"type": "DDR5", "gb": 64, "sticks": 2, "speed": 4000, "part": "CT32G48C40S5.C16A1", "reg": False, "slots": 4, "max_gb": 128}, mem
assert hw.parse_udev_memory("") == {}
reg = hw.parse_udev_memory("E: MEMORY_DEVICE_0_SIZE=17179869184\nE: MEMORY_DEVICE_0_TYPE=DDR4\nE: MEMORY_DEVICE_0_TYPE_DETAIL=Synchronous Registered (Buffered)\nE: MEMORY_DEVICE_0_CONFIGURED_SPEED_MTS=2133\n")
assert reg["reg"] and reg["speed"] == 2133 and reg["sticks"] == 1
disks = hw.parse_lsblk((FX / "lsblk.txt").read_text())
assert [x["name"] for x in disks] == ["nvme0n1", "nvme1n1", "sda", "sdb"] and disks[2]["kind"] == "sata", disks
assert hw.parse_lsblk("sdc 1 sata 2000398934016 ST2000DM008\nsdd 0 usb 64000000000 Pendrive")[0]["kind"] == "hdd"
gpus = hw.parse_lspci((FX / "lspci.txt").read_text())
assert {g["vendor"] for g in gpus} == {"nvidia", "amd"}
assert hw.parse_nvidia_smi("NVIDIA GeForce RTX 5070 Ti, 16303 MiB\n") == [{"name": "NVIDIA GeForce RTX 5070 Ti", "vram": 16, "vendor": "nvidia"}]
assert hw.parse_cpuinfo("processor : 0\nmodel name\t: AMD Ryzen 9 9950X3D 16-Core Processor\n") == "AMD Ryzen 9 9950X3D 16-Core Processor"

# ---------------------------------------------------------------- casar com a base
def m(cat, text, vram=0):
    p, _ = hw.match(cat, text, vram)
    return p["id"] if p else None


assert m("cpu", "AMD Ryzen 9 9950X3D 16-Core Processor") == "r9-9950x3d"
assert m("cpu", "AMD Ryzen 7 7800X3D 8-Core Processor") == "r7-7800x3d"
assert m("cpu", "AMD Ryzen 5 7600 6-Core Processor") == "r5-7600"
assert m("cpu", "AMD Ryzen 5 7600X 6-Core Processor") == "r5-7600x"
assert m("cpu", "Intel(R) Core(TM) i5-10400F CPU @ 2.90GHz") == "i5-10400f"
assert m("cpu", "Intel(R) Core(TM) i5-10400 CPU @ 2.90GHz") is None, "10400 sem F nao vira 10400F"
assert m("cpu", "Intel(R) Xeon(R) CPU E5-2666 v3 @ 2.90GHz") == "e5-2666v3"
assert m("cpu", "Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz") == "q9550"
assert m("cpu", "AMD FX(tm)-8350 Eight-Core Processor") == "fx-8350"
assert m("gpu", "NVIDIA GeForce RTX 5070 Ti", 16) == "rtx-5070ti"
assert m("gpu", "NVIDIA GeForce RTX 5070", 12) == "rtx-5070"
assert m("gpu", "GA106 [GeForce RTX 3060 Lite Hash Rate]") == "rtx-3060"
assert m("gpu", "NVIDIA GeForce RTX 4060 Ti", 8) == "rtx-4060ti8"
p, amb = hw.match("gpu", "Navi 32 [Radeon RX 7700 XT / 7800 XT]")
assert p and amb, "lspci da AMD com dois modelos fica marcado para conferir"
assert hw.match_board("MAG B550 TOMAHAWK (MS-7C91)")["id"] == "b550-tomahawk"
assert hw.match_board("MAG X870E TOMAHAWK WIFI (MS-7E59)") is None
bp = hw.board_part("MAG X870E TOMAHAWK WIFI (MS-7E59)", "AM5", mem)
assert bp["chipset"] == "X870E" and bp["form"] == "ATX" and bp["mem"] == "DDR5" and bp["slots"] == 4 and bp["name"] == "MAG X870E TOMAHAWK WIFI"
assert hw.board_part("ROG STRIX B650E-I GAMING WIFI", "AM5", mem)["form"] == "ITX"
assert hw.board_part("PRIME B650M-A", "AM5", mem)["form"] == "mATX"

raw = {"cpu": "AMD Ryzen 9 9950X3D 16-Core Processor", "board": "MAG X870E TOMAHAWK WIFI (MS-7E59)", "board_vendor": "MSI",
       "mem": mem, "disks": disks, "gpus": [{"name": "NVIDIA GeForce RTX 5070 Ti", "vram": 16, "vendor": "nvidia"}] + gpus[1:]}
det = hw.detect(raw)
assert det["parts"] == {"cpu": "r9-9950x3d", "mobo": "pc:mobo", "ram": "pc:ram", "gpu": "rtx-5070ti", "storage": "pc:storage"}, det["parts"]
assert any("4000 MT/s" in n for n in det["notes"]), "avisa da memoria abaixo do normal"
b = hw.apply(C.from_preset("medio"), det)
assert not C.errors(C.check(b)), C.check(b)
assert b["parts"]["psu"] == "rm750e" and b["parts"]["case"] == "fractal-north", "fonte e gabinete continuam os da montagem"
assert C.part_name(b, "mobo").endswith("(do seu PC)") and C.part(b, "ram")["speed"] == 4000
C.save_build(b)
assert C.load_build() == b, "pecas do PC sobrevivem a salvar e abrir"
det2 = hw.detect({"cpu": "Processador Misterioso 3000", "board": "", "mem": {}, "disks": [], "gpus": []})
assert "cpu" not in det2["parts"] and any("não está na base" in n for n in det2["notes"])

# ---------------------------------------------------------------- mesma plataforma
s = C.suggest_same_platform(b)
assert s["gpu"] and all(x["gain"] > 5 for x in s["gpu"]), "GPU mais forte rende"
assert all(C.db().get("cpu", x["id"])["socket"] == "AM5" for x in s["cpu"]), "processador so do mesmo soquete"
for cat in ("cpu", "gpu", "ram"):
    for x in s[cat]:
        assert not {"mobo"} & {c["cat"] for c in x["changes"]}, "na mesma plataforma a placa-mae fica"
old = C.from_preset("entrada")                         # Ryzen 5 5600 (AM4) + RX 6600
s = C.suggest_same_platform(old)
assert all(C.db().get("cpu", x["id"])["socket"] == "AM4" for x in s["cpu"])
assert all(C.db().get("ram", x["id"])["type"] == "DDR4" for x in s["ram"])
assert s["gpu"][0]["gain"] > 10 and s["gpu"][-1]["gain"] >= s["gpu"][0]["gain"]
one = C.from_preset("medio")
one["parts"]["ram"] = "ddr5-1x16-5600"
s = C.suggest_same_platform(one)
assert s["ram"] and C.db().get("ram", s["ram"][0]["id"])["sticks"] >= 2 and any("dual channel" in n for n in s["notes"])
ant = C.from_preset("antigo")                          # HD no PC antigo
s = C.suggest_same_platform(ant)
assert s["storage"] and "carregamento" in s["storage"][0]["note"]
assert all(C.db().get("cpu", x["id"])["socket"] == "LGA1155" for x in s["cpu"])

# ---------------------------------------------------------------- troca de plataforma
r = C.suggest_platform(ant)
assert r["tiers"] and {t["tier"] for t in r["tiers"]} <= {"entrada", "equilibrado", "topo"}
for t in r["tiers"]:
    cats = {c["cat"] for c in t["changes"]}
    assert "mobo" in cats and "ram" in cats, "plataforma nova = placa-mae e memoria novas"
    assert not t["errors"] and t["cpu_gain"] > 50
    assert C.db().get("cpu", t["id"])["socket"] in C.PLATFORM_TARGETS
assert "placa de vídeo limita" in r["note"], "GTX 750 Ti limita: avisa que a plataforma rende pouco agora"
assert C.suggest_platform(b)["tiers"] == [] and "ponta" in C.suggest_platform(b)["note"]
tiers = C.pick_tiers([{"id": str(i), "gain": g, "errors": [], "cost": c, "no_price": 0} for i, (g, c) in enumerate([(5, 500), (15, 900), (40, 1500), (80, 6000)])])
assert [t["tier"] for t in tiers][0] == "custo-benefício" and tiers[-1]["gain"] == 80

# Windows: o JSON da consulta WMI vira o mesmo formato do Linux (enums como texto ou numero)
import json as _json  # noqa: E402
win = hw.parse_windows(_json.dumps({
    "cpu": "AMD Ryzen 9 9950X3D 16-Core Processor ", "board": "MAG X870E TOMAHAWK WIFI (MS-7E59)", "board_vendor": "Micro-Star",
    "mem": [{"Capacity": 34359738368, "ConfiguredClockSpeed": 6000, "Speed": 4800, "SMBIOSMemoryType": 34, "PartNumber": "CT32G48C40S5 ", "TypeDetail": 128},
            {"Capacity": 34359738368, "ConfiguredClockSpeed": 6000, "Speed": 4800, "SMBIOSMemoryType": 34, "PartNumber": "CT32G48C40S5", "TypeDetail": 128}],
    "mem_slots": 4, "mem_max_kb": 134217728,
    "disks": [{"FriendlyName": "ST2000DM008", "MediaType": "HDD", "BusType": "SATA", "Size": 2000398934016},
              {"FriendlyName": "WD_BLACK SN770 500GB", "MediaType": 4, "BusType": 17, "Size": 500107862016},
              {"FriendlyName": "Pendrive", "MediaType": "SSD", "BusType": "USB", "Size": 64000000000}],
    "video": [{"Name": "NVIDIA GeForce RTX 5070 Ti", "AdapterCompatibility": "NVIDIA"},
              {"Name": "Microsoft Basic Display Adapter", "AdapterCompatibility": "(Standard display types)"}]}))
assert win["cpu"] == "AMD Ryzen 9 9950X3D 16-Core Processor" and win["board"].startswith("MAG X870E")
assert win["mem"] == {"type": "DDR5", "gb": 64, "sticks": 2, "speed": 6000, "part": "CT32G48C40S5", "reg": False, "slots": 4, "max_gb": 128}
assert [(d["kind"], d["gb"]) for d in win["disks"]] == [("nvme", 500), ("hdd", 2000)], "pendrive USB fica fora"
assert win["gpus"] == [{"name": "NVIDIA GeForce RTX 5070 Ti", "vendor": "nvidia", "vram": 0}], "adaptador basico fica fora"
assert hw.parse_windows("") == {"cpu": "", "board": "", "board_vendor": "", "mem": {}, "disks": [], "gpus": []}
print("■ upgrade do PC: tudo certo")
