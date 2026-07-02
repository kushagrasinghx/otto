"""Configuration loading/saving.

Config lives at %APPDATA%/WindowsAIAgent/config.json. On first run we copy the
bundled defaults there. Everything can also be driven purely from environment
variables (typically via the project's .env), with no config.json edits:
  - WINDOWS_PILOT_PROVIDER  overrides which provider runs (gemini/claude)
  - GEMINI_API_KEY / GOOGLE_API_KEY, ANTHROPIC_API_KEY     -> API keys
  - GEMINI_MODEL, CLAUDE_MODEL (alias ANTHROPIC_MODEL)     -> model id
Real OS environment variables always take precedence over .env, and .env takes
precedence over an empty value in config.json.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

# Load a project-root .env (if present) so GEMINI_API_KEY / ANTHROPIC_API_KEY
# defined there populate the environment. Real env vars still take precedence.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
except Exception:
    pass

DEFAULTS = {
    "provider": "gemini",
    "hotkey": "ctrl+space",
    "gemini": {"api_key": "", "model": "gemini-2.5-flash"},
    "claude": {"api_key": "", "model": "claude-opus-4-8"},
    "agent": {
        "max_steps": 40,
        "include_screenshot": True,
        "screenshot_max_width": 1280,
    },
}


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    d = Path(base) / "WindowsAIAgent"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return config_dir() / "config.json"


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, data: dict):
        self.data = data

    # convenience accessors -------------------------------------------------
    @property
    def provider(self) -> str:
        env_provider = (os.environ.get("WINDOWS_PILOT_PROVIDER") or "").strip().lower()
        if env_provider:
            return env_provider
        return self.data.get("provider", "gemini").lower()

    @property
    def hotkey(self) -> str:
        return self.data.get("hotkey", "ctrl+alt+space")

    def provider_block(self, name: str | None = None) -> dict:
        return self.data.get(name or self.provider, {})

    @property
    def agent(self) -> dict:
        return self.data.get("agent", DEFAULTS["agent"])

    def api_key(self, provider: str | None = None) -> str:
        provider = provider or self.provider
        block = self.provider_block(provider)
        key = (block.get("api_key") or "").strip()
        if key:
            return key
        # fall back to environment variables
        if provider == "gemini":
            return (os.environ.get("GOOGLE_API_KEY")
                    or os.environ.get("GEMINI_API_KEY") or "").strip()
        if provider == "claude":
            return (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        return ""

    def model(self, provider: str | None = None) -> str:
        provider = (provider or self.provider).lower()
        env_var = {"gemini": "GEMINI_MODEL", "claude": "CLAUDE_MODEL"}.get(provider)
        if env_var:
            val = (os.environ.get(env_var) or "").strip()
            if not val and provider == "claude":
                val = (os.environ.get("ANTHROPIC_MODEL") or "").strip()
            if val:
                return val
        return self.provider_block(provider).get("model", "")


VALID_PROVIDERS = ("gemini", "claude")


def update_provider(provider: str, model: str | None = None) -> "Config":
    """Persist a provider switch (and optional model override) to config.json.
    Used by the in-box `/model` command. Returns the freshly loaded Config."""
    provider = provider.lower()
    if provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. Use one of: {', '.join(VALID_PROVIDERS)}.")
    path = config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}
    merged = _deep_merge(DEFAULTS, data)
    merged["provider"] = provider
    if model:
        merged.setdefault(provider, {})["model"] = model
    path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return Config(merged)


def load_config() -> Config:
    path = config_path()
    if not path.exists():
        path.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")
        return Config(copy.deepcopy(DEFAULTS))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    return Config(_deep_merge(DEFAULTS, data))
