# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for Otto.

Build with:   pyinstaller otto.spec --noconfirm
Output:       dist/Otto.exe   (single file, no console window)

Edit APP_NAME / APP_ICON below to rebrand.
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

# ---------------------------------------------------------------------------
# Edit these two lines to change the app name and icon.
APP_NAME = "Otto"
APP_ICON = "assets/icon.ico"
# ---------------------------------------------------------------------------

# Bundle packages PyInstaller can't fully trace on its own (native/plugin/data
# bits). The rest of the app is plain Python + PySide6 (which has its own hook).
datas, binaries, hiddenimports = [], [], []
for pkg in ("google", "anthropic", "uiautomation", "mss", "pyautogui",
            "pyscreeze", "keyboard", "pyperclip"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass
hiddenimports += collect_submodules("comtypes")  # uiautomation's COM backend

# App image assets used at runtime (tray/notification/popup logo + the
# notification-header icon copied into %APPDATA%\Otto at startup).
datas += [
    ("assets/main_icon.svg", "assets"),
    ("assets/icon.ico", "assets"),
]


a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # windowed app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=APP_ICON,
)
