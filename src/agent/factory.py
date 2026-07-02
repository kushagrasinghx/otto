"""Build the right agent from config.

Providers:
  gemini  -> GeminiAgent (Google GenAI)
  claude  -> ClaudeAgent on the direct Anthropic API
"""

from __future__ import annotations

from ..config import Config


class AgentConfigError(Exception):
    pass


def create_agent(config: Config):
    provider = config.provider
    agent_cfg = config.agent

    if provider == "gemini":
        key = config.api_key("gemini")
        if not key:
            raise AgentConfigError(
                "No Gemini API key. Run /settings to configure"
                "/ GEMINI_API_KEY (or your .env).")
        from .gemini_agent import GeminiAgent
        return GeminiAgent(key, config.model("gemini"), agent_cfg)

    if provider == "claude":
        key = config.api_key("claude")
        if not key:
            raise AgentConfigError(
                "No Claude API key. Run /settings to configure"
                "ANTHROPIC_API_KEY (or your .env).")
        import anthropic
        from .claude_agent import ClaudeAgent
        client = anthropic.Anthropic(api_key=key)
        return ClaudeAgent(client, config.model("claude"), agent_cfg)

    raise AgentConfigError(
        f"Unknown provider '{provider}'. Use 'gemini' or 'claude' "
        f"(set via config.json's 'provider' or the OTTO_PROVIDER env var).")
