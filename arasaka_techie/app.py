"""
ARASAKA TECHIE // interface (PySide6 / Qt 6): montagem, desempenho, airflow, upgrade e relatorio.
"""
from __future__ import annotations

import copy
import math
import sys
import threading

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStackedWidget,
                               QVBoxLayout, QWidget)

from . import core, fx, prices
from .core import APP_NAME, CAT_NAME, CATS, POS_NAME, VERSION
from .kit import BG2, FG, LINE, MUTED, RED, CutFrame, Page, SidebarBrand, button, label, load_fonts, spaced, stylesheet

EXTRA_QSS = """
QSpinBox { background: #050506; border: 1px solid #2a2a31; padding: 6px 8px; selection-background-color: #e3121f; }
QSpinBox:focus { border-color: #e3121f; }
QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: #141418; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #e3121f; }
QPlainTextEdit#report { background: #030304; border: 1px solid #2a2a31; color: #d6d6dc; font-family: monospace; font-size: 12px; padding: 8px; }
QLabel#warn { color: #e0a030; font-weight: 700; }
QLabel#ok { color: #4fd18b; font-weight: 700; }
QLabel#big { font-size: 30px; font-weight: 700; }
QPushButton#step { text-align: left; padding: 7px 9px; font-size: 11px; color: #8c8c96; background: #0b0b0e; border: 1px solid #1d1d22; border-bottom: 2px solid #1d1d22; }
QPushButton#step[done="true"] { color: #ececf0; border-bottom: 2px solid #5a080e; }
QPushButton#step:checked { color: #ffffff; background: rgba(227,18,31,0.16); border: 1px solid #e3121f; border-bottom: 2px solid #e3121f; }
QFrame#opt { background: #0b0b0e; border: 1px solid #1d1d22; }
QFrame#opt:hover { border-color: #e3121f; background: #160709; }
QFrame#opt[chosen="true"] { border: 1px solid #4fd18b; background: #07140d; }
QFrame#opt[bad="true"] { background: #09090b; }
"""
LEVEL_COLOR = {"erro": QColor(170, 14, 26), "aviso": QColor(150, 110, 20), "info": LINE}
LEVEL_TXT = {"erro": "INCOMPATIVEL", "aviso": "ATENCAO", "info": "INFO"}
INTAKE = QColor(63, 184, 255)
DISCLAIMER = "ESTIMATIVA · modelo simples a partir de pontuações relativas, não é medição. Use para comparar montagens, não como número exato."


def clear(lay):
    while lay.count():
        it = lay.takeAt(0)
        if it.widget():
            it.widget().deleteLater()
        elif it.layout():
            clear(it.layout())


def part_label(cat: str, p: dict) -> str:
    if cat == "cpu":
        return f"{p['name']}  ·  {p['socket']}  ·  {p['cores']}C/{p['threads']}T  ·  {p['max_w']} W"
    if cat == "mobo":
        return f"{p['name']}  ·  {p['socket']}  ·  {p['form']}  ·  {p['mem']}"
    if cat == "gpu":
        return f"{p['name']}  ·  {p['vram']} GB  ·  {p['power']} W  ·  {p['length']} mm"
    if cat == "psu":
        return f"{p['name']}  ·  {p['watts']} W  ·  {p['rating']}"
    if cat == "case":
        return f"{p['name']}  ·  GPU até {p['gpu_max']} mm  ·  cooler até {p['cooler_max']} mm"
    if cat == "cooler":
        return f"{p['name']}  ·  " + (f"radiador {p['radiator']} mm" if p["kind"] == "aio" else f"{p['height']} mm") + f"  ·  ≈{p['capacity']} W"
    return p["name"]


def issue_card(i: dict) -> CutFrame:
    c = CutFrame(cut=10)
    c.set_border(LEVEL_COLOR[i["level"]])
    lay = QHBoxLayout(c)
    lay.setContentsMargins(16, 10, 16, 10)
    t = label(LEVEL_TXT[i["level"]], "red" if i["level"] == "erro" else ("warn" if i["level"] == "aviso" else "muted"), 2, 11, True)
    t.setFixedWidth(120)
    lay.addWidget(t)
    lay.addWidget(label(i["text"], None, 0.5, wrap=True), 1)
    return c


def stat(title: str, value: str, obj: str | None = None, sub: str = "") -> CutFrame:
    c = CutFrame(cut=10)
    lay = QVBoxLayout(c)
    lay.setContentsMargins(16, 10, 16, 12)
    lay.setSpacing(2)
    lay.addWidget(label(title, "muted", 2, 11, True))
    v = label(value, obj, 1, 22, True)
    lay.addWidget(v)
    if sub:
        lay.addWidget(label(sub, "dim", 0.5, 11, wrap=True))
    return c


def banner() -> QLabel:
    lb = label(DISCLAIMER, "warn", 1, 12, True, wrap=True)
    lb.setStyleSheet("border:1px solid #5a4210; background:#120d04; padding:8px 12px;")
    return lb


class Bar(QWidget):
    """Barra de FPS: verde >=144, branca >=60, amarela >=30, vermelha abaixo. Marca 60 e 144."""

    def __init__(self, fps: float, scale: float, ghost: float | None = None):
        super().__init__()
        self.fps, self.scale, self.ghost = fps, max(scale, 1), ghost
        self.setMinimumHeight(14)
        self.setMinimumWidth(160)

    def paintEvent(self, _e):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 3, w, h - 6, QColor(20, 20, 24))
        col = QColor(79, 209, 139) if self.fps >= 144 else FG if self.fps >= 60 else QColor(224, 160, 48) if self.fps >= 30 else RED
        if self.ghost is not None:
            p.fillRect(0, 3, int(w * min(1, self.ghost / self.scale)), h - 6, QColor(70, 70, 80))
        p.fillRect(0, 3, int(w * min(1, self.fps / self.scale)), h - 6, col)
        p.setPen(QPen(QColor(227, 18, 31, 160), 1))
        for mark in (60, 144):
            if mark < self.scale:
                x = int(w * mark / self.scale)
                p.drawLine(x, 0, x, h)


