"""Native Windows frosted-glass (acrylic) blur + rounded corners for a window.

Uses the undocumented SetWindowCompositionAttribute for the backdrop blur and
DwmSetWindowAttribute for Win11 rounded corners. Both are wrapped in try/except
so the app still runs (just without blur) on older Windows or if the calls fail.
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


def enable_blur(hwnd: int, tint: int = 0xD20B0909, acrylic: bool = True) -> bool:
    """Frost the window backdrop. `tint` is 0xAABBGGRR (default: true Tailwind
    zinc-950 #09090b, ~82% opacity — R and G equal, B only +2, so the frost
    reads as neutral black-zinc instead of the cool/blue cast a higher-blue
    tint produces)."""
    try:
        set_wca = ctypes.windll.user32.SetWindowCompositionAttribute
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
        set_wca.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        set_wca(int(hwnd), ctypes.byref(data))
        return True
    except Exception:
        return False


def round_corners(hwnd: int, small: bool = False) -> bool:
    """Round the window corners (Windows 11). No-op on older Windows."""
    try:
        pref = ctypes.c_int(DWMWCP_ROUNDSMALL if small else DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            int(hwnd), DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(pref), ctypes.sizeof(pref))
        return True
    except Exception:
        return False
