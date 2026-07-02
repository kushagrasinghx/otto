"""Claude-powered Windows agent (alternative brain)."""

from __future__ import annotations

import base64

from ..desktop.tools import DesktopController
from . import tool_specs
from .base import (
    EmitFn, StopFn, describe_call, execute_tool, is_generic_done, is_real_action,
)
from .system_prompt import SYSTEM_PROMPT


class ClaudeAgent:
    def __init__(self, client, model: str, agent_cfg: dict):
        self.client = client
        self.model = model or "claude-opus-4-8"
        self.cfg = agent_cfg or {}
        self.controller = DesktopController(
            max_width=int(self.cfg.get("screenshot_max_width", 1280)))

    def run(self, instruction: str, emit: EmitFn, should_stop: StopFn):
        """Returns (kind, text): 'reply' for a plain conversational answer,
        'result' for a task completed via done(), 'status' if cancelled."""
        tools = tool_specs.claude_tools()
        include_shot = bool(self.cfg.get("include_screenshot", True))
        max_steps = int(self.cfg.get("max_steps", 40))

        messages = [{"role": "user", "content": instruction}]
        did_action = False  # did we ever perform a real desktop action?

        for step in range(max_steps):
            if should_stop():
                return ("status", "Stopped.")

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    messages=messages,
                )
            except Exception as e:
                # Raise rather than emit+return: AgentWorker's except-clause
                # turns this into the single failure card (red).
                raise RuntimeError(f"Claude API error: {e}") from e

            messages.append({"role": "assistant", "content": response.content})

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            narration = " ".join(b.text.strip() for b in response.content
                                if b.type == "text" and b.text.strip())

            if not tool_uses:
                # Plain-text answer — final message (conversational reply, or a
                # task summary if we did work).
                kind = "result" if did_action else "reply"
                return (kind, narration)

            # done() ends the run; its accompanying narration is the real answer
            # and a generic "Done" summary is dropped for it, so a simple
            # greeting shows one reply card, never a separate "Done".
            done_use = next((tu for tu in tool_uses if tu.name == "done"), None)
            action_uses = [tu for tu in tool_uses if tu.name != "done"]

            if action_uses and narration:
                emit("thought", narration)

            tool_results = []
            for tu in action_uses:
                args = dict(tu.input or {})
                emit("action", describe_call(tu.name, args))
                if should_stop():
                    return ("status", "Stopped.")
                if is_real_action(tu.name):
                    did_action = True
                result = execute_tool(self.controller, tu.name, args, include_shot)
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

            if done_use is not None:
                summary = str((done_use.input or {}).get("summary", "")).strip()
                if is_generic_done(summary):
                    summary = narration  # may be "" -> panel just fades out
                return (("result" if did_action else "reply"), summary)

            messages.append({"role": "user", "content": tool_results})

        raise RuntimeError(
            "Reached the maximum number of steps before completing the task.")
