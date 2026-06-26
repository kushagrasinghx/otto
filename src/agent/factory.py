"""Build the right agent from config.

Providers:
  gemini   -> GeminiAgent (Google GenAI)
  claude   -> ClaudeAgent on the direct Anthropic API
  bedrock  -> ClaudeAgent on Amazon Bedrock (AWS credentials)
"""

from __future__ import annotations

import os

from ..config import Config


class AgentConfigError(Exception):
    pass


def _build_bedrock_client(config: Config):
    import anthropic

    blk = config.provider_block("bedrock")
    region = (blk.get("region") or "").strip() or os.environ.get("AWS_REGION") \
        or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"

    kwargs = {"aws_region": region}
    ak = (blk.get("access_key_id") or "").strip() or os.environ.get("AWS_ACCESS_KEY_ID")
    sk = (blk.get("secret_access_key") or "").strip() or os.environ.get("AWS_SECRET_ACCESS_KEY")
    st = (blk.get("session_token") or "").strip() or os.environ.get("AWS_SESSION_TOKEN")
    if ak:
        kwargs["aws_access_key"] = ak
    if sk:
        kwargs["aws_secret_key"] = sk
    if st:
        kwargs["aws_session_token"] = st

    use_mantle = blk.get("use_mantle", True)
    if use_mantle and hasattr(anthropic, "AnthropicBedrockMantle"):
        cls = anthropic.AnthropicBedrockMantle  # Messages-API Bedrock endpoint
    elif hasattr(anthropic, "AnthropicBedrock"):
        cls = anthropic.AnthropicBedrock        # legacy InvokeModel path
        prof = (blk.get("profile") or "").strip()
        if prof:
            kwargs["aws_profile"] = prof
    else:
        raise AgentConfigError(
            "Your 'anthropic' package has no Bedrock client. Install the extra:\n"
            "    pip install \"anthropic[bedrock]\"")

    try:
        return cls(**kwargs)
    except Exception as e:
        raise AgentConfigError(
            f"Could not create the Bedrock client: {e}\n"
            "Make sure boto3 is installed (pip install \"anthropic[bedrock]\") and "
            "your AWS credentials/region are set.")


def create_agent(config: Config):
    provider = config.provider
    agent_cfg = config.agent

    if provider == "gemini":
        key = config.api_key("gemini")
        if not key:
            raise AgentConfigError(
                "No Gemini API key. Add it to config.json or set GOOGLE_API_KEY "
                "/ GEMINI_API_KEY (or your .env).")
        from .gemini_agent import GeminiAgent
        return GeminiAgent(key, config.model("gemini"), agent_cfg)

    if provider == "claude":
        key = config.api_key("claude")
        if not key:
            raise AgentConfigError(
                "No Claude API key. Add it to config.json or set "
                "ANTHROPIC_API_KEY (or your .env).")
        import anthropic
        from .claude_agent import ClaudeAgent
        client = anthropic.Anthropic(api_key=key)
        return ClaudeAgent(client, config.model("claude"), agent_cfg)

    if provider == "bedrock":
        from .claude_agent import ClaudeAgent
        client = _build_bedrock_client(config)
        model = config.model("bedrock") or "anthropic.claude-opus-4-8"
        return ClaudeAgent(client, model, agent_cfg)

    raise AgentConfigError(
        f"Unknown provider '{provider}'. Use 'gemini', 'claude', or 'bedrock'.")
