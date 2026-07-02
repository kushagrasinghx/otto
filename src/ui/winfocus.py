"""Force a window to the foreground and give it keyboard focus.

Windows blocks a process that doesn't own the foreground from calling
SetForegroundWindow — so when our global hotkey fires while another app is
active, Qt's activateWindow() is silently ignored: the popup shows (it's
always-on-top) but never becomes the *active* window, so keystrokes still go to
the previous app and Esc/click-away don't work.

The workaround is to briefly AttachThreadInput our thread to the foreground
window's thread (which lets us call SetForegroundWindow), plus lowering the
foreground-lock timeout. This is the standard technique launcher/Spotlight-style
apps use on Windows.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

try:
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                                 ctypes.POINTER(wintypes.DWORD)]
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.BringWindowToTop.argtypes = [wintypes.HWND]
    _user32.SetActiveWindow.argtypes = [wintypes.HWND]
    _user32.SetFocus.argtypes = [wintypes.HWND]
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    _AVAILABLE = True
except Exception:  # pragma: no cover - non-Windows
    _AVAILABLE = False

SW_SHOW = 5
ASFW_ANY = -1
SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001
SPIF_SENDCHANGE = 0x0002


def _relax_foreground_lock():
    try:
        _user32.SystemParametersInfoW(
            SPI_SETFOREGROUNDLOCKTIMEOUT, 0, ctypes.c_void_p(0), SPIF_SENDCHANGE)
    except Exception:
        pass
    try:
        _user32.AllowSetForegroundWindow(ASFW_ANY)
    except Exception:
        pass


def force_foreground(hwnd: int) -> None:
    """Bring hwnd to the foreground and give it keyboard focus, bypassing the
    Windows foreground-stealing lock. No-op on non-Windows / on failure."""
    if not _AVAILABLE or not hwnd:
        return
    handle = wintypes.HWND(int(hwnd))
    _relax_foreground_lock()

    fg = _user32.GetForegroundWindow()
    this_thread = _kernel32.GetCurrentThreadId()
    fg_thread = _user32.GetWindowThreadProcessId(fg, None) if fg else 0

    attached = False
    try:
        if fg_thread and fg_thread != this_thread:
            attached = bool(_user32.AttachThreadInput(fg_thread, this_thread, True))
        _user32.ShowWindow(handle, SW_SHOW)
        _user32.BringWindowToTop(handle)
        _user32.SetForegroundWindow(handle)
        _user32.SetActiveWindow(handle)
        _user32.SetFocus(handle)
    finally:
        if attached:
            _user32.AttachThreadInput(fg_thread, this_thread, False)
