"""Minimal vector line-icons, hand-drawn with QPainter.

No emoji, no icon-font dependency (which risks missing glyphs/tofu boxes on
machines without that font) — every icon is plain geometry, so it renders
identically everywhere and matches the existing search-icon's stroke style.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF


def _new_pixmap(size: int) -> tuple[QPixmap, QPainter]:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    return pm, p


def _pen(color: QColor, width: float = 1.6) -> QPen:
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _arrowhead(p: QPainter, tip: QPointF, angle_deg: float, color: QColor, length=3.6):
    a = math.radians(angle_deg)
    a1, a2 = a + math.radians(150), a - math.radians(150)
    p1 = QPointF(tip.x() + length * math.cos(a1), tip.y() + length * math.sin(a1))
    p2 = QPointF(tip.x() + length * math.cos(a2), tip.y() + length * math.sin(a2))
    p.setBrush(color)
    p.drawPolygon(QPolygonF([tip, p1, p2]))
    p.setBrush(Qt.NoBrush)


def _draw_eye(p, s, color):
    p.drawEllipse(QRectF(s * 0.14, s * 0.34, s * 0.72, s * 0.34))
    p.setBrush(color)
    p.drawEllipse(QPointF(s / 2, s / 2), s * 0.07, s * 0.07)
    p.setBrush(Qt.NoBrush)


def _draw_cursor(p, s, color):
    pts = [QPointF(s * 0.30, s * 0.16), QPointF(s * 0.30, s * 0.80),
           QPointF(s * 0.47, s * 0.64), QPointF(s * 0.58, s * 0.84),
           QPointF(s * 0.67, s * 0.79), QPointF(s * 0.56, s * 0.59),
           QPointF(s * 0.76, s * 0.56)]
    p.setBrush(color)
    p.drawPolygon(QPolygonF(pts))
    p.setBrush(Qt.NoBrush)


def _draw_drag(p, s, color):
    p.drawLine(QPointF(s * 0.18, s * 0.82), QPointF(s * 0.82, s * 0.18))
    _arrowhead(p, QPointF(s * 0.82, s * 0.18), -135, color)
    _arrowhead(p, QPointF(s * 0.18, s * 0.82), 45, color)


def _draw_keyboard(p, s, color):
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.30, s * 0.76, s * 0.42), s * 0.06, s * 0.06)
    keyw, keyh, gap, y = s * 0.085, s * 0.07, s * 0.045, s * 0.40
    for i in range(5):
        x = s * 0.20 + i * (keyw + gap)
        p.drawRoundedRect(QRectF(x, y, keyw, keyh), 1.0, 1.0)


def _draw_scroll(p, s, color):
    p.drawLine(QPointF(s / 2, s * 0.16), QPointF(s / 2, s * 0.84))
    _arrowhead(p, QPointF(s / 2, s * 0.16), -90, color)
    _arrowhead(p, QPointF(s / 2, s * 0.84), 90, color)


def _draw_launch(p, s, color):
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.32, s * 0.54, s * 0.54), s * 0.06, s * 0.06)
    p.drawLine(QPointF(s * 0.50, s * 0.42), QPointF(s * 0.82, s * 0.16))
    p.drawLine(QPointF(s * 0.62, s * 0.16), QPointF(s * 0.82, s * 0.16))
    p.drawLine(QPointF(s * 0.82, s * 0.16), QPointF(s * 0.82, s * 0.34))
    _arrowhead(p, QPointF(s * 0.82, s * 0.16), -45, color)


def _draw_window(p, s, color):
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.16, s * 0.56, s * 0.46), s * 0.05, s * 0.05)
    p.drawRoundedRect(QRectF(s * 0.32, s * 0.38, s * 0.56, s * 0.46), s * 0.05, s * 0.05)


def _draw_terminal(p, s, color):
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.14, s * 0.76, s * 0.72), s * 0.08, s * 0.08)
    p.drawLine(QPointF(s * 0.28, s * 0.40), QPointF(s * 0.40, s * 0.50))
    p.drawLine(QPointF(s * 0.28, s * 0.60), QPointF(s * 0.40, s * 0.50))
    p.drawLine(QPointF(s * 0.46, s * 0.62), QPointF(s * 0.68, s * 0.62))


def _draw_clipboard(p, s, color):
    p.drawRoundedRect(QRectF(s * 0.18, s * 0.22, s * 0.64, s * 0.66), s * 0.05, s * 0.05)
    p.drawRoundedRect(QRectF(s * 0.38, s * 0.12, s * 0.24, s * 0.13), s * 0.03, s * 0.03)


def _draw_clock(p, s, color):
    p.drawEllipse(QRectF(s * 0.14, s * 0.14, s * 0.72, s * 0.72))
    cx, cy = s / 2, s / 2
    p.drawLine(QPointF(cx, cy), QPointF(cx, cy - s * 0.22))
    p.drawLine(QPointF(cx, cy), QPointF(cx + s * 0.16, cy))


def _draw_check(p, s, color):
    p.setPen(_pen(color, 2.0))
    p.drawLine(QPointF(s * 0.20, s * 0.52), QPointF(s * 0.42, s * 0.74))
    p.drawLine(QPointF(s * 0.42, s * 0.74), QPointF(s * 0.80, s * 0.26))


def _draw_warning(p, s, color):
    pts = [QPointF(s / 2, s * 0.14), QPointF(s * 0.86, s * 0.82), QPointF(s * 0.14, s * 0.82)]
    p.drawPolygon(QPolygonF(pts))
    p.drawLine(QPointF(s / 2, s * 0.42), QPointF(s / 2, s * 0.62))
    p.setBrush(color)
    p.drawEllipse(QPointF(s / 2, s * 0.72), 1.1, 1.1)
    p.setBrush(Qt.NoBrush)


def _draw_info(p, s, color):
    p.drawEllipse(QRectF(s * 0.14, s * 0.14, s * 0.72, s * 0.72))
    p.setBrush(color)
    p.drawEllipse(QPointF(s / 2, s * 0.34), 1.1, 1.1)
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(s / 2, s * 0.46), QPointF(s / 2, s * 0.68))


def _draw_thought(p, s, color):
    p.setBrush(color)
    for cx in (s * 0.30, s * 0.50, s * 0.70):
        p.drawEllipse(QPointF(cx, s / 2), 1.5, 1.5)
    p.setBrush(Qt.NoBrush)


def _draw_gear(p, s, color):
    p.drawEllipse(QRectF(s * 0.30, s * 0.30, s * 0.40, s * 0.40))
    cx, cy, r = s / 2, s / 2, s * 0.40
    for i in range(6):
        a = math.radians(i * 60)
        x1, y1 = cx + r * 0.74 * math.cos(a), cy + r * 0.74 * math.sin(a)
        x2, y2 = cx + r * math.cos(a), cy + r * math.sin(a)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


_DRAW = {
    "eye": _draw_eye, "cursor": _draw_cursor, "drag": _draw_drag,
    "keyboard": _draw_keyboard, "scroll": _draw_scroll, "launch": _draw_launch,
    "window": _draw_window, "terminal": _draw_terminal, "clipboard": _draw_clipboard,
    "clock": _draw_clock, "check": _draw_check, "warning": _draw_warning,
    "info": _draw_info, "thought": _draw_thought, "gear": _draw_gear,
}


def icon(name: str, size: int = 16, color: QColor = QColor(228, 228, 231)) -> QPixmap:
    pm, p = _new_pixmap(size)
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    try:
        _DRAW.get(name, _draw_gear)(p, size, color)
    finally:
        p.end()
    return pm
