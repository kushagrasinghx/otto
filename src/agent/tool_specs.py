"""Canonical tool definitions, plus converters to Gemini and Claude formats.

One source of truth (`TOOLS`) is converted into each provider's schema so the
agent behaves identically regardless of the brain behind it.
"""

from __future__ import annotations

# Canonical JSON-schema-ish tool list.
TOOLS = [
    {
        "name": "get_state",
        "description": (
            "Look at the screen. Returns the active window, all open windows, "
            "the cursor position, and a list of interactive UI elements each "
            "with a clickable (x,y) coordinate, plus a screenshot. ALWAYS call "
            "this first and after any action whose result you need to verify."
        ),
        "properties": {
            "include_screenshot": {
                "type": "boolean",
                "description": "Attach a screenshot image (default true).",
            }
        },
        "required": [],
    },
    {
        "name": "click",
        "description": "Move the mouse to (x,y) and click. Use coordinates from get_state.",
        "properties": {
            "x": {"type": "integer", "description": "X in physical pixels."},
            "y": {"type": "integer", "description": "Y in physical pixels."},
            "button": {"type": "string", "enum": ["left", "right", "middle"],
                       "description": "Mouse button (default left)."},
            "clicks": {"type": "integer", "description": "1=single, 2=double (default 1)."},
        },
        "required": ["x", "y"],
    },
    {
        "name": "move_mouse",
        "description": "Move the mouse pointer to (x,y) without clicking.",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["x", "y"],
    },
    {
        "name": "drag",
        "description": "Press and hold the left button at the start point and release at the end point.",
        "properties": {
            "start_x": {"type": "integer"},
            "start_y": {"type": "integer"},
            "end_x": {"type": "integer"},
            "end_y": {"type": "integer"},
        },
        "required": ["start_x", "start_y", "end_x", "end_y"],
    },
    {
        "name": "type_text",
        "description": (
            "Type text. Optionally click a target (x,y) first, optionally clear "
            "the field first, and optionally press Enter after."
        ),
        "properties": {
            "text": {"type": "string"},
            "x": {"type": "integer", "description": "Optional: click here before typing."},
            "y": {"type": "integer", "description": "Optional: click here before typing."},
            "clear": {"type": "boolean", "description": "Select-all + delete first (default false)."},
            "press_enter": {"type": "boolean", "description": "Press Enter after typing (default false)."},
        },
        "required": ["text"],
    },
    {
        "name": "press_keys",
        "description": (
            "Press a key or key combo, e.g. 'enter', 'esc', 'ctrl+c', "
            "'alt+tab', 'win+r', 'ctrl+shift+escape'."
        ),
        "properties": {"keys": {"type": "string"}},
        "required": ["keys"],
    },
    {
        "name": "scroll",
        "description": "Scroll the screen (optionally after moving to x,y).",
        "properties": {
            "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
            "amount": {"type": "integer", "description": "Number of scroll steps (default 3)."},
            "x": {"type": "integer", "description": "Optional: move here before scrolling."},
            "y": {"type": "integer", "description": "Optional: move here before scrolling."},
        },
        "required": ["direction"],
    },
    {
        "name": "launch_app",
        "description": "Open an application by name using the Start menu (e.g. 'notepad', 'chrome', 'settings').",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
    {
        "name": "switch_app",
        "description": "Bring an already-open window to the foreground by (partial) title.",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
    {
        "name": "run_shell",
        "description": (
            "Run a PowerShell command and return its output. Use for file "
            "operations, launching things, system queries, etc. Avoid destructive "
            "commands unless the user clearly asked for them."
        ),
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
    {
        "name": "clipboard",
        "description": "Read or write the Windows clipboard.",
        "properties": {
            "mode": {"type": "string", "enum": ["get", "set"]},
            "text": {"type": "string", "description": "Text to set (when mode='set')."},
        },
        "required": ["mode"],
    },
    {
        "name": "wait",
        "description": "Pause for a number of seconds to let the UI catch up.",
        "properties": {"seconds": {"type": "number"}},
        "required": ["seconds"],
    },
    {
        "name": "done",
        "description": (
            "Call this when the task is complete (or cannot proceed). Provide a "
            "short summary of what you did or why you stopped."
        ),
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
    },
]

TOOL_NAMES = {t["name"] for t in TOOLS}

_JSON_TO_GEMINI_TYPE = {
    "string": "STRING", "integer": "INTEGER", "number": "NUMBER",
    "boolean": "BOOLEAN", "object": "OBJECT", "array": "ARRAY",
}


def _prop_to_gemini(prop: dict):
    from google.genai import types
    schema = types.Schema(type=_JSON_TO_GEMINI_TYPE.get(prop.get("type", "string"), "STRING"))
    if "description" in prop:
        schema.description = prop["description"]
    if "enum" in prop:
        schema.enum = prop["enum"]
    return schema


def gemini_tool():
    """Return a single google.genai types.Tool with all function declarations."""
    from google.genai import types
    decls = []
    for t in TOOLS:
        props = {k: _prop_to_gemini(v) for k, v in t["properties"].items()}
        params = types.Schema(
            type="OBJECT",
            properties=props,
            required=t.get("required", []),
        ) if props else None
        decls.append(types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=params,
        ))
    return types.Tool(function_declarations=decls)


def claude_tools() -> list[dict]:
    out = []
    for t in TOOLS:
        out.append({
            "name": t["name"],
            "description": t["description"],
            "input_schema": {
                "type": "object",
                "properties": t["properties"],
                "required": t.get("required", []),
            },
        })
    return out
