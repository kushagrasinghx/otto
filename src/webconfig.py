"""Local settings web UI to configure API keys without editing files.

Serves a small shadcn-styled page at http://127.0.0.1:9999/ that reads and
writes the same %APPDATA%/Otto/config.json the app uses. Runs in a
daemon thread started at launch, so a PyInstaller-packaged build can be
reconfigured any time by opening the page (via the /settings command or the
tray). Uses only the standard library — nothing extra for PyInstaller to bundle.
"""

from __future__ import annotations

import io
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import DEFAULTS, _deep_merge, config_path, load_config, write_config

SETTINGS_HOST = "127.0.0.1"
SETTINGS_PORT = 9999


def settings_url() -> str:
    return f"http://{SETTINGS_HOST}:{SETTINGS_PORT}/"


def _asset_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parents[1]
    return str(root / "assets" / name)


_icon_png_cache: bytes | None = None


def _icon_png() -> bytes:
    """The app icon (assets/icon.ico) as a 128px PNG, for the settings page.
    Cached after first render. Empty bytes if the icon can't be loaded."""
    global _icon_png_cache
    if _icon_png_cache is not None:
        return _icon_png_cache
    try:
        from PIL import Image
        im = Image.open(_asset_path("icon.ico")).convert("RGBA").resize((128, 128))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        _icon_png_cache = buf.getvalue()
    except Exception:
        _icon_png_cache = b""
    return _icon_png_cache


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Otto · Settings</title>
<link rel="icon" type="image/png" href="/icon.png" />
<style>
  :root {
    --background: #09090b; --foreground: #fafafa;
    --card: #0c0c0f; --card-border: #1f1f23;
    --muted: #a1a1aa; --muted-2: #71717a;
    --input-border: #27272a; --input-bg: #101013;
    --ring: #3b82f6;
    --primary: #fafafa; --primary-fg: #18181b;
    --radius: 10px;
    --green: #22c55e; --red: #ef4444;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; background: var(--background);
    color: var(--foreground);
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    display: flex; align-items: flex-start; justify-content: center;
    padding: 48px 20px;
  }
  .card {
    width: 100%; max-width: 480px; background: var(--card);
    border: 1px solid var(--card-border); border-radius: 16px;
    padding: 28px; box-shadow: 0 20px 60px rgba(0,0,0,.45);
  }
  .brand { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
  .brand .logo { width: 26px; height: 26px; border-radius: 7px; display: block; }
  h1 { font-size: 18px; font-weight: 650; margin: 0; letter-spacing: -.01em; }
  .desc { color: var(--muted); font-size: 13px; margin: 6px 0 22px; line-height: 1.5; }
  .section-label { font-size: 12px; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: .06em; margin: 22px 0 12px; }
  label { display: block; font-size: 13px; font-weight: 500; margin: 0 0 6px; }
  .hint { font-size: 12px; color: var(--muted-2); margin-top: 6px; }
  .hint a { color: var(--muted); text-decoration: none; border-bottom: 1px dotted var(--muted-2); }
  .field { margin-bottom: 16px; }
  .input {
    width: 100%; height: 38px; padding: 0 12px; font-size: 13px;
    color: var(--foreground); background: var(--input-bg);
    border: 1px solid var(--input-border); border-radius: var(--radius);
    outline: none; transition: border-color .15s, box-shadow .15s;
    font-family: inherit;
  }
  .input:focus { border-color: var(--ring); box-shadow: 0 0 0 3px rgba(59,130,246,.25); }
  .input::placeholder { color: var(--muted-2); }
  .pw-wrap { position: relative; }
  .pw-wrap .input { padding-right: 42px; }
  .pw-toggle { position: absolute; right: 6px; top: 5px; height: 28px; width: 30px;
    display: flex; align-items: center; justify-content: center; cursor: pointer;
    background: transparent; border: none; color: var(--muted-2); border-radius: 6px; }
  .pw-toggle:hover { color: var(--foreground); background: #18181b; }
  .segmented { display: flex; gap: 4px; padding: 4px; background: var(--input-bg);
    border: 1px solid var(--input-border); border-radius: var(--radius); }
  .seg { flex: 1; height: 30px; border: none; background: transparent; cursor: pointer;
    color: var(--muted); font-size: 13px; font-weight: 500; border-radius: 7px;
    font-family: inherit; transition: background .15s, color .15s; }
  .seg[aria-selected="true"] { background: #26262b; color: var(--foreground); }
  .row { display: flex; gap: 12px; }
  .row .field { flex: 1; }
  .btn {
    width: 100%; height: 40px; margin-top: 22px; border: none; cursor: pointer;
    background: var(--primary); color: var(--primary-fg); font-weight: 600;
    font-size: 14px; border-radius: var(--radius); font-family: inherit;
    transition: opacity .15s;
  }
  .btn:hover { opacity: .9; }
  .btn:disabled { opacity: .5; cursor: default; }
  .toast { position: fixed; left: 50%; bottom: 28px; transform: translateX(-50%) translateY(20px);
    background: #18181b; border: 1px solid var(--card-border); color: var(--foreground);
    padding: 10px 16px; border-radius: 10px; font-size: 13px; opacity: 0;
    transition: opacity .2s, transform .2s; display: flex; align-items: center; gap: 9px;
    box-shadow: 0 10px 30px rgba(0,0,0,.4); pointer-events: none; }
  .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
  .toast .mark { width: 8px; height: 8px; border-radius: 50%; background: var(--green); }
  .toast.err .mark { background: var(--red); }
  .foot { margin-top: 18px; font-size: 12px; color: var(--muted-2); text-align: center; line-height: 1.5; }
</style>
</head>
<body>
  <div class="card">
    <div class="brand"><img class="logo" src="/icon.png" alt="Otto" /><h1>Otto</h1></div>
    <p class="desc">Configure the AI provider that drives your PC. Keys are stored
      locally in your config file and never leave this machine except to call the
      provider you choose.</p>

    <div class="field">
      <label>Active provider</label>
      <div class="segmented" id="seg">
        <button type="button" class="seg" data-v="gemini">Gemini</button>
        <button type="button" class="seg" data-v="claude">Claude</button>
      </div>
    </div>

    <div class="section-label">Google Gemini</div>
    <div class="field">
      <label for="gk">API key</label>
      <div class="pw-wrap">
        <input id="gk" class="input" type="password" placeholder="AIza…" autocomplete="off" spellcheck="false" />
        <button type="button" class="pw-toggle" data-for="gk" title="Show/Hide">&#128065;</button>
      </div>
      <div class="hint">Get one at <a href="https://aistudio.google.com/apikey" target="_blank">aistudio.google.com/apikey</a></div>
    </div>
    <div class="field">
      <label for="gm">Model</label>
      <input id="gm" class="input" type="text" placeholder="gemini-2.5-flash" autocomplete="off" spellcheck="false" />
    </div>

    <div class="section-label">Anthropic Claude</div>
    <div class="field">
      <label for="ck">API key</label>
      <div class="pw-wrap">
        <input id="ck" class="input" type="password" placeholder="sk-ant-…" autocomplete="off" spellcheck="false" />
        <button type="button" class="pw-toggle" data-for="ck" title="Show/Hide">&#128065;</button>
      </div>
      <div class="hint">Get one at <a href="https://console.anthropic.com/" target="_blank">console.anthropic.com</a></div>
    </div>
    <div class="field">
      <label for="cm">Model</label>
      <input id="cm" class="input" type="text" placeholder="claude-opus-4-8" autocomplete="off" spellcheck="false" />
    </div>

    <div class="section-label">General</div>
    <div class="field">
      <label for="hk">Summon hotkey</label>
      <input id="hk" class="input" type="text" placeholder="ctrl+space" autocomplete="off" spellcheck="false" />
      <div class="hint">Changing the hotkey takes effect after restarting the app.</div>
    </div>

    <button class="btn" id="save">Save settings</button>
    <div class="foot">You can reopen this page any time with <b>/settings</b> in the command box.</div>
  </div>

  <div class="toast" id="toast"><span class="mark"></span><span id="toastMsg">Saved</span></div>

<script>
  let provider = "gemini";
  const $ = (id) => document.getElementById(id);
  const seg = $("seg");

  function selectProvider(v) {
    provider = v;
    seg.querySelectorAll(".seg").forEach(b =>
      b.setAttribute("aria-selected", b.dataset.v === v ? "true" : "false"));
  }
  seg.querySelectorAll(".seg").forEach(b =>
    b.addEventListener("click", () => selectProvider(b.dataset.v)));

  document.querySelectorAll(".pw-toggle").forEach(btn =>
    btn.addEventListener("click", () => {
      const el = $(btn.dataset.for);
      el.type = el.type === "password" ? "text" : "password";
    }));

  function toast(msg, err) {
    const t = $("toast");
    $("toastMsg").textContent = msg;
    t.classList.toggle("err", !!err);
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 2400);
  }

  async function load() {
    try {
      const r = await fetch("/api/config");
      const c = await r.json();
      selectProvider((c.provider || "gemini").toLowerCase());
      $("gk").value = (c.gemini && c.gemini.api_key) || "";
      $("gm").value = (c.gemini && c.gemini.model) || "";
      $("ck").value = (c.claude && c.claude.api_key) || "";
      $("cm").value = (c.claude && c.claude.model) || "";
      $("hk").value = c.hotkey || "";
    } catch (e) { toast("Could not load settings", true); }
  }

  async function save() {
    const btn = $("save");
    btn.disabled = true;
    const body = {
      provider,
      hotkey: $("hk").value.trim(),
      gemini: { api_key: $("gk").value.trim(), model: $("gm").value.trim() },
      claude: { api_key: $("ck").value.trim(), model: $("cm").value.trim() },
    };
    try {
      const r = await fetch("/api/config", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(await r.text());
      toast("Settings saved");
    } catch (e) { toast("Save failed", true); }
    btn.disabled = false;
  }
  $("save").addEventListener("click", save);
  load();
</script>
</body>
</html>
"""


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body, ctype: str = "application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except Exception:
            pass

    def log_message(self, *args):  # keep the console quiet
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, INDEX_HTML, "text/html; charset=utf-8")
        elif self.path in ("/icon.png", "/favicon.ico"):
            data = _icon_png()
            if data:
                self._send(200, data, "image/png")
            else:
                self._send(404, json.dumps({"error": "no icon"}))
        elif self.path == "/api/config":
            self._send(200, json.dumps(self._current()))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/api/config":
            self._send(404, json.dumps({"error": "not found"}))
            return
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            self._send(400, json.dumps({"error": f"bad request: {e}"}))
            return
        try:
            self._save(payload)
            self._send(200, json.dumps({"ok": True}))
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}))

    def _current(self) -> dict:
        d = load_config().data
        g, c = d.get("gemini", {}), d.get("claude", {})
        return {
            "provider": d.get("provider", "gemini"),
            "hotkey": d.get("hotkey", "ctrl+space"),
            "gemini": {"api_key": g.get("api_key", ""), "model": g.get("model", "")},
            "claude": {"api_key": c.get("api_key", ""), "model": c.get("model", "")},
        }

    def _save(self, payload: dict):
        path = config_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            data = {}
        merged = _deep_merge(DEFAULTS, data)

        provider = str(payload.get("provider", "")).lower()
        if provider in ("gemini", "claude"):
            merged["provider"] = provider
        if payload.get("hotkey"):
            merged["hotkey"] = str(payload["hotkey"]).strip()
        for prov in ("gemini", "claude"):
            block = payload.get(prov) or {}
            if "api_key" in block:
                merged.setdefault(prov, {})["api_key"] = str(block["api_key"]).strip()
            if block.get("model"):
                merged.setdefault(prov, {})["model"] = str(block["model"]).strip()

        write_config(merged)  # atomic — never leaves a half-written key


_server: ThreadingHTTPServer | None = None


def start_settings_server() -> str | None:
    """Start the settings server in a daemon thread. Returns its URL, or None
    if the port is already taken (e.g. another instance is already serving it)."""
    global _server
    if _server is not None:
        return settings_url()
    try:
        _server = ThreadingHTTPServer((SETTINGS_HOST, SETTINGS_PORT), _Handler)
    except OSError:
        return None  # port busy — likely an existing instance
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    return settings_url()
