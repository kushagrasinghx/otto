"""Actuation: take over mouse + keyboard and drive Windows.

`DesktopController` executes the actions the agent requests. `get_state` returns
both a textual observation and (optionally) screenshot bytes; every other action
returns a short string observation describing what happened.

Coordinates are physical pixels. The app sets per-monitor DPI awareness at
startup so pyautogui / uiautomation / mss all share the same coordinate space.
"""

from __future__ import annotations

import subprocess
import time

import pyautogui
import pyperclip

try:
    import uiautomation as auto
except Exception:
    auto = None

from . import uitree

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# Map friendly key names -> pyautogui key names.
_KEYMAP = {
    "win": "winleft", "windows": "winleft", "cmd": "winleft",
    "esc": "escape", "return": "enter", "del": "delete",
    "ins": "insert", "pgup": "pageup", "pgdn": "pagedown",
    "ctrl": "ctrl", "control": "ctrl", "alt": "alt", "shift": "shift",
}


def _norm_key(token: str) -> str:
    t = token.strip().lower()
    return _KEYMAP.get(t, t)


class DesktopController:
    def __init__(self, max_width: int = 1280):
        self.max_width = max_width

    # -- perception ---------------------------------------------------------
    def get_state(self, include_screenshot: bool = True):
        state = uitree.capture_state(include_screenshot, self.max_width)
        return state  # caller pulls .to_text() and .screenshot

    # -- mouse --------------------------------------------------------------
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> str:
        x, y = int(x), int(y)
        pyautogui.moveTo(x, y, duration=0.15)
        pyautogui.click(x=x, y=y, clicks=int(clicks), interval=0.08, button=button)
        return f"Clicked {button} x{clicks} at ({x}, {y})."

    def move_mouse(self, x: int, y: int) -> str:
        pyautogui.moveTo(int(x), int(y), duration=0.15)
        return f"Moved mouse to ({int(x)}, {int(y)})."

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> str:
        pyautogui.moveTo(int(start_x), int(start_y), duration=0.15)
        pyautogui.dragTo(int(end_x), int(end_y), duration=0.4, button="left")
        return f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})."

    def scroll(self, direction: str = "down", amount: int = 3,
               x: int | None = None, y: int | None = None) -> str:
        if x is not None and y is not None:
            pyautogui.moveTo(int(x), int(y), duration=0.1)
        ticks = int(amount) * 120
        direction = direction.lower()
        if direction in ("up", "down"):
            pyautogui.scroll(ticks if direction == "up" else -ticks)
        else:
            pyautogui.hscroll(-ticks if direction == "left" else ticks)
        return f"Scrolled {direction} ({amount})."

    # -- keyboard -----------------------------------------------------------
    def type_text(self, text: str, x: int | None = None, y: int | None = None,
                  clear: bool = False, press_enter: bool = False) -> str:
        if x is not None and y is not None:
            pyautogui.click(int(x), int(y))
            time.sleep(0.15)
        if clear:
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.05)
            pyautogui.press("delete")
            time.sleep(0.05)
        # Paste via clipboard for speed + full unicode support, then restore.
        saved = ""
        try:
            saved = pyperclip.paste()
        except Exception:
            pass
        try:
            pyperclip.copy(text)
            time.sleep(0.05)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.1)
        except Exception:
            pyautogui.typewrite(text, interval=0.01)
        finally:
            try:
                pyperclip.copy(saved)
            except Exception:
                pass
        if press_enter:
            time.sleep(0.1)
            pyautogui.press("enter")
        preview = text if len(text) <= 60 else text[:57] + "..."
        return f"Typed: {preview!r}" + (" + Enter" if press_enter else "")

    def press_keys(self, keys: str) -> str:
        parts = [_norm_key(k) for k in keys.replace(" ", "").split("+") if k]
        if not parts:
            return "No keys provided."
        if len(parts) == 1:
            pyautogui.press(parts[0])
        else:
            pyautogui.hotkey(*parts)
        return f"Pressed {'+'.join(parts)}."

    # -- apps / windows -----------------------------------------------------
    def launch_app(self, name: str) -> str:
        pyautogui.press("winleft")
        time.sleep(0.6)
        pyperclip_safe_type(name)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(1.0)
        return f"Launched '{name}' via Start search."

    def switch_app(self, name: str) -> str:
        if auto is not None:
            try:
                for w in auto.GetRootControl().GetChildren():
                    try:
                        wname = w.Name or ""
                        if name.lower() in wname.lower() and wname.strip():
                            w.SetActive()
                            try:
                                w.SetTopmost(True)
                                w.SetTopmost(False)
                            except Exception:
                                pass
                            return f"Switched to window: {wname}"
                    except Exception:
                        pass
            except Exception:
                pass
        pyautogui.hotkey("alt", "tab")
        return f"Could not find a window matching '{name}'; pressed Alt+Tab."

    # -- shell / clipboard / wait ------------------------------------------
    def run_shell(self, command: str) -> str:
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, timeout=60,
            )
            out = (result.stdout or "").strip()
            err = (result.stderr or "").strip()
            combined = out
            if err:
                combined += ("\n[stderr] " + err if combined else "[stderr] " + err)
            if len(combined) > 4000:
                combined = combined[:4000] + "\n...[truncated]"
            return combined or f"(no output, exit code {result.returncode})"
        except subprocess.TimeoutExpired:
            return "Command timed out after 60s."
        except Exception as e:
            return f"Shell error: {e}"

    def clipboard(self, mode: str = "get", text: str = "") -> str:
        if mode == "set":
            pyperclip.copy(text or "")
            return "Clipboard set."
        try:
            return f"Clipboard contents: {pyperclip.paste()}"
        except Exception as e:
            return f"Could not read clipboard: {e}"

    def wait(self, seconds: float = 1.0) -> str:
        seconds = max(0.0, min(float(seconds), 30.0))
        time.sleep(seconds)
        return f"Waited {seconds:.1f}s."


def pyperclip_safe_type(text: str) -> None:
    """Type into Start menu search (clipboard paste isn't reliable there)."""
    try:
        pyautogui.typewrite(text, interval=0.02)
    except Exception:
        pass
