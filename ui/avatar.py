# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# 详见根目录 LICENSE 与 ADDITIONAL_TERMS.md。
# 本文件不含任何开发者的个人信息与真实数据。
# ─────────────────────────────────────────────────────────────────────────────
"""大肥鱼形象区：立绘 + 情绪状态动画（活泼/平静/失落/害羞/思考/学习）。

只有一张立绘，所以状态靠「呼吸缩放 + 程序化叠加」表达，不假装有六套原画；
以后把六张图丢进 ui/assets/states/<state>.png 就会自动替换。
"""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

ASSETS = Path(__file__).resolve().parent / "assets"
STATES = {
    "lively": ("活泼", "#4ade80"),
    "calm": ("平静", "#38bdf8"),
    "sad": ("失落", "#94a3b8"),
    "shy": ("害羞", "#f472b6"),
    "think": ("思考", "#a78bfa"),
    "study": ("学习", "#fbbf24"),
    "reluctant": ("不情愿", "#fb923c"),
    "refuse": ("拒绝", "#ef4444"),
}


class AvatarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.state = "calm"
        self.caption = ""
        self.t = 0.0
        self._pix: QPixmap | None = None
        self._state_pix: dict[str, QPixmap] = {}
        self._load()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)

    # ── 资源 ──
    def _load(self) -> None:
        base = ASSETS / "大肥鱼-big.png"
        if not base.exists():
            base = ASSETS / "大肥鱼.png"
        if base.exists():
            self._pix = QPixmap(str(base))
        states_dir = ASSETS / "states"
        if states_dir.exists():
            for key in STATES:
                path = states_dir / f"{key}.png"
                if path.exists():
                    self._state_pix[key] = QPixmap(str(path))

    # ── 状态 ──
    def set_state(self, state: str, caption: str = "") -> None:
        self.state = state if state in STATES else "calm"
        self.caption = caption
        self.update()

    def _tick(self) -> None:
        self.t += 0.04
        if self.isVisible():
            self.update()

    # ── 绘制 ──
    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        width, height = self.width(), self.height()

        # 背景光晕
        glow = QRadialGradient(QPointF(width / 2, height * 0.44), max(width, height) * 0.62)
        label, color = STATES[self.state]
        base_color = QColor(color)
        glow.setColorAt(0.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 52))
        glow.setColorAt(1.0, QColor(13, 17, 23, 0))
        painter.fillRect(self.rect(), glow)

        pix = self._state_pix.get(self.state) or self._pix
        if pix is None or pix.isNull():
            painter.setPen(QPen(QColor("#8fa6c4")))
            painter.drawText(self.rect(), Qt.AlignCenter, "（找不到立绘：ui/assets/大肥鱼.png）")
            return

        # 呼吸/浮动
        breath = 1.0 + 0.012 * math.sin(self.t * 1.5)
        bob = 3.0 * math.sin(self.t * 0.9)
        side = min(width * 0.82, height * 0.86)
        scale = side / max(pix.width(), pix.height())
        draw_w = pix.width() * scale * breath
        draw_h = pix.height() * scale * breath
        x = (width - draw_w) / 2
        y = (height - draw_h) / 2 + bob - 6

        if self.state == "sad":
            painter.setOpacity(0.82)
        painter.drawPixmap(QRectF(x, y, draw_w, draw_h), pix, QRectF(pix.rect()))
        painter.setOpacity(1.0)

        self._overlay(painter, x, y, draw_w, draw_h)
        self._caption(painter, width, height, label, color)

    def _overlay(self, painter: QPainter, x: float, y: float, w: float, h: float) -> None:
        if self.state == "shy":
            for cx in (0.385, 0.615):
                center = QPointF(x + w * cx, y + h * 0.615)
                grad = QRadialGradient(center, w * 0.075)
                grad.setColorAt(0.0, QColor(244, 114, 182, 150))
                grad.setColorAt(1.0, QColor(244, 114, 182, 0))
                painter.setBrush(grad)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(center, w * 0.075, h * 0.045)
            # 汗滴
            painter.setBrush(QColor(147, 197, 253, 200))
            drop = QPainterPath()
            dx, dy = x + w * 0.76, y + h * 0.30
            drop.moveTo(dx, dy)
            drop.cubicTo(dx + 7, dy + 10, dx + 6, dy + 20, dx, dy + 20)
            drop.cubicTo(dx - 6, dy + 20, dx - 7, dy + 10, dx, dy)
            painter.drawPath(drop)

        elif self.state == "sad":
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(96, 165, 250, 190))
            for cx in (0.42, 0.58):
                center = QPointF(x + w * cx, y + h * 0.585)
                painter.drawEllipse(center, w * 0.010, h * 0.020)
            # 头顶小雨云
            cloud = QPainterPath()
            cxx, cyy = x + w * 0.5, y + h * 0.10
            cloud.addEllipse(QPointF(cxx - 16, cyy), 16, 11)
            cloud.addEllipse(QPointF(cxx + 4, cyy - 4), 20, 14)
            cloud.addEllipse(QPointF(cxx + 24, cyy + 2), 14, 10)
            painter.setBrush(QColor(148, 163, 184, 90))
            painter.drawPath(cloud.simplified())

        elif self.state == "lively":
            for i, (cx, cy, r) in enumerate(((0.20, 0.22, 4), (0.80, 0.18, 5), (0.86, 0.44, 3),
                                            (0.15, 0.46, 3), (0.70, 0.10, 3))):
                phase = 0.5 + 0.5 * math.sin(self.t * 2.4 + i * 1.7)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(250, 240, 137, int(70 + 150 * phase)))
                px, py = x + w * cx, y + h * cy
                star = QPainterPath()
                star.moveTo(px, py - r * 2)
                star.lineTo(px + r * 0.6, py - r * 0.6)
                star.lineTo(px + r * 2, py)
                star.lineTo(px + r * 0.6, py + r * 0.6)
                star.lineTo(px, py + r * 2)
                star.lineTo(px - r * 0.6, py + r * 0.6)
                star.lineTo(px - r * 2, py)
                star.lineTo(px - r * 0.6, py - r * 0.6)
                star.closeSubpath()
                painter.drawPath(star)

        elif self.state == "think":
            bx, by = x + w * 0.66, y + h * 0.12
            bubble = QPainterPath()
            bubble.addRoundedRect(QRectF(bx, by, 92, 46), 18, 18)
            painter.setBrush(QColor(30, 41, 59, 220))
            painter.setPen(QPen(QColor("#3b4d66"), 1))
            painter.drawPath(bubble)
            for i in range(3):
                phase = 0.5 + 0.5 * math.sin(self.t * 3.0 - i * 0.8)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(167, 139, 250, int(90 + 140 * phase)))
                painter.drawEllipse(QPointF(bx + 26 + i * 20, by + 23), 4.5, 4.5)

        elif self.state == "study":
            ring = QRectF(x + w * 0.12, y + h * 0.86, w * 0.76, 10)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(251, 191, 36, 70))
            painter.drawRoundedRect(ring, 5, 5)
            phase = 0.5 + 0.5 * math.sin(self.t * 1.8)
            painter.setBrush(QColor(251, 191, 36, int(120 + 90 * phase)))
            painter.drawRoundedRect(QRectF(ring.x(), ring.y(), ring.width() * (0.4 + 0.4 * phase), 10), 5, 5)

        elif self.state == "reluctant":
            # 别扭：一个「哼」的小气泡
            bx, by = x + w * 0.62, y + h * 0.13
            bubble = QPainterPath()
            bubble.addRoundedRect(QRectF(bx, by, 64, 42), 16, 16)
            painter.setBrush(QColor(48, 33, 20, 220))
            painter.setPen(QPen(QColor("#fb923c"), 1))
            painter.drawPath(bubble)
            font = QFont(self.font())
            font.setPointSize(15)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(QColor("#fdba74")))
            painter.drawText(QRectF(bx, by, 64, 42), Qt.AlignCenter, "哼")

        elif self.state == "refuse":
            # 拒绝：右上角一个红叉徽标 + 边缘暗红
            cx, cy = x + w * 0.80, y + h * 0.16
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(239, 68, 68, 210))
            painter.drawEllipse(QPointF(cx, cy), 17, 17)
            painter.setPen(QPen(QColor(255, 255, 255), 3.5, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(cx - 7, cy - 7), QPointF(cx + 7, cy + 7))
            painter.drawLine(QPointF(cx + 7, cy - 7), QPointF(cx - 7, cy + 7))

    def _caption(self, painter: QPainter, width: int, height: int, label: str, color: str) -> None:
        font = QFont(self.font())
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        text = f"● {label}"
        if self.caption:
            text += f" · {self.caption}"
        metrics = painter.fontMetrics()
        box_w = min(width - 24, metrics.horizontalAdvance(text) + 28)
        box = QRectF((width - box_w) / 2, height - 46, box_w, 30)
        pill = QPainterPath()
        pill.addRoundedRect(box, 15, 15)
        painter.setPen(QPen(QColor(35, 48, 66), 1))
        painter.setBrush(QColor(15, 22, 32, 220))
        painter.drawPath(pill)
        painter.setPen(QPen(QColor(color)))
        painter.drawText(box, Qt.AlignCenter, text)
