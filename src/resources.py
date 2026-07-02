"""Access to bundled image assets, working both from source and a PyInstaller
build (where data files are unpacked under sys._MEIPASS)."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

APP_ICON_FILE = "main_icon.svg"


def asset_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parents[1]
    return str(root / "assets" / name)


def app_pixmap(size: int = 256) -> QPixmap:
    """Render the app logo SVG to a crisp square QPixmap. Null if missing."""
    renderer = QSvgRenderer(asset_path(APP_ICON_FILE))
    if not renderer.isValid():
        return QPixmap()
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    renderer.render(p)
    p.end()
    return pm


def app_icon() -> QIcon:
    """The app logo as a QIcon (for tray + notifications). Null if missing."""
    pm = app_pixmap(256)
    return QIcon(pm) if not pm.isNull() else QIcon()
