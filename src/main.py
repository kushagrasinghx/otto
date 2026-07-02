"""Application entry point: tray icon + global hotkey + Spotlight window."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .config import config_dir, config_path, load_config
from .resources import app_icon, asset_path
from .ui.spotlight import SpotlightWindow
from .webconfig import settings_url, start_settings_server

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


APP_ID = "Otto"


def register_windows_identity():
    """Give Windows an app identity so toast notifications show the Otto name
    AND icon in their header. Setting the AppUserModelID alone yields only the
    name; the header *icon* comes from a registry entry
    (HKCU\\Software\\Classes\\AppUserModelId\\<id>) with an IconUri pointing at
    a real file. Under PyInstaller the bundled asset lives in a temp dir that
    changes every run, so we copy the icon to a stable %APPDATA%\\Otto path and
    point the registry there."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass
    try:
        import winreg
        from PIL import Image

        icon_dest = config_dir() / "app_icon.png"
        try:
            Image.open(asset_path("icon.ico")).convert("RGBA").resize(
                (256, 256)).save(icon_dest)
        except Exception:
            icon_dest = None

        key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, r"Software\Classes\AppUserModelId\%s" % APP_ID)
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Otto")
        winreg.SetValueEx(key, "IconBackgroundColor", 0, winreg.REG_SZ, "FF18181B")
        if icon_dest is not None:
            winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, str(icon_dest))
        winreg.CloseKey(key)
    except Exception:
        pass


def main():
    # Identify the app to Windows as "Otto" *before* the QApplication is built,
    # so tray toast notifications show the Otto name + icon instead of "Python".
    register_windows_identity()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Otto")
    app.setApplicationDisplayName("Otto")
    app.setOrganizationName("Otto")

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

    # ---- local settings web UI (API keys) ----
    start_settings_server()

    def open_settings():
        import webbrowser
        webbrowser.open(settings_url())

    # ---- system tray ----
    icon = app_icon()          # assets/main_icon.png
    if icon.isNull():
        icon = make_icon()     # fallback to the painted icon if it's missing
    app.setWindowIcon(icon)
    tray = QSystemTrayIcon(icon)
    tray.setToolTip("Otto — press the hotkey to summon")
    menu = QMenu()

    act_show = QAction("Show (or press hotkey)")
    act_show.triggered.connect(window.show_centered)
    act_settings = QAction("Settings (API keys)…")
    act_settings.triggered.connect(open_settings)
    act_reload = QAction("Reload config")
    act_reload.triggered.connect(lambda: window.reload_config(load_config()))
    act_config = QAction("Open config file…")
    act_config.triggered.connect(lambda: os.startfile(str(config_path())))
    act_quit = QAction("Quit")
    act_quit.triggered.connect(app.quit)
    for a in (act_show, act_settings, act_reload, act_config):
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
            "Otto",
            f"Ready. Press {hotkey} to summon the command box.",
            icon, 4000)
    except Exception as e:
        tray.showMessage(
            "Otto — hotkey failed",
            f"Could not register '{hotkey}': {e}. Use the tray icon instead.",
            icon, 6000)

    # First run with no key: open the settings page so setup is one paste away.
    if not config.api_key():
        tray.showMessage(
            "Otto — add your API key",
            "Opening settings in your browser. Paste your API key and save.",
            icon, 8000)
        QTimer.singleShot(600, open_settings)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
