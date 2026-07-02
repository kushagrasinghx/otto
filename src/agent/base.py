"""Shared dispatch + event plumbing for both provider agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..desktop.tools import DesktopController


@dataclass
class ToolResult:
    text: str
    screenshot: bytes | None = None
    screenshot_mime: str = "image/jpeg"
    is_done: bool = False


# Which vector icon (see ui/icons.py) represents each tool, and the default
# icon for non-action step kinds (thoughts, status lines, results, errors).
TOOL_ICON = {
    "get_state": "eye", "click": "cursor", "move_mouse": "cursor",
    "drag": "drag", "type_text": "keyboard", "press_keys": "keyboard",
    "scroll": "scroll", "launch_app": "launch", "switch_app": "window",
    "run_shell": "terminal", "clipboard": "clipboard", "wait": "clock",
    "done": "check",
}
KIND_ICON = {"status": "info", "thought": "thought", "result": "check", "error": "warning"}

# describe_call() embeds the icon key as a hidden prefix using this separator
# (a NUL byte never appears in human text, unlike "|" which can show up in
# shell commands) so the UI can split it back out without touching the
# emit()/Signal plumbing in the agent loops.
ICON_SEP = "\x00"


def split_icon(kind: str, text: str) -> tuple[str, str]:
    """Recover (icon_key, display_text) from an emitted step. Falls back to a
    per-kind default icon for plain messages that didn't go through
    describe_call (model "thought" text, status lines, results, errors)."""
    if ICON_SEP in text:
        icon_key, _, rest = text.partition(ICON_SEP)
        return icon_key, rest
    return KIND_ICON.get(kind, "info"), text


# A short human-readable summary of a call, for the live status log.
def describe_call(name: str, args: dict) -> str:
    icon_key = TOOL_ICON.get(name, "gear")
    if name == "get_state":
        text = "Looking at the screen"
    elif name == "click":
        text = f"Click ({args.get('x')}, {args.get('y')})"
    elif name == "move_mouse":
        text = f"Move to ({args.get('x')}, {args.get('y')})"
    elif name == "drag":
        text = "Drag"
    elif name == "type_text":
        text = f"Type “{args.get('text', '')}”"
    elif name == "press_keys":
        text = f"Press {args.get('keys')}"
    elif name == "scroll":
        text = f"Scroll {args.get('direction')}"
    elif name == "launch_app":
        text = f"Open {args.get('name')}"
    elif name == "switch_app":
        text = f"Switch to {args.get('name')}"
    elif name == "run_shell":
        text = f"Shell: {args.get('command', '')}"
    elif name == "clipboard":
        text = f"Clipboard {args.get('mode')}"
    elif name == "wait":
        text = f"Wait {args.get('seconds')}s"
    elif name == "done":
        text = "Done"
    else:
        text = name.replace("_", " ").title()
    return f"{icon_key}{ICON_SEP}{text}"


def execute_tool(controller: DesktopController, name: str, args: dict,
                 include_screenshot_default: bool = True) -> ToolResult:
    """Run a single tool call and return a ToolResult."""
    args = args or {}
    try:
        if name == "get_state":
            inc = args.get("include_screenshot", include_screenshot_default)
            state = controller.get_state(include_screenshot=bool(inc))
            return ToolResult(text=state.to_text(), screenshot=state.screenshot,
                              screenshot_mime=state.screenshot_mime)
        if name == "click":
            return ToolResult(controller.click(
                args["x"], args["y"], args.get("button", "left"),
                int(args.get("clicks", 1))))
        if name == "move_mouse":
            return ToolResult(controller.move_mouse(args["x"], args["y"]))
        if name == "drag":
            return ToolResult(controller.drag(
                args["start_x"], args["start_y"], args["end_x"], args["end_y"]))
        if name == "type_text":
            return ToolResult(controller.type_text(
                args.get("text", ""), args.get("x"), args.get("y"),
                bool(args.get("clear", False)), bool(args.get("press_enter", False))))
        if name == "press_keys":
            return ToolResult(controller.press_keys(args.get("keys", "")))
        if name == "scroll":
            return ToolResult(controller.scroll(
                args.get("direction", "down"), int(args.get("amount", 3)),
                args.get("x"), args.get("y")))
        if name == "launch_app":
            return ToolResult(controller.launch_app(args.get("name", "")))
        if name == "switch_app":
            return ToolResult(controller.switch_app(args.get("name", "")))
        if name == "run_shell":
            return ToolResult(controller.run_shell(args.get("command", "")))
        if name == "clipboard":
            return ToolResult(controller.clipboard(
                args.get("mode", "get"), args.get("text", "")))
        if name == "wait":
            return ToolResult(controller.wait(float(args.get("seconds", 1))))
        if name == "done":
            return ToolResult(args.get("summary", "Task finished."), is_done=True)
        return ToolResult(f"Unknown tool: {name}")
    except KeyError as e:
        return ToolResult(f"Missing required argument {e} for {name}.")
    except Exception as e:
        return ToolResult(f"Error running {name}: {e}")


# Event callback signature: emit(kind, text)
#   kind in {"status", "action", "thought", "result", "error"}
EmitFn = Callable[[str, str], None]
StopFn = Callable[[], bool]
