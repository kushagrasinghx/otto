"""Claude-powered Windows agent (alternative brain)."""

from __future__ import annotations

import base64

from ..desktop.tools import DesktopController
from . import tool_specs
from .base import EmitFn, StopFn, describe_call, execute_tool
from .system_prompt import SYSTEM_PROMPT


class ClaudeAgent:
    def __init__(self, client, model: str, agent_cfg: dict):
        # `client` is any Anthropic Messages-API client: anthropic.Anthropic,
        # AnthropicBedrockMantle, or AnthropicBedrock. They share the same
        # messages.create surface, so the loop below is provider-agnostic.
        self.client = client
        self.model = model or "claude-opus-4-8"
        self.cfg = agent_cfg or {}
        self.controller = DesktopController(
            max_width=int(self.cfg.get("screenshot_max_width", 1280)))

    def run(self, instruction: str, emit: EmitFn, should_stop: StopFn) -> str:
        tools = tool_specs.claude_tools()
        include_shot = bool(self.cfg.get("include_screenshot", True))
        max_steps = int(self.cfg.get("max_steps", 40))

        messages = [{"role": "user", "content": instruction}]

        for step in range(max_steps):
            if should_stop():
                return "Stopped by user."

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    messages=messages,
                )
            except Exception as e:
                emit("error", f"Claude API error: {e}")
                return f"Claude API error: {e}"

            messages.append({"role": "assistant", "content": response.content})

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            for b in response.content:
                if b.type == "text" and b.text.strip():
                    emit("thought", b.text.strip())

            if not tool_uses:
                if response.stop_reason == "end_turn":
                    text = " ".join(b.text for b in response.content if b.type == "text")
                    return text or "Done."
                messages.append({"role": "user", "content":
                    "Continue. Take the next action with a tool, or call done."})
                continue

            tool_results = []
            for tu in tool_uses:
                args = dict(tu.input or {})
                emit("action", describe_call(tu.name, args))
                if should_stop():
                    return "Stopped by user."

                result = execute_tool(self.controller, tu.name, args, include_shot)

                if result.is_done:
                    emit("result", result.text)
                    return result.text

                content = [{"type": "text", "text": result.text}]
                if result.screenshot:
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": result.screenshot_mime,
                            "data": base64.standard_b64encode(result.screenshot).decode(),
                        },
                    })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": content,
                })

            messages.append({"role": "user", "content": tool_results})

        emit("error", "Reached the step limit before finishing.")
        return "Reached the maximum number of steps before completing the task."
