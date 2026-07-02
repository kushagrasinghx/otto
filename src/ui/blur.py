"""Native Windows frosted-glass (acrylic) blur + rounded corners for a window.

Uses SetWindowCompositionAttribute with the acrylic accent policy. This is the
mechanism that actually works for Qt frameless windows: Qt's
WA_TranslucentBackground makes the window *layered* (WS_EX_LAYERED), and the
newer documented DWM "system backdrop" API (DWMWA_SYSTEMBACKDROP_TYPE / Mica /
DWMSBT_*) silently refuses to render on layered windows — it returns S_OK but
draws nothing. The older accent-policy acrylic is undocumented but is the one
that composites correctly behind a layered translucent window, including on
current Windows 11 builds. Rounded corners still come from the documented DWM
corner-preference attribute.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
WCA_ACCENT_POLICY = 19

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3


class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),  # 0xAABBGGRR
        ("AnimationId", ctypes.c_int),
    ]


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.POINTER(ACCENT_POLICY)),
        ("SizeOfData", ctypes.c_size_t),
    ]


def enable_blur(hwnd: int, tint: int = 0x8C0B0909, acrylic: bool = True) -> bool:
    """Frost the window backdrop; returns the API's real BOOL result (it does
    NOT raise on failure). `tint` is 0xAABBGGRR — default is zinc-950 #09090b
    at ~55% opacity, low enough that the blurred desktop clearly reads through
    while the panel still looks dark-neutral."""
    try:
        set_wca = ctypes.windll.user32.SetWindowCompositionAttribute
        set_wca.argtypes = [wintypes.HWND,
                            ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        set_wca.restype = wintypes.BOOL
    except Exception:
        return False
    accent = ACCENT_POLICY()
    accent.AccentState = (ACCENT_ENABLE_ACRYLICBLURBEHIND if acrylic
                          else ACCENT_ENABLE_BLURBEHIND)
    accent.AccentFlags = 0
    accent.GradientColor = tint
    accent.AnimationId = 0
    data = WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute = WCA_ACCENT_POLICY
    data.SizeOfData = ctypes.sizeof(accent)
    data.Data = ctypes.pointer(accent)
    try:
        return bool(set_wca(wintypes.HWND(int(hwnd)), ctypes.byref(data)))
    except Exception:
        return False


def round_corners(hwnd: int, small: bool = False) -> bool:
    """Round the window corners (Windows 11). No-op on older Windows."""
    try:
        pref = ctypes.c_int(DWMWCP_ROUNDSMALL if small else DWMWCP_ROUND)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(int(hwnd)), DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(pref), ctypes.sizeof(pref))
        return res == 0
    except Exception:
        return False
