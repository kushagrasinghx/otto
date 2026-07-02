# Otto 🖱️⌨️

A Spotlight-style command box for Windows. Press a hotkey, type what you want in
plain English, and an AI agent **takes over your mouse, keyboard, and shell** to
actually do it — navigating apps, clicking, typing, running commands — like a
careful human assistant sitting at your PC.

Powered by **Gemini** (default) or **Claude** — your choice, via a config file.
The Windows-control tool design follows
[CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP),
reimplemented natively so the whole thing ships as one Python app.

---

## How it works

```
You type a request  →  LLM (Gemini/Claude)  →  loop:
                         1. get_state  (reads the UI tree + screenshot = "eyes")
                         2. picks ONE action (click / type / keys / launch / shell …)
                         3. performs it on the real desktop
                         4. looks again, until the task is done
```

The model sees your screen two ways: a **UI Automation tree** (every button,
field, menu item with exact click coordinates) and a **screenshot** (for layout
and anything the tree misses). It then drives the machine with real mouse and
keyboard input.

## Can I use my own Claude / Gemini API key?

**Yes — that's the whole point.** Put your key in the config file (or an
environment variable) and pick the provider. Default is Gemini.

---

## Setup

> Windows 10/11 + Python 3.11+ recommended.

```powershell
cd otto
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Add your API key (settings page)

The app runs a tiny **local settings page** at **http://127.0.0.1:9999** for
managing your keys — no file editing required. Open it any of these ways:

- Press the hotkey and type **`/settings`** in the command box, or
- Tray icon → **Settings (API keys)…**, or
- Just browse to http://127.0.0.1:9999

On first run with no key configured, it opens automatically. Paste your key,
pick the provider, and click **Save** — changes apply on your next command (no
restart needed, except for a hotkey change).

- **Gemini key:** https://aistudio.google.com/apikey
- **Claude key:** https://console.anthropic.com/

Everything is stored in `%APPDATA%\Otto\config.json` (tray → *Open config file…*
to edit by hand). Keys can also be supplied via environment variables
`GOOGLE_API_KEY` / `GEMINI_API_KEY` or `ANTHROPIC_API_KEY`.

### Run

```powershell
python run.py
```

A tray icon appears. Press **Ctrl+Alt+Space** (configurable) to summon the
command box. Type something and hit Enter:

- *"open notepad and write a haiku about the rain"*
- *"find the largest files in my Downloads folder"*
- *"open chrome and search for flights to Tokyo"*
- *"mute the volume and turn off wi‑fi"*

While the agent works, the box hides (so it's out of the way) and a small
status panel in the top‑right shows each action live. **Press the hotkey again
to cancel** a running task.

---

## Configuration (`config.json`)

| Key | Meaning |
|-----|---------|
| `provider` | `"gemini"` or `"claude"` |
| `hotkey` | Global summon hotkey, e.g. `"ctrl+space"` |
| `gemini.model` | e.g. `gemini-2.5-flash` (fast) or `gemini-2.5-pro` (stronger) |
| `claude.model` | e.g. `claude-opus-4-8` (direct Anthropic API) |
| `agent.max_steps` | Max actions per task (default 40) |
| `agent.include_screenshot` | Send screenshots to the model (default true) |
| `agent.screenshot_max_width` | Downscale screenshots to this width for cost |

---

## Project layout

```
run.py                     # entry point
src/
  main.py                  # tray icon, global hotkey, DPI awareness
  config.py                # config load/save
  webconfig.py             # local settings web UI (127.0.0.1:9999) for API keys
  ui/spotlight.py          # the Spotlight box, status toast, worker thread
  agent/
    factory.py             # builds Gemini or Claude agent from config
    gemini_agent.py        # Gemini function-calling loop
    claude_agent.py        # Claude tool-use loop
    tool_specs.py          # one tool definition -> both providers' formats
    base.py                # tool dispatch
    system_prompt.py       # operator instructions
  desktop/
    uitree.py              # perception: UI Automation tree + screenshot
    tools.py               # actuation: mouse, keyboard, apps, shell, clipboard
```

## Safety notes

- The agent is instructed to avoid destructive/irreversible actions unless you
  clearly ask for them, and never to enter passwords or payment details.
- It controls your **real** machine. Start with low-stakes tasks while you build
  trust, and keep the cancel hotkey handy.
- Everything runs locally except the LLM calls (your prompt + screenshots go to
  Gemini/Claude). Don't point it at sensitive screens you don't want sent to the
  provider.
