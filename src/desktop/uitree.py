"""Desktop perception: capture the Windows UI Automation tree + a screenshot.

This is the agent's "eyes". `capture_state` returns a compact textual snapshot
of the foreground window's interactive elements (each with a center coordinate
the agent can click), the list of open windows, and the cursor position. The
screenshot is returned separately as PNG/JPEG bytes for multimodal models.

Built on the same foundation as CursorTouch/Windows-MCP (uiautomation + a
screen grabber), reimplemented here so the whole app ships as one package.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

try:
    import uiautomation as auto
except Exception:  # pragma: no cover - only importable on Windows
    auto = None

import mss
from PIL import Image

# Control types that a human would actually interact with.
INTERACTIVE_TYPES = {
    "ButtonControl", "EditControl", "CheckBoxControl", "RadioButtonControl",
    "ComboBoxControl", "ListItemControl", "MenuItemControl", "TabItemControl",
    "HyperlinkControl", "TreeItemControl", "SplitButtonControl", "SliderControl",
    "DocumentControl", "DataItemControl", "HeaderItemControl",
}

MAX_ELEMENTS = 80
MAX_DEPTH = 40


@dataclass
class UIElement:
    index: int
    name: str
    control_type: str
    x: int
    y: int


@dataclass
class DesktopState:
    cursor: tuple[int, int]
    active_window: str
    windows: list[str]
    elements: list[UIElement]
    screen_size: tuple[int, int]
    screenshot: bytes | None = None
    screenshot_mime: str = "image/jpeg"
    notes: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = []
        lines.append(f"Screen size: {self.screen_size[0]}x{self.screen_size[1]} "
                     f"(coordinates below are TRUE physical pixels).")
        lines.append(f"Cursor at: ({self.cursor[0]}, {self.cursor[1]})")
        lines.append(f"Active window: {self.active_window or 'unknown'}")
        if self.windows:
            lines.append("Open windows: " + " | ".join(self.windows[:15]))
        lines.append("")
        if self.elements:
            lines.append("Interactive elements (click using the given x,y):")
            for el in self.elements:
                name = (el.name or "").strip().replace("\n", " ")
                if len(name) > 70:
                    name = name[:67] + "..."
                lines.append(f"  [{el.index}] {el.control_type:<16} "
                             f"({el.x},{el.y})  {name}")
        else:
            lines.append("No interactive elements detected via the accessibility "
                         "tree. Rely on the screenshot and click by coordinate.")
        for n in self.notes:
            lines.append(n)
        return "\n".join(lines)


def _safe(getter, default=""):
    try:
        return getter()
    except Exception:
        return default


def _collect_elements(root) -> list[UIElement]:
    elements: list[UIElement] = []
    idx = 0

    def walk(ctrl, depth):
        nonlocal idx
        if idx >= MAX_ELEMENTS or depth > MAX_DEPTH:
            return
        try:
            children = ctrl.GetChildren()
        except Exception:
            children = []
        for child in children:
            if idx >= MAX_ELEMENTS:
                return
            try:
                ctype = child.ControlTypeName
                if _safe(lambda: child.IsOffscreen, False):
                    walk(child, depth + 1)
                    continue
                rect = child.BoundingRectangle
                if rect.width() <= 0 or rect.height() <= 0:
                    walk(child, depth + 1)
                    continue
                name = _safe(lambda: child.Name, "")
                if ctype in INTERACTIVE_TYPES and (name or ctype == "EditControl"):
                    elements.append(UIElement(
                        index=idx,
                        name=name,
                        control_type=ctype.replace("Control", ""),
                        x=rect.xcenter(),
                        y=rect.ycenter(),
                    ))
                    idx += 1
            except Exception:
                pass
            walk(child, depth + 1)

    walk(root, 0)
    return elements


def _list_windows() -> list[str]:
    names: list[str] = []
    try:
        for w in auto.GetRootControl().GetChildren():
            try:
                if w.ControlTypeName not in ("WindowControl", "PaneControl"):
                    continue
                if _safe(lambda: w.IsOffscreen, False):
                    continue
                name = _safe(lambda: w.Name, "")
                if name and name not in names:
                    names.append(name)
            except Exception:
                pass
    except Exception:
        pass
    return names


def grab_screenshot(max_width: int = 1280) -> tuple[bytes, tuple[int, int]]:
    """Return (jpeg_bytes, (full_width, full_height)). The image may be scaled
    down for token efficiency; coordinates in the UI tree remain full-res."""
    with mss.mss() as sct:
        mon = sct.monitors[1]  # primary monitor
        raw = sct.grab(mon)
        full_size = (raw.width, raw.height)
        img = Image.frombytes("RGB", (raw.width, raw.height), raw.rgb)
    if max_width and img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue(), full_size


def capture_state(include_screenshot: bool = True,
                  screenshot_max_width: int = 1280) -> DesktopState:
    if auto is None:
        raise RuntimeError("uiautomation is unavailable (Windows only).")

    cursor = _safe(lambda: auto.GetCursorPos(), (0, 0))
    try:
        fg = auto.GetForegroundControl()
        active_window = _safe(lambda: fg.Name, "")
        top = fg
        # climb to the top-level window for a fuller element list
        for _ in range(10):
            parent = _safe(lambda: top.GetParentControl(), None)
            if parent is None or parent.ControlTypeName in ("PaneControl",) and \
                    _safe(lambda: parent.Name, "") == "":
                break
            if parent is None or top.ControlTypeName == "WindowControl":
                break
            top = parent
        elements = _collect_elements(top if top else fg)
    except Exception:
        active_window = ""
        elements = []

    windows = _list_windows()

    shot = None
    screen_size = (0, 0)
    if include_screenshot:
        try:
            shot, screen_size = grab_screenshot(screenshot_max_width)
        except Exception:
            shot = None
    if screen_size == (0, 0):
        try:
            with mss.mss() as sct:
                mon = sct.monitors[1]
                screen_size = (mon["width"], mon["height"])
        except Exception:
            screen_size = (1920, 1080)

    return DesktopState(
        cursor=cursor,
        active_window=active_window,
        windows=windows,
        elements=elements,
        screen_size=screen_size,
        screenshot=shot,
    )
