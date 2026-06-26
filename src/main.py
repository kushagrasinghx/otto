"""Application entry point: tray icon + global hotkey + Spotlight window."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .config import config_path, load_config
from .ui.spotlight import SpotlightWindow

# Note: we deliberately do NOT call SetProcessDpiAwareness ourselves. Qt sets
# PER_MONITOR_AWARE_V2 during QApplication construction (which is DPI-aware, so
# pyautogui / uiautomation / mss all share physical-pixel coordinates). Setting
# it first only makes Qt log an "Access is denied" warning when it tries to
# upgrade the context.


def make_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(80, 140, 255))
    p.setPen(Qt.NoPen)
    p.drawEllipse(6, 6, 52, 52)
    p.setBrush(QColor(255, 255, 255))
    # little cursor triangle
    from PySide6.QtGui import QPolygon
    from PySide6.QtCore import QPoint
    p.drawPolygon(QPolygon([QPoint(26, 22), QPoint(26, 44), QPoint(33, 37),
                            QPoint(38, 46), QPoint(42, 44), QPoint(37, 35),
                            QPoint(45, 34)]))
    p.end()
    return QIcon(pix)


class HotkeyBridge(QObject):
    """Marshals the global-hotkey callback (foreign thread) onto the UI thread."""
    triggered = Signal()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Make Ctrl+C in the console actually quit. Qt's C++ event loop normally
    # blocks Python from seeing SIGINT, so we (1) route SIGINT to app.quit and
    # (2) run a no-op timer so the interpreter regularly regains control and can
    # deliver the pending signal.
    import signal
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    sigint_timer = QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)

    config = load_config()
    window = SpotlightWindow(config)

    # ---- system tray ----
    icon = make_icon()
    tray = QSystemTrayIcon(icon)
    tray.setToolTip("Windows Pilot — press the hotkey to summon")
    menu = QMenu()

    act_show = QAction("Show (or press hotkey)")
    act_show.triggered.connect(window.show_centered)
    act_reload = QAction("Reload config")
    act_reload.triggered.connect(lambda: window.reload_config(load_config()))
    act_config = QAction("Open config file…")
    act_config.triggered.connect(lambda: os.startfile(str(config_path())))
    act_quit = QAction("Quit")
    act_quit.triggered.connect(app.quit)
    for a in (act_show, act_reload, act_config):
        menu.addAction(a)
    menu.addSeparator()
    menu.addAction(act_quit)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: window.toggle()
        if reason == QSystemTrayIcon.Trigger else None)
    tray.show()

    # ---- global hotkey ----
    bridge = HotkeyBridge()
    bridge.triggered.connect(window.toggle, Qt.QueuedConnection)
    hotkey = config.hotkey
    keyboard = None
    try:
        import keyboard
        keyboard.add_hotkey(hotkey, lambda: bridge.triggered.emit())
        # Release the global hook on quit so the process exits cleanly.
        app.aboutToQuit.connect(lambda: keyboard.unhook_all())
        tray.showMessage(
            "Windows Pilot",
            f"Ready. Press {hotkey} to summon the command box.",
            icon, 4000)
    except Exception as e:
        tray.showMessage(
            "Windows Pilot — hotkey failed",
            f"Could not register '{hotkey}': {e}. Use the tray icon instead.",
            icon, 6000)

    # First-run nudge if no API key configured.
    if not config.api_key():
        tray.showMessage(
            "Windows Pilot — add your API key",
            "Open the config file from the tray menu and paste your "
            f"{config.provider} API key.", icon, 8000)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