# ================================================================ diagrama do gabinete
class CaseDiagram(QWidget):
    """Vista lateral do gabinete: frente a esquerda, traseira a direita. Fans em azul (entrada) e vermelho (saida)."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setMinimumSize(460, 500)

    def paintEvent(self, _e):
        b, d = self.win.build, core.db()
        case = core.part(b, "case")
        air = core.airflow(b)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, QColor(5, 5, 6))
        if not case:
            p.setPen(MUTED)
            p.drawText(self.rect(), Qt.AlignCenter, "Escolha um gabinete")
            return
        itx = case["forms"] == ["ITX"]
        real_h, real_w = (380, 360) if itx else (480, 450)        # medidas internas tipicas em mm
        sc = min((H - 90) / real_h, (W - 120) / real_w) * (0.8 if itx else 1.0)
        bw, bh = real_w * sc, real_h * sc
        x0, y0 = (W - bw) / 2, 34
        box = QRectF(x0, y0, bw, bh)
        p.setPen(QPen(QColor(90, 90, 100), 2))
        p.setBrush(QColor(12, 12, 15))
        p.drawRect(box)
        f = QFont(p.font())
        f.setPixelSize(11)
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        p.setFont(f)
        p.setPen(QColor(85, 85, 94))
        p.drawText(QRectF(0, y0 + bh + 6, x0 + 80, 18), Qt.AlignRight, "◀ FRENTE")
        p.drawText(QRectF(x0 + bw - 80, y0 + bh + 6, 80, 18), Qt.AlignRight, "TRAS ▶")
        # placa-mae, cooler, gpu, fonte
        mb = QRectF(x0 + bw * 0.42, y0 + 14, bw * 0.52, bh * 0.66)
        p.setPen(QPen(QColor(40, 40, 46), 1))
        p.setBrush(QColor(18, 18, 22))
        p.drawRect(mb)
        cpu_c = QPointF(mb.x() + mb.width() * 0.45, mb.y() + mb.height() * 0.28)
        cool = core.part(b, "cooler")
        p.setBrush(QColor(30, 30, 36))
        p.setPen(QPen(QColor(120, 120, 130), 1))
        p.drawRect(QRectF(cpu_c.x() - 22, cpu_c.y() - 22, 44, 44))
        if cool and cool["kind"] != "aio":
            p.drawRect(QRectF(cpu_c.x() - 30, cpu_c.y() - 34, 14, 68))
        gpu = core.part(b, "gpu")
        if gpu:
            gl = bw * min(0.92, gpu["length"] / case["gpu_max"] * 0.9)
            gr = QRectF(x0 + bw - 12 - gl, mb.y() + mb.height() * 0.58, gl, 26)
            p.setBrush(QColor(28, 8, 11))
            p.setPen(QPen(RED, 1))
            p.drawRect(gr)
            if air["gpu"] is not None:
                p.setPen(FG)
                p.drawText(gr, Qt.AlignCenter, f"GPU {air['gpu']:.0f}°C")
        if air["cpu"] is not None:
            p.setPen(FG)
            p.drawText(QRectF(cpu_c.x() - 60, cpu_c.y() + 26, 120, 18), Qt.AlignCenter, f"CPU {air['cpu']:.0f}°C")
        psu = QRectF(x0 + bw * 0.62, y0 + bh - 62, bw * 0.34, 52)
        p.setBrush(QColor(16, 16, 19))
        p.setPen(QPen(QColor(50, 50, 58), 1))
        p.drawRect(psu)
        p.setPen(QColor(85, 85, 94))
        p.drawText(psu, Qt.AlignCenter, "FONTE")
        # fans
        rad = air["radiator"]

        def slot_d(pos):
            slot = case["slots"].get(pos)
            if not slot:
                return 0
            fan = b["fans"].get(pos)
            return (fan["size"] if fan else max(int(k) for k in slot["sizes"])) * sc
        self._top_d, self._bot_d, self._front_d = slot_d("top"), slot_d("bottom"), slot_d("front")
        for pos, slot in case["slots"].items():
            fan = b["fans"].get(pos)
            sizes = {int(k): v for k, v in slot["sizes"].items()}
            size = fan["size"] if fan else max(sizes)
            n_max = sizes.get(size, 0)
            n = fan["count"] if fan else 0
            dia = size * sc
            for k in range(n_max):
                c = self._fan_center(pos, k, n_max, dia, box)
                on = k < n
                if pos == rad and k < n_max:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(60, 20, 24, 120))
                    p.drawRect(QRectF(c.x() - dia / 2 - 2, c.y() - dia / 2 - 2, dia + 4, dia + 4))
                col = (INTAKE if fan and fan["dir"] == "in" else RED) if on else QColor(60, 60, 68)
                pen = QPen(col, 2 if on else 1)
                if not on:
                    pen.setStyle(Qt.DashLine)
                p.setPen(pen)
                p.setBrush(QColor(col.red(), col.green(), col.blue(), 40) if on else Qt.NoBrush)
                p.drawEllipse(c, dia / 2, dia / 2)
                if on:
                    p.drawLine(QPointF(c.x() - dia / 2 * 0.7, c.y()), QPointF(c.x() + dia / 2 * 0.7, c.y()))
                    p.drawLine(QPointF(c.x(), c.y() - dia / 2 * 0.7), QPointF(c.x(), c.y() + dia / 2 * 0.7))
                    self._arrow(p, pos, c, dia, fan["dir"] == "in", col)
            if pos == "side" and n_max:
                p.setPen(QColor(85, 85, 94))
                c = self._fan_center(pos, 0, n_max, dia, box)
                p.drawText(QRectF(c.x() - 60, c.y() - dia / 2 - 18, 120, 16), Qt.AlignCenter, "LATERAL")
        # legenda
        p.setPen(INTAKE)
        p.drawText(QRectF(12, H - 22, 200, 18), Qt.AlignLeft, "■ ENTRADA")
        p.setPen(RED)
        p.drawText(QRectF(110, H - 22, 200, 18), Qt.AlignLeft, "■ SAIDA")
        p.setPen(QColor(85, 85, 94))
        p.drawText(QRectF(190, H - 22, W - 200, 18), Qt.AlignLeft, "TRACEJADO = POSICAO LIVRE" + ("   ▨ RADIADOR" if rad else ""))
        p.setPen(FG)
        p.drawText(QRectF(12, 8, W - 24, 18), Qt.AlignLeft, f"PRESSAO {air['pressure'].upper()}  ·  FLUXO ≈{air['flow']} CFM  ·  AR INTERNO {air['case_air']:.0f}°C")

    def _fan_center(self, pos, k, n, dia, box: QRectF) -> QPointF:
        gap = dia + 4
        if pos in ("front", "rear"):
            top = box.top() + self._top_d + 8
            room = box.bottom() - (self._bot_d + 8 if pos == "front" else 70) - top
            start = top + max(0, (room - n * gap) / 2) if pos == "front" else top
            x = box.left() + dia / 2 + 3 if pos == "front" else box.right() - dia / 2 - 3
            return QPointF(x, start + dia / 2 + k * gap)
        if pos == "top":
            return QPointF(box.left() + box.width() * 0.06 + dia / 2 + k * gap, box.top() + dia / 2 + 3)
        if pos == "bottom":
            return QPointF(box.left() + max(box.width() * 0.06, self._front_d + 10) + dia / 2 + k * gap, box.bottom() - dia / 2 - 3)
        # lateral: no meio, na altura da placa de video
        start = box.center().x() - (n * gap) / 2 + gap / 2
        return QPointF(start + k * gap, box.top() + box.height() * 0.6)

    @staticmethod
    def _arrow(p: QPainter, pos, c: QPointF, dia, inward: bool, col):
        vec = {"front": (1, 0), "rear": (-1, 0), "top": (0, 1), "bottom": (0, -1), "side": (0, 0)}[pos]
        if pos == "side":
            p.setPen(QPen(col, 2))
            p.drawText(QRectF(c.x() - 20, c.y() + dia / 2 + 2, 40, 14), Qt.AlignCenter, "⊙" if inward else "⊗")
            return
        sgn = 1 if inward else -1
        dx, dy = vec[0] * sgn, vec[1] * sgn
        base = QPointF(c.x() - dx * dia * 0.15, c.y() - dy * dia * 0.15) if inward else QPointF(c.x() + dx * -dia * 0.1, c.y() + dy * -dia * 0.1)
        tip = QPointF(base.x() + dx * dia * 0.75, base.y() + dy * dia * 0.75)
        p.setPen(QPen(col, 2.5))
        p.drawLine(base, tip)
        nx, ny = -dy, dx
        head = QPolygonF([tip, QPointF(tip.x() - dx * 8 + nx * 5, tip.y() - dy * 8 + ny * 5), QPointF(tip.x() - dx * 8 - nx * 5, tip.y() - dy * 8 - ny * 5)])
        p.setBrush(col)
        p.drawPolygon(head)


# ================================================================ paginas
class Task(QObject):
    """Roda algo demorado (rede) numa thread daemon e devolve o resultado na thread da interface."""
    done = Signal(object)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def _run(self):
        try:
            r = self.fn(*self.args)
        except Exception as e:  # noqa: BLE001
            r = e
        try:
            self.done.emit(r)
        except RuntimeError:
            pass


class Images(QObject):
    """Fotos das pecas (vindas das lojas pelo servidor de precos), com cache em disco."""
    got = Signal(str, bytes)

    def __init__(self):
        super().__init__()
        self.pix: dict[str, QPixmap] = {}
        self.waiting: dict[str, list] = {}
        self.got.connect(self._got)

    def request(self, url: str, thumb: "Thumb"):
        if not url:
            return
        if url in self.pix:
            thumb.set_pixmap(self.pix[url])
            return
        first = url not in self.waiting
        self.waiting.setdefault(url, []).append(thumb)
        if first:
            threading.Thread(target=lambda: self._load(url), daemon=True).start()

    def _load(self, url):
        data = prices.fetch_image(url) or b""
        try:
            self.got.emit(url, data)
        except RuntimeError:
            pass

    def _got(self, url, data):
        pm = QPixmap()
        if data and pm.loadFromData(data):
            self.pix[url] = pm
        for t in self.waiting.pop(url, []):
            try:
                if url in self.pix:
                    t.set_pixmap(self.pix[url])
            except RuntimeError:
                pass                    # o widget ja foi apagado


class Thumb(QWidget):
    """Foto da peca; sem foto, um desenho da categoria."""

    def __init__(self, cat: str, size: int = 64):
        super().__init__()
        self.cat, self.pm = cat, None
        self.setFixedSize(size, size)

    def set_pixmap(self, pm: QPixmap):
        self.pm = pm
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(8, 8, 10))
        p.setPen(QPen(LINE, 1))
        p.drawRect(0, 0, w - 1, h - 1)
        if self.pm and not self.pm.isNull():
            p.fillRect(1, 1, w - 2, h - 2, QColor(236, 236, 240))
            pm = self.pm.scaled(w - 6, h - 6, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap((w - pm.width()) // 2, (h - pm.height()) // 2, pm)
            return
        s = w / 64
        p.scale(s, s)
        pen = QPen(QColor(150, 150, 160), 2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        c = self.cat
        if c == "cpu":
            p.drawRect(18, 18, 28, 28)
            p.setPen(QPen(RED, 2))
            p.drawRect(25, 25, 14, 14)
            p.setPen(pen)
            for i in range(4):
                for (x1, y1, x2, y2) in ((22 + i * 7, 12, 22 + i * 7, 18), (22 + i * 7, 46, 22 + i * 7, 52), (12, 22 + i * 7, 18, 22 + i * 7), (46, 22 + i * 7, 52, 22 + i * 7)):
                    p.drawLine(x1, y1, x2, y2)
        elif c == "gpu":
            p.drawRect(6, 20, 52, 22)
            p.drawEllipse(QPointF(22, 31), 8, 8)
            p.drawEllipse(QPointF(42, 31), 8, 8)
            p.setPen(QPen(RED, 2))
            p.drawLine(14, 46, 40, 46)
        elif c == "ram":
            p.drawRect(6, 24, 52, 16)
            p.setPen(QPen(RED, 2))
            for i in range(5):
                p.drawRect(10 + i * 9, 28, 6, 8)
            p.setPen(pen)
            for i in range(10):
                p.drawLine(9 + i * 5, 40, 9 + i * 5, 44)
        elif c == "mobo":
            p.drawRect(10, 8, 44, 48)
            p.setPen(QPen(RED, 2))
            p.drawRect(18, 14, 14, 14)
            p.setPen(pen)
            p.drawLine(38, 12, 38, 30)
            p.drawLine(42, 12, 42, 30)
            p.drawLine(16, 38, 48, 38)
            p.drawLine(16, 46, 48, 46)
        elif c == "storage":
            p.drawRect(8, 22, 48, 20)
            p.setPen(QPen(RED, 2))
            p.drawRect(12, 27, 14, 10)
            p.setPen(pen)
            p.drawEllipse(QPointF(48, 32), 3, 3)
        elif c == "psu":
            p.drawRect(10, 14, 44, 36)
            p.drawEllipse(QPointF(32, 32), 12, 12)
            p.setPen(QPen(RED, 2))
            p.drawLine(26, 32, 38, 32)
            p.drawLine(32, 26, 32, 38)
        elif c == "case":
            p.drawRect(18, 6, 28, 52)
            p.setPen(QPen(RED, 2))
            p.drawEllipse(QPointF(32, 22), 7, 7)
            p.drawEllipse(QPointF(32, 40), 7, 7)
        else:
            p.drawEllipse(QPointF(32, 32), 18, 18)
            p.setPen(QPen(RED, 2))
            for i in range(6):
                p.drawLine(QPointF(32, 32), QPointF(32 + 15 * math.cos(i * math.pi / 3), 32 + 15 * math.sin(i * math.pi / 3)))


def verdict_chip(level: str) -> QLabel:
    txt = {"baixo": "PRECO BAIXO", "normal": "PRECO NORMAL", "alto": "PRECO ALTO", "curto": "HISTORICO CURTO"}.get(level, "")
    col = {"baixo": "#4fd18b", "normal": "#8c8c96", "alto": "#ff3b47", "curto": "#55555e"}.get(level, "#55555e")
    lb = label(txt, None, 1.5, 10, True)
    lb.setStyleSheet(f"color:{col}; border:1px solid {col}; padding:2px 6px;")
    return lb


class OptionRow(QFrame):
    """Uma peca na lista da escolha passo a passo."""

    def __init__(self, page, cat: str, opt: dict, chosen: bool, price: dict | None):
        super().__init__()
        self.setObjectName("opt")
        self.setProperty("chosen", chosen)
        self.setProperty("bad", not opt["ok"])
        self.setCursor(Qt.PointingHandCursor)
        self.page, self.cat, self.pid = page, cat, opt["part"]["id"]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 14, 8)
        lay.setSpacing(14)
        th = Thumb(cat, 56)
        if price and price.get("image"):
            page.win.images.request(price["image"], th)
        lay.addWidget(th)
        col = QVBoxLayout()
        col.setSpacing(2)
        p = opt["part"]
        col.addWidget(label(p["name"], None, 0.5, 14, True, wrap=True))
        col.addWidget(label(spec_line(cat, p), "muted", 0.5, 12, wrap=True))
        if not opt["ok"]:
            col.addWidget(label("INCOMPATIVEL: " + opt["why"], "red", 0.5, 11, wrap=True))
        lay.addLayout(col, 1)
        right = QVBoxLayout()
        right.setSpacing(4)
        if chosen:
            right.addWidget(label("■ ESCOLHIDA", "ok", 2, 11, True), 0, Qt.AlignRight)
        if price and isinstance(price.get("price"), (int, float)):
            right.addWidget(label(prices.brl(price["price"]), None, 1, 14, True), 0, Qt.AlignRight)
            right.addWidget(label(price.get("store", ""), "dim", 0.5, 11), 0, Qt.AlignRight)
            if price.get("verdict") in ("baixo", "alto"):
                right.addWidget(verdict_chip(price["verdict"]), 0, Qt.AlignRight)
        lay.addLayout(right)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.page.choose(self.cat, self.pid)


def spec_line(cat: str, p: dict) -> str:
    yr = f"  ·  {p['year']}" if p.get("year") else ""
    if cat == "cpu":
        return f"{p['socket']}  ·  {p['cores']} núcleos / {p['threads']} threads  ·  até {p['boost']} GHz  ·  {'/'.join(p['mem'])}  ·  {p['max_w']} W" + \
            (f"  ·  vídeo {p.get('igpu_name', 'integrado')}" if p["igpu"] else "  ·  sem vídeo integrado") + yr
    if cat == "mobo":
        return f"{'/'.join(core.mobo_sockets(p))}  ·  {p['chipset']}  ·  {p['form']}  ·  {p['mem']} ({p['slots']} slots, até {p['max_mem']} GB)" + \
            ("  ·  aceita memória de servidor" if p.get("reg") else "")
    if cat == "ram":
        return f"{p['type']}  ·  {p['gb']} GB em {p['sticks']} pente(s)  ·  {p['speed']} MT/s CL{p['cl']}" + ("  ·  ECC REG (só placa de Xeon)" if p.get("reg") else "")
    if cat == "gpu":
        return f"{p['vram']} GB  ·  {p['power']} W  ·  {p['length']} mm  ·  fonte de {p['rec_psu']} W" + yr
    if cat == "psu":
        return f"{p['watts']} W  ·  {p['rating']}  ·  {p['form']}"
    if cat == "case":
        return f"{', '.join(p['forms'])}  ·  GPU até {p['gpu_max']} mm  ·  cooler até {p['cooler_max']} mm  ·  fonte {p['psu']}"
    if cat == "cooler":
        return (f"water cooler, radiador {p['radiator']} mm" if p["kind"] == "aio" else f"ar, {p['height']} mm de altura") + \
            f"  ·  dissipa ≈{p['capacity']} W  ·  {', '.join(p['sockets'][:6])}{'…' if len(p['sockets']) > 6 else ''}"
    if cat == "storage":
        return f"{p['kind'].upper()}  ·  {p['gb']} GB  ·  leitura {p['read']} MB/s"
    return ""


STEP_NAME = {"cpu": "CPU", "mobo": "PLACA-MÃE", "ram": "MEMÓRIA", "cooler": "COOLER", "gpu": "VÍDEO", "case": "GABINETE", "psu": "FONTE", "storage": "DISCO"}


class BuildPage(Page):
    """Escolha passo a passo: cada passo mostra o que e compativel com o que ja foi escolhido."""

    def __init__(self, win):
        super().__init__(win, "MONTAGEM", "Escolha peça por peça: cada passo mostra o que encaixa no que você já escolheu", "TECHIE://BUILD")
        self.step = "cpu"
        steps = QHBoxLayout()
        steps.setSpacing(4)
        self.step_btn: dict[str, QPushButton] = {}
        self.step_grp = QButtonGroup(self)
        for i, cat in enumerate(core.STEPS):
            b = QPushButton()
            b.setObjectName("step")
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            b.setMinimumHeight(46)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=cat: self.go_step(c))
            self.step_grp.addButton(b, i)
            self.step_btn[cat] = b
            steps.addWidget(b, 1)
        self.lay.addLayout(steps)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar:  xeon,  am3,  lga1155,  rtx 3060,  ddr3,  16gb,  2011 ...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.timer.start(180))
        row.addWidget(self.search, 1)
        self.show_bad = QCheckBox("Mostrar incompatíveis")
        self.show_bad.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.show_bad.toggled.connect(lambda _v: self.fill())
        row.addWidget(self.show_bad)
        self.no_gpu = button("SEM PLACA DE VIDEO", None, lambda: self.choose("gpu", ""))
        row.addWidget(self.no_gpu)
        self.lay.addLayout(row)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fill)
        self.count = label("", "dim", 1, 11)
        self.lay.addWidget(self.count)
        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(6)
        holder = QWidget()
        holder.setObjectName("page")
        holder.setLayout(self.list_box)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setWidget(holder)
        sc.setMinimumHeight(430)
        self.list_scroll = sc
        self.lay.addWidget(sc)
        pr = QHBoxLayout()
        pr.addWidget(label("MODELO PRONTO", "muted", 2, 11, True))
        self.preset = QComboBox()
        for p in core.db().presets:
            self.preset.addItem(p["name"], p["id"])
        pr.addWidget(self.preset)
        pr.addWidget(button("CARREGAR", None, self.load_preset))
        pr.addStretch()
        pr.addWidget(button("COMECAR DO ZERO", "ghost", self.reset))
        self.lay.addLayout(pr)
        self.summary = QHBoxLayout()
        self.lay.addLayout(self.summary)
        self.issues = QVBoxLayout()
        self.issues.setSpacing(8)
        self.lay.addLayout(self.issues)
        self.lay.addStretch()

    # ---- acoes
    def load_preset(self):
        self.win.set_build(core.from_preset(self.preset.currentData()))
        self.win.toast(f"Montagem: {self.preset.currentText()}")

    def reset(self):
        b = core.new_build({})
        b["res"], b["quality"], b["ambient"] = self.win.build["res"], self.win.build["quality"], self.win.build["ambient"]
        self.win.set_build(b)
        self.go_step("cpu")

    def go_step(self, cat):
        self.step = cat
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.refresh()

    def choose(self, cat, pid):
        b = self.win.build
        cleared = core.pick(b, cat, pid)
        self.win.save()
        if cleared:
            self.win.toast("Desmarcado por incompatibilidade: " + ", ".join(CAT_NAME[c].lower() for c in cleared) + ". Escolha de novo.")
        nxt = core.next_step(b, cat)
        self.step = cleared[0] if cleared else (nxt or cat)
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.refresh()

    # ---- desenho
    def steps_text(self):
        b = self.win.build
        for i, cat in enumerate(core.STEPS):
            pid = b["parts"].get(cat)
            name = core.db().name(cat, pid) if pid else ("vídeo integrado" if cat == "gpu" and b["parts"].get("cpu") and core.part(b, "cpu")["igpu"] and self.step != "gpu" and core.next_step(b) != "gpu" else "—")
            btn = self.step_btn[cat]
            short = btn.fontMetrics().elidedText(name, Qt.ElideRight, max(40, btn.width() - 20))
            btn.setText(f"{i + 1:02d} {STEP_NAME[cat]}\n{short}")
            btn.setToolTip(name)
            btn.setProperty("done", bool(pid))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.setChecked(cat == self.step)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.steps_text()

    def refresh(self):
        self.steps_text()
        self.no_gpu.setVisible(self.step == "gpu")
        self.fill()
        self.render()

    def fill(self):
        clear(self.list_box)
        b, cat = self.win.build, self.step
        opts = core.options(b, cat, self.search.text())
        n_ok = sum(1 for o in opts if o["ok"])
        shown = opts if self.show_bad.isChecked() else [o for o in opts if o["ok"] or o["part"]["id"] == b["parts"].get(cat)]
        idx = self.win.price_index
        self.count.setText(f"{CAT_NAME[cat].upper()}  ·  {n_ok} compatível(is)" + (f"  ·  {len(opts) - n_ok} escondida(s) por incompatibilidade (marque Mostrar incompatíveis para trocar de plataforma)" if len(opts) > n_ok and not self.show_bad.isChecked() else "")
                           + ("  ·  clique para escolher" if shown else ""))
        spaced(self.count, 1.5, 11, True)
        for o in shown[:150]:
            self.list_box.addWidget(OptionRow(self, cat, o, o["part"]["id"] == b["parts"].get(cat), idx.get(o["part"]["id"])))
        if not shown:
            self.list_box.addWidget(label("Nada encontrado. Tente outra busca ou marque \"Mostrar incompatíveis\".", "muted", 1, wrap=True))
        self.list_box.addStretch()
        self.list_scroll.verticalScrollBar().setValue(0)

    def render(self):
        b = self.win.build
        clear(self.summary)
        clear(self.issues)
        pw = core.power(b)
        iss = core.check(b)
        n_err = len(core.errors(iss))
        self.summary.addWidget(stat("COMPATIBILIDADE", "OK" if not n_err else f"{n_err} ERRO(S)", "ok" if not n_err else "red"))
        self.summary.addWidget(stat("CONSUMO JOGANDO", f"≈{pw['game']} W", sub=f"pico ≈{pw['peak']} W · fonte recomendada {pw['recommended']} W"))
        rows = core.estimate_all(b) if core.part(b, "cpu") else []
        avg = round(sum(e["fps"] for _, e in rows) / len(rows)) if rows else 0
        self.summary.addWidget(stat(f"MEDIA {b['res']} {core.QUALITY_NAME[b['quality']].upper()}", f"{avg} FPS" if avg else "—", sub=f"estimativa, {len(core.db().games)} jogos"))
        total, missing = prices.build_total(b["parts"], self.win.price_index)
        self.summary.addWidget(stat("PRECO DA MONTAGEM", prices.brl(total) if total else "—",
                                    sub=("menor preço de cada peça" + (f" · sem preço: {len(missing)}" if missing else "")) if total else "preços: aba PRECOS"))
        for i in sorted(iss, key=lambda x: ["erro", "aviso", "info"].index(x["level"])):
            if i["code"] != "missing":
                self.issues.addWidget(issue_card(i))
        miss = [i for i in iss if i["code"] == "missing"]
        if miss:
            self.issues.addWidget(issue_card({"level": "info", "text": "Falta escolher: " + ", ".join(CAT_NAME[i["parts"][0]].lower() for i in miss) + "."}))
        if not iss:
            self.issues.addWidget(issue_card({"level": "info", "text": "Tudo compatível. Veja o desempenho, o airflow, os preços e o relatório nas outras abas."}))


class HistoryChart(QWidget):
    """Grafico do menor preco por dia, com a mediana tracejada."""

    def __init__(self):
        super().__init__()
        self.hist, self.med = [], None
        self.setMinimumHeight(220)

    def set_data(self, hist: list[dict], median: float | None):
        self.hist, self.med = hist[-180:], median
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(5, 5, 6))
        p.setPen(QPen(LINE, 1))
        p.drawRect(0, 0, w - 1, h - 1)
        f = QFont(p.font())
        f.setPixelSize(11)
        p.setFont(f)
        if len(self.hist) < 2:
            p.setPen(MUTED)
            p.drawText(self.rect(), Qt.AlignCenter, "Sem histórico suficiente ainda: o coletor guarda um ponto por dia.")
            return
        vals = [x["min"] for x in self.hist]
        lo, hi = min(vals), max(vals)
        if hi - lo < 1:
            lo, hi = lo - 1, hi + 1
        pad_l, pad_r, pad_t, pad_b = 74, 14, 14, 26
        cw, ch = w - pad_l - pad_r, h - pad_t - pad_b

        def pt(i, v):
            return QPointF(pad_l + cw * i / (len(vals) - 1), pad_t + ch * (1 - (v - lo) / (hi - lo)))
        p.setPen(QColor(85, 85, 94))
        for k in range(3):
            v = lo + (hi - lo) * k / 2
            y = pt(0, v).y()
            p.drawText(QRectF(0, y - 8, pad_l - 8, 16), Qt.AlignRight | Qt.AlignVCenter, prices.brl(v))
            p.setPen(QPen(QColor(25, 25, 30), 1))
            p.drawLine(QPointF(pad_l, y), QPointF(w - pad_r, y))
            p.setPen(QColor(85, 85, 94))
        p.drawText(QRectF(pad_l, h - 20, 120, 16), Qt.AlignLeft, self.hist[0]["d"])
        p.drawText(QRectF(w - pad_r - 120, h - 20, 120, 16), Qt.AlignRight, self.hist[-1]["d"])
        if self.med:
            pen = QPen(QColor(140, 140, 150), 1)
            pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            y = pt(0, self.med).y()
            p.drawLine(QPointF(pad_l, y), QPointF(w - pad_r, y))
            p.drawText(QRectF(pad_l + 4, y - 16, 160, 14), Qt.AlignLeft, "mediana")
        poly = QPolygonF([pt(i, v) for i, v in enumerate(vals)])
        p.setPen(QPen(RED, 2))
        p.drawPolyline(poly)
        last = pt(len(vals) - 1, vals[-1])
        p.setBrush(RED)
        p.drawEllipse(last, 4, 4)


class PricesPage(Page):
    def __init__(self, win):
        super().__init__(win, "PRECOS", "Menor preço de cada peça, histórico e se está caro ou barato agora", "TECHIE://MARKET")
        disc = label(prices.DISCLOSURE, "warn", 0.5, 12, False, wrap=True)
        disc.setStyleSheet("border:1px solid #5a4210; background:#120d04; padding:8px 12px;")
        self.lay.addWidget(disc)
        top = QHBoxLayout()
        self.status = label("", "muted", 0.5, 12, wrap=True)
        top.addWidget(self.status, 1)
        top.addWidget(button("ATUALIZAR PRECOS", None, lambda: self.win.load_prices(True)))
        self.lay.addLayout(top)
        self.total = QHBoxLayout()
        self.lay.addLayout(self.total)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(6)
        self.lay.addLayout(self.rows)
        self.detail = QVBoxLayout()
        self.detail.setSpacing(8)
        self.lay.addLayout(self.detail)
        self.lay.addStretch()
        self.sel = None
        self.task = None

    def refresh(self):
        b, idx = self.win.build, self.win.price_index
        clear(self.rows)
        clear(self.total)
        st = self.win.price_state
        self.status.setText({"carregando": "■  Buscando preços no servidor...",
                             "offline": "Sem conexão com o servidor de preços" + (" · mostrando o último cache." if idx else ": ainda não há preços salvos."),
                             "ok": f"Preços do coletor piphin.online · atualizado {self.win.price_updated or '—'} · uma coleta por dia nas lojas parceiras."}.get(st, ""))
        total, missing = prices.build_total(b["parts"], idx)
        self.total.addWidget(stat("TOTAL DA MONTAGEM", prices.brl(total) if total else "—", sub="somando o menor preço de cada peça"))
        self.total.addWidget(stat("PECAS SEM PRECO", str(len(missing)), sub=", ".join(CAT_NAME[c].lower() for c in missing) if missing else "nenhuma"))
        for cat in core.STEPS:
            pid = b["parts"].get(cat)
            if not pid:
                continue
            self.rows.addWidget(self.part_row(cat, pid, idx.get(pid)))
        if not any(b["parts"].values()):
            self.rows.addWidget(label("Escolha as peças na aba Montagem.", "muted"))
        if self.sel and b["parts"].get(self.sel[0]) == self.sel[1]:
            self.show_part(*self.sel)
        else:
            clear(self.detail)

    def part_row(self, cat, pid, pr):
        c = CutFrame(cut=10)
        lay = QHBoxLayout(c)
        lay.setContentsMargins(12, 8, 14, 8)
        lay.setSpacing(14)
        th = Thumb(cat, 52)
        if pr and pr.get("image"):
            self.win.images.request(pr["image"], th)
        lay.addWidget(th)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(label(CAT_NAME[cat].upper(), "muted", 2, 10, True))
        col.addWidget(label(core.db().name(cat, pid), None, 0.5, 13, True, wrap=True))
        lay.addLayout(col, 1)
        if pr and isinstance(pr.get("price"), (int, float)):
            r = QVBoxLayout()
            r.setSpacing(2)
            r.addWidget(label(prices.brl(pr["price"]), None, 1, 15, True), 0, Qt.AlignRight)
            r.addWidget(label(pr.get("store", ""), "dim", 0.5, 11), 0, Qt.AlignRight)
            lay.addLayout(r)
            if pr.get("verdict"):
                lay.addWidget(verdict_chip(pr["verdict"]))
        else:
            lay.addWidget(label("sem preço", "dim"))
        lay.addWidget(button("HISTORICO E LOJAS", None, lambda: self.show_part(cat, pid)))
        return c

    def show_part(self, cat, pid):
        self.sel = (cat, pid)
        clear(self.detail)
        self.detail.addWidget(label(f"{CAT_NAME[cat].upper()} · {core.db().name(cat, pid)}", "section", 2, 12, True, wrap=True))
        self.detail.addWidget(label("■  Carregando histórico...", "muted"))
        self.task = Task(prices.part, pid).start()
        self.task.done.connect(lambda r, c=cat, p=pid: self._part_loaded(c, p, r))

    def _part_loaded(self, cat, pid, r):
        if self.sel != (cat, pid):
            return
        clear(self.detail)
        self.detail.addWidget(label(f"{CAT_NAME[cat].upper()} · {core.db().name(cat, pid)}", "section", 2, 12, True, wrap=True))
        data, stale = (None, True) if isinstance(r, Exception) else r
        if not data:
            self.detail.addWidget(issue_card({"level": "info", "text": "Sem dados de preço para esta peça (servidor fora do ar ou peça ainda não coletada)."}))
            return
        offers = data.get("offers", [])
        cur = next((o["price"] for o in offers if isinstance(o.get("price"), (int, float))), None)
        v = prices.verdict(data.get("history", []), cur)
        row = QHBoxLayout()
        row.addWidget(stat("MENOR PRECO HOJE", prices.brl(cur), "ok" if v["level"] == "baixo" else ("red" if v["level"] == "alto" else None)))
        row.addWidget(stat("MENOR EM 90 DIAS", prices.brl(v["min"])))
        row.addWidget(stat("MEDIANA", prices.brl(v["median"])))
        row.addWidget(stat("MAIOR EM 90 DIAS", prices.brl(v["max"])))
        self.detail.addLayout(row)
        vl = QHBoxLayout()
        vl.addWidget(verdict_chip(v["level"]))
        vl.addWidget(label(v["text"], None, 0.5, 13, wrap=True), 1)
        self.detail.addLayout(vl)
        ch = HistoryChart()
        ch.set_data(data.get("history", []), v["median"])
        self.detail.addWidget(ch)
        if stale:
            self.detail.addWidget(label("Dados do cache (sem conexão com o servidor agora).", "dim"))
        self.detail.addWidget(label("ONDE COMPRAR", "muted", 2, 11, True))
        for k, o in enumerate(offers[:12]):
            c = CutFrame(cut=8)
            lay = QHBoxLayout(c)
            lay.setContentsMargins(12, 6, 12, 6)
            lay.addWidget(label(o.get("store", "loja"), None, 1, 12, True))
            t = o.get("title", "")
            lay.addWidget(label(t if len(t) < 90 else t[:89] + "…", "muted", 0.5, 11), 1)
            lay.addWidget(label(prices.brl(o.get("price")) if o.get("price") is not None else "ver preço na loja", None, 1, 13, True))
            lay.addWidget(button("COMPRAR ↗" if o.get("price") is not None else "VER NA LOJA ↗", "primary" if k == 0 and o.get("price") is not None else None,
                                 lambda u=o["url"]: self.open(u)))
            self.detail.addWidget(c)
        if not offers:
            self.detail.addWidget(label("Nenhuma loja com oferta para esta peça agora.", "muted"))

    def open(self, url):
        if prices.safe_url(url):
            QDesktopServices.openUrl(QUrl(url))


class PerfPage(Page):
    def __init__(self, win):
        super().__init__(win, "DESEMPENHO", "FPS esperado em jogos populares e quem limita: processador ou placa de vídeo", "TECHIE://FPS")
        self.lay.addWidget(banner())
        row = QHBoxLayout()
        row.addWidget(label("RESOLUCAO", "muted", 2, 11, True))
        self.res = QComboBox()
        self.res.addItems(list(core.RES))
        row.addWidget(self.res)
        row.addSpacing(16)
        row.addWidget(label("QUALIDADE", "muted", 2, 11, True))
        self.q = QComboBox()
        for k in core.QUALITY:
            self.q.addItem(core.QUALITY_NAME[k], k)
        row.addWidget(self.q)
        row.addStretch()
        self.lay.addLayout(row)
        self.res.currentTextChanged.connect(self.opts)
        self.q.currentIndexChanged.connect(self.opts)
        self.head = QLabel()
        self.head.setWordWrap(True)
        self.lay.addWidget(self.head)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(6)
        self.lay.addLayout(self.grid)
        self.lay.addWidget(label("Como é calculado: FPS da GPU = referência do jogo × pontuação da GPU × resolução × qualidade (com perda se faltar VRAM). "
                                 "FPS da CPU = referência × pontuação do processador × memória. O menor dos dois manda; o jogo pode ter limite próprio. "
                                 "1% low ≈ os piores momentos. Barras: marcas em 60 e 144 FPS.", "dim", 0.5, 11, wrap=True))
        self.lay.addStretch()

    def opts(self):
        if getattr(self, "_filling", False):
            return
        self.win.build["res"] = self.res.currentText()
        self.win.build["quality"] = self.q.currentData()
        self.win.save()
        self.render()

    def refresh(self):
        self._filling = True
        self.res.setCurrentText(self.win.build["res"])
        self.q.setCurrentIndex(core.QUALITY.index(self.win.build["quality"]))
        self._filling = False
        self.render()

    def render(self):
        clear(self.grid)
        b = self.win.build
        if not core.part(b, "cpu"):
            self.head.setText("Escolha pelo menos o processador na aba Montagem.")
            return
        rows = core.estimate_all(b)
        gpu = core.part(b, "gpu")
        self.head.setText(f"{core.db().name('cpu', b['parts']['cpu'])}  +  {gpu['name'] if gpu else 'vídeo integrado'}\n{core.bottleneck_summary(rows)}")
        spaced(self.head, 1, 13, True)
        scale = max(240, max(e["fps"] for _, e in rows) * 1.05)
        for c, h in enumerate(["JOGO", "", "FPS", "1% LOW", "LIMITA", "GARGALO"]):
            self.grid.addWidget(label(h, "muted", 2, 11, True), 0, c)
        for r, (g, e) in enumerate(rows, 1):
            self.grid.addWidget(label(g["name"], None, 0.5), r, 0)
            self.grid.addWidget(Bar(e["fps"], scale), r, 1)
            self.grid.addWidget(label(f"{e['fps']}", None, 1, 14, True), r, 2)
            self.grid.addWidget(label(f"{e['low']}", "muted"), r, 3)
            self.grid.addWidget(label(e["limit"] + ("  · VRAM!" if e["vram_short"] else ""), "red" if e["vram_short"] else "muted", 1), r, 4)
            self.grid.addWidget(label(f"{e['bottleneck']}%" if e["limit"] in ("CPU", "GPU") else "—", "dim"), r, 5)
        self.grid.setColumnStretch(1, 1)


class AirPage(Page):
    def __init__(self, win):
        super().__init__(win, "AIRFLOW", "Fans em cada posição do gabinete, pressão, fluxo e temperaturas", "TECHIE://FLOW")
        self.lay.addWidget(banner())
        top = QHBoxLayout()
        left = QVBoxLayout()
        self.ctl = QGridLayout()
        self.ctl.setHorizontalSpacing(10)
        self.ctl.setVerticalSpacing(8)
        left.addLayout(self.ctl)
        amb = QHBoxLayout()
        amb.addWidget(label("TEMPERATURA AMBIENTE", "muted", 2, 11, True))
        self.amb = QSpinBox()
        self.amb.setRange(10, 45)
        self.amb.setSuffix(" °C")
        self.amb.valueChanged.connect(self.set_amb)
        amb.addWidget(self.amb)
        amb.addStretch()
        left.addLayout(amb)
        self.rad_row = QHBoxLayout()
        left.addLayout(self.rad_row)
        left.addWidget(button("VOLTAR AOS FANS DE FABRICA", None, self.factory))
        left.addStretch()
        top.addLayout(left, 1)
        self.diagram = CaseDiagram(win)
        top.addWidget(self.diagram, 1)
        self.lay.addLayout(top)
        self.stats = QGridLayout()
        self.stats.setSpacing(10)
        self.lay.addLayout(self.stats)
        self.notes = QVBoxLayout()
        self.lay.addLayout(self.notes)
        self.lay.addWidget(label("Como é calculado: vazão típica por tamanho (80 mm ≈ 30 CFM, 92 ≈ 40, 120 ≈ 55, 140 ≈ 68, 200 ≈ 110), menos a restrição do painel "
                                 "(tela, vidro, frente fechada) e do radiador. Entrada maior que a saída = pressão positiva (menos poeira). O ar interno esquenta "
                                 "com o calor da CPU e da GPU dividido pela vazão; um caminho ruim (contra a convecção) piora a mistura.", "dim", 0.5, 11, wrap=True))
        self.lay.addStretch()

    def set_amb(self, v):
        if not getattr(self, "_filling", False):
            self.win.build["ambient"] = v
            self.win.save()
            self.render_stats()

    def factory(self):
        core.reset_fans(self.win.build)
        self.win.save()
        self.refresh()

    def refresh(self):
        self._filling = True
        self.amb.setValue(int(self.win.build.get("ambient", 25)))
        self._filling = False
        self.build_controls()
        self.render_stats()

    def build_controls(self):
        clear(self.ctl)
        clear(self.rad_row)
        b = self.win.build
        case = core.part(b, "case")
        if not case:
            self.ctl.addWidget(label("Escolha um gabinete na aba Montagem.", "muted"), 0, 0)
            return
        for c, h in enumerate(["POSICAO", "QTD", "TAMANHO", "DIRECAO"]):
            self.ctl.addWidget(label(h, "muted", 2, 11, True), 0, c)
        for r, pos in enumerate(p for p in core.POSITIONS if p in case["slots"]):
            slot = case["slots"][pos]
            sizes = sorted(int(k) for k in slot["sizes"])
            fan = b["fans"].get(pos, {"count": 0, "size": sizes[-1] if 120 not in sizes else 120, "dir": "in"})
            self.ctl.addWidget(label(POS_NAME[pos].upper(), None, 2, 12, True), r + 1, 0)
            n = QSpinBox()
            n.setRange(0, slot["sizes"][str(fan["size"])] if str(fan["size"]) in slot["sizes"] else max(slot["sizes"].values()))
            n.setValue(fan["count"])
            sz = QComboBox()
            for s in sizes:
                sz.addItem(f"{s} mm (até {slot['sizes'][str(s)]})", s)
            sz.setCurrentIndex(sizes.index(fan["size"]) if fan["size"] in sizes else len(sizes) - 1)
            dr = QComboBox()
            dr.addItem("Entrada", "in")
            dr.addItem("Saída", "out")
            dr.setCurrentIndex(0 if fan["dir"] == "in" else 1)
            for w in (n, sz, dr):
                self.ctl.addWidget(w, r + 1, [n, sz, dr].index(w) + 1)
            n.valueChanged.connect(lambda _v, p=pos, a=n, s=sz, d=dr: self.set_fan(p, a, s, d))
            sz.currentIndexChanged.connect(lambda _v, p=pos, a=n, s=sz, d=dr: self.set_fan(p, a, s, d, True))
            dr.currentIndexChanged.connect(lambda _v, p=pos, a=n, s=sz, d=dr: self.set_fan(p, a, s, d))
        cool = core.part(b, "cooler")
        if cool and cool["kind"] == "aio":
            fits = [p for p in core.RAD_PREF if core.fits_radiator(case, p, cool["radiator"])]
            self.rad_row.addWidget(label(f"RADIADOR {cool['radiator']} MM", "muted", 2, 11, True))
            if fits:
                cb = QComboBox()
                for p in fits:
                    cb.addItem(POS_NAME[p], p)
                cb.setCurrentIndex(max(0, cb.findData(core.radiator_pos(b))))
                cb.currentIndexChanged.connect(lambda _i, c=cb: self.set_rad(c.currentData()))
                self.rad_row.addWidget(cb)
            else:
                self.rad_row.addWidget(label("não cabe neste gabinete", "red"))
            self.rad_row.addStretch()

    def set_rad(self, pos):
        self.win.build["radiator"] = pos
        self.win.save()
        self.render_stats()

    def set_fan(self, pos, n, sz, dr, size_changed=False):
        case = core.part(self.win.build, "case")
        size = sz.currentData()
        mx = case["slots"][pos]["sizes"][str(size)]
        if size_changed:
            n.blockSignals(True)
            n.setMaximum(mx)
            n.blockSignals(False)
        cnt = min(n.value(), mx)
        if cnt:
            self.win.build["fans"][pos] = {"count": cnt, "size": size, "dir": dr.currentData()}
        else:
            self.win.build["fans"].pop(pos, None)
        self.win.save()
        self.render_stats()

    def render_stats(self):
        clear(self.stats)
        clear(self.notes)
        b = self.win.build
        a, full = core.airflow(b), core.airflow(b, full_load=True)
        cells = [
            stat("ENTRADA", f"{a['intake']} CFM"), stat("SAIDA", f"{a['exhaust']} CFM"),
            stat("PRESSAO", a["pressure"].upper(), "ok" if a["pressure"] in ("positiva", "equilibrada") else "warn",
                 {"positiva": "entra mais do que sai: menos poeira", "negativa": "ar entra pelas frestas sem filtro", "equilibrada": "entrada ≈ saída",
                  "sem fans": "só convecção natural"}.get(a["pressure"], "")),
            stat("FLUXO UTIL", f"≈{a['flow']} CFM", sub=a["path"]),
            stat("AR INTERNO", f"{a['case_air']:.0f} °C", sub=f"+{a['case_air'] - b.get('ambient', 25):.0f} °C sobre o ambiente"),
            stat("CPU JOGANDO", f"{a['cpu']:.0f} °C" if a["cpu"] is not None else "—", "red" if a["cpu_throttle"] else None,
                 f"carga total ≈{full['cpu']:.0f} °C" + (" · LIMITE" if full["cpu_throttle"] else "") if full["cpu"] is not None else ""),
            stat("GPU JOGANDO", f"{a['gpu']:.0f} °C" if a["gpu"] is not None else "—", "red" if a["gpu_throttle"] else None),
            stat("CALOR NO GABINETE", f"≈{a['heat']} W", sub="radiador soprando para fora tira o calor da CPU" if a["radiator"] else ""),
        ]
        for i, c in enumerate(cells):
            self.stats.addWidget(c, i // 4, i % 4)
        for i in core.check(b):
            if i["code"] in ("rad_fans", "no_exhaust", "no_intake", "radiator", "gpu_len", "gpu_tight", "cooler_h"):
                self.notes.addWidget(issue_card(i))
        if a["cpu_throttle"] or full["cpu_throttle"]:
            self.notes.addWidget(issue_card({"level": "aviso" if not a["cpu_throttle"] else "erro",
                                             "text": "O processador chega no limite de temperatura e reduz a frequência: cooler maior ou mais fluxo de ar."}))
        self.diagram.update()


class UpgradePage(Page):
    def __init__(self, win):
        super().__init__(win, "UPGRADE", "Escolha a peça nova e veja o ganho e o que mais precisa trocar junto", "TECHIE://CHROME")
        self.lay.addWidget(banner())
        row = QHBoxLayout()
        self.cat = QComboBox()
        for c in CATS:
            self.cat.addItem(CAT_NAME[c], c)
        self.cat.setCurrentIndex(CATS.index("gpu"))
        self.cat.currentIndexChanged.connect(self.fill)
        self.pick = QComboBox()
        row.addWidget(label("TROCAR", "muted", 2, 11, True))
        row.addWidget(self.cat)
        row.addWidget(label("POR", "muted", 2, 11, True))
        row.addWidget(self.pick, 1)
        row.addWidget(button("SIMULAR", "primary", self.run))
        self.lay.addLayout(row)
        self.out = QVBoxLayout()
        self.out.setSpacing(10)
        self.lay.addLayout(self.out)
        self.lay.addStretch()
        self.result = None

    def fill(self):
        cat = self.cat.currentData()
        cur = self.win.build["parts"].get(cat)
        self.pick.clear()
        for p in core.db().parts[cat]:
            if p["id"] != cur:
                self.pick.addItem(part_label(cat, p), p["id"])
        if cat in ("cpu", "gpu"):
            old = core.part(self.win.build, cat)
            ref = old["score"] if old else 0
            better = next((i for i in range(self.pick.count()) if core.db().get(cat, self.pick.itemData(i))["score"] > ref), 0)
            nearest = min((i for i in range(self.pick.count()) if core.db().get(cat, self.pick.itemData(i))["score"] > ref),
                          key=lambda i: core.db().get(cat, self.pick.itemData(i))["score"], default=better)
            self.pick.setCurrentIndex(nearest)

    def refresh(self):
        self.fill()
        clear(self.out)
        cur = core.db().name("cpu", self.win.build["parts"].get("cpu")), core.db().name("gpu", self.win.build["parts"].get("gpu"))
        self.out.addWidget(label(f"Montagem atual: {cur[0]} + {cur[1] if cur[1] != '—' else 'vídeo integrado'} · comparação em "
                                 f"{self.win.build['res']} {core.QUALITY_NAME[self.win.build['quality']].lower()} (mude na aba Desempenho).", "muted", 0.5, wrap=True))

    def run(self, cat=None, new=None):
        cat = cat or self.cat.currentData()
        new = new or self.pick.currentData()
        if not new:
            return
        d = core.db()
        r = core.upgrade(self.win.build, cat, new)
        self.result = r
        clear(self.out)
        old = r["changed"]["old"]
        c = CutFrame(cut=12)
        c.set_border(RED)
        lay = QVBoxLayout(c)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.addWidget(label("TROCA ESCOLHIDA", "muted", 2, 11, True))
        lay.addWidget(label(f"{CAT_NAME[cat]}: {d.name(cat, old)}  →  {d.name(cat, new)}", None, 1, 14, True, wrap=True))
        g = r["avg_gain"]
        big = label(f"{g:+.0f}%", "ok" if g > 1 else ("red" if g < -1 else "muted"), 1, 34, True)
        lay.addWidget(big)
        lay.addWidget(label(f"ganho médio de FPS nos {len(r['games'])} jogos ({self.win.build['res']}, {core.QUALITY_NAME[self.win.build['quality']].lower()})", "muted"))
        idx = self.win.price_index
        buy = [new] + [ch["new"] for ch in r["changes"]]
        known = [idx[x]["price"] for x in buy if isinstance((idx.get(x) or {}).get("price"), (int, float))]
        if known:
            miss = len(buy) - len(known)
            lay.addWidget(label(f"Custo estimado: {prices.brl(sum(known))} (peça nova" + (" + trocas obrigatórias" if r["changes"] else "") + ", menor preço"
                                + (f"; {miss} peça(s) sem preço" if miss else "") + "). Vendendo as peças antigas, sai mais barato.", None, 0.5, 13, True, wrap=True))
        self.out.addWidget(c)
        self.out.addWidget(label("TROCAS OBRIGATORIAS", "section", 2, 12, True))
        if r["changes"]:
            for ch in r["changes"]:
                self.out.addWidget(issue_card({"level": "aviso", "text": f"{CAT_NAME[ch['cat']]}: {d.name(ch['cat'], ch['old']) if ch['old'] else 'nenhuma'}  →  "
                                                                         f"{d.name(ch['cat'], ch['new'])}\nPor quê: {ch['reason']}. (Sugestão: outra peça equivalente também serve.)"}))
        else:
            self.out.addWidget(issue_card({"level": "info", "text": "Nenhuma: a peça nova encaixa na montagem atual."}))
        for i in core.errors(r["issues"]):
            self.out.addWidget(issue_card(i))
        pb, pa = r["power_before"], r["power_after"]
        ab, aa = r["air_before"], r["air_after"]
        row = QHBoxLayout()

        def t(v):
            return f"{v:.0f}°C" if v is not None else "—"
        row.addWidget(stat("CONSUMO JOGANDO", f"{pb['game']} → {pa['game']} W", sub=f"fonte recomendada {pb['recommended']} → {pa['recommended']} W"))
        row.addWidget(stat("CPU", f"{t(ab['cpu'])} → {t(aa['cpu'])}"))
        row.addWidget(stat("GPU", f"{t(ab['gpu'])} → {t(aa['gpu'])}"))
        row.addWidget(stat("AR INTERNO", f"{t(ab['case_air'])} → {t(aa['case_air'])}"))
        self.out.addLayout(row)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(5)
        for k, h in enumerate(["JOGO", "", "ANTES", "DEPOIS", "GANHO", "LIMITA DEPOIS"]):
            grid.addWidget(label(h, "muted", 2, 11, True), 0, k)
        scale = max(240, max(x["after"]["fps"] for x in r["games"]) * 1.05)
        for n, x in enumerate(r["games"], 1):
            grid.addWidget(label(x["game"]["name"], None, 0.5), n, 0)
            grid.addWidget(Bar(x["after"]["fps"], scale, x["before"]["fps"]), n, 1)
            grid.addWidget(label(str(x["before"]["fps"]), "muted"), n, 2)
            grid.addWidget(label(str(x["after"]["fps"]), None, 1, 14, True), n, 3)
            grid.addWidget(label(f"{x['gain']:+.0f}%", "ok" if x["gain"] > 1 else ("red" if x["gain"] < -1 else "dim"), 1, 13, True), n, 4)
            grid.addWidget(label(x["after"]["limit"], "dim"), n, 5)
        grid.setColumnStretch(1, 1)
        self.out.addLayout(grid)
        act = QHBoxLayout()
        act.addStretch()
        act.addWidget(button("APLICAR NA MONTAGEM", "primary", self.apply))
        self.out.addLayout(act)

    def apply(self):
        if self.result:
            self.win.set_build(self.result["build"])
            self.win.toast("Upgrade aplicado na montagem")
            self.refresh()


class ReportPage(Page):
    def __init__(self, win):
        super().__init__(win, "RELATORIO", "Resumo final: desempenho, temperaturas, consumo e avisos", "TECHIE://DOSSIER")
        self.lay.addWidget(banner())
        self.text = QPlainTextEdit()
        self.text.setObjectName("report")
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(560)
        self.lay.addWidget(self.text, 1)
        row = QHBoxLayout()
        row.addWidget(button("COPIAR", None, self.copy))
        row.addWidget(button("SALVAR .TXT", "primary", self.export))
        row.addStretch()
        self.lay.addLayout(row)

    def refresh(self):
        b = self.win.build
        self.text.setPlainText(core.report(b) + prices.report_section(b["parts"], self.win.price_index, CAT_NAME, core.db().name))

    def copy(self):
        QGuiApplication.clipboard().setText(self.text.toPlainText())
        self.win.toast("Relatório copiado")

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Salvar relatório", str(core.HOME / "montagem-arasaka-techie.txt"), "Texto (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text.toPlainText())
            self.win.toast("Relatório salvo")


# ================================================================ janela
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1240, 860)
        self.build = core.load_build()
        self.images = Images()
        self.price_index, self.price_state, self.price_updated, self._price_task = {}, "carregando", "", None
        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 14)
        sl.setSpacing(2)
        sl.addWidget(SidebarBrand("TECHIE"))
        sl.addSpacing(10)
        self.nav = QButtonGroup(self)
        self.stack = QStackedWidget()
        self.pages = {"build": BuildPage(self), "perf": PerfPage(self), "air": AirPage(self), "upgrade": UpgradePage(self),
                      "prices": PricesPage(self), "report": ReportPage(self)}
        for i, (key, text) in enumerate([("build", "MONTAGEM"), ("perf", "DESEMPENHO"), ("air", "AIRFLOW"), ("upgrade", "UPGRADE"),
                                         ("prices", "PRECOS"), ("report", "RELATORIO")]):
            b = QPushButton(f"{i + 1:02d}   {text}")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            spaced(b, 2.5)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav.addButton(b, i)
            sl.addWidget(b)
            self.stack.addWidget(self.pages[key])
        sl.addStretch()
        db_lbl = label(f"{sum(len(v) for v in core.db().parts.values())} PECAS · {len(core.db().games)} JOGOS", "dim", 1.5, 11, True)
        db_lbl.setContentsMargins(20, 0, 0, 0)
        sl.addWidget(db_lbl)
        ver = label(f"TECHIE v{VERSION}", "dim", 2, 11)
        ver.setContentsMargins(20, 0, 0, 0)
        sl.addWidget(ver)
        h.addWidget(side)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.toast_lbl = QLabel(self)
        self.toast_lbl.setStyleSheet("background:#000; border:1px solid #e3121f; padding:10px 18px; color:#ececf0;")
        self.toast_lbl.hide()
        self.go("build")
        self.load_prices()

    def load_prices(self, force=False):
        if self._price_task:
            return
        self.price_state = "carregando"
        if self.stack.currentWidget() is self.pages["prices"]:
            self.pages["prices"].refresh()

        def job():
            idx, stale = prices.index(force)
            return idx, stale
        self._price_task = Task(job).start()
        self._price_task.done.connect(self._prices_loaded)

    def _prices_loaded(self, r):
        self._price_task = None
        idx, stale = ({}, True) if isinstance(r, Exception) else r
        self.price_index = idx
        self.price_state = "offline" if stale else "ok"
        try:
            f = prices.CACHE / "precos-index.json"
            import json as _j
            self.price_updated = _j.loads(f.read_text(encoding="utf-8")).get("updated", "") if f.exists() else ""
        except (OSError, ValueError):
            self.price_updated = ""
        page = self.stack.currentWidget()
        if page in (self.pages["build"], self.pages["prices"]):
            page.refresh()

    def go(self, key: str):
        self.nav.button(list(self.pages).index(key)).setChecked(True)
        self.stack.setCurrentWidget(self.pages[key])
        self.pages[key].refresh()

    def set_build(self, b: dict):
        self.build = copy.deepcopy(b)
        self.save()
        self.stack.currentWidget().refresh()

    def save(self):
        try:
            core.save_build(self.build)
        except OSError:
            pass

    def toast(self, text: str):
        self.toast_lbl.setText(text)
        spaced(self.toast_lbl, 1)
        self.toast_lbl.adjustSize()
        self.toast_lbl.move(self.width() - self.toast_lbl.width() - 24, 20)
        self.toast_lbl.raise_()
        self.toast_lbl.show()
        QTimer.singleShot(3500, self.toast_lbl.hide)


def main(argv: list[str] | None = None):
    argv = list(sys.argv if argv is None else argv)
    QApplication.setApplicationName(core.APP_ID)
    QApplication.setApplicationDisplayName(APP_NAME)
    QApplication.setDesktopFileName(core.APP_ID)
    app = QApplication(argv)
    load_fonts()
    app.setStyleSheet(stylesheet() + EXTRA_QSS)
    app.setWindowIcon(QIcon(str(core.ASSETS / "arasaka-techie.svg")))
    win = MainWindow()
    fx.install(win, name=APP_NAME, icon=core.ASSETS / "arasaka-techie.svg", boot=not any(a.startswith("--screenshot=") for a in argv))
    win.show()
    shot = next((a.split("=", 1)[1] for a in argv if a.startswith("--screenshot=")), None)
    if shot:
        path, _, page = shot.partition(",")
        if page:
            QTimer.singleShot(200, lambda: win.go(page))
            if page == "upgrade":
                QTimer.singleShot(400, lambda: win.pages["upgrade"].run())
            if page == "prices" and win.build["parts"].get("gpu"):
                QTimer.singleShot(900, lambda: win.pages["prices"].show_part("gpu", win.build["parts"]["gpu"]))
        QTimer.singleShot(int(next((a.split("=", 1)[1] for a in argv if a.startswith("--delay=")), "2600")), lambda: (win.grab().save(path), app.quit()))
    return app.exec()
