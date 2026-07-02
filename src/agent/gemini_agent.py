"""Gemini-powered Windows agent (default brain)."""

from __future__ import annotations

from ..desktop.tools import DesktopController
from . import tool_specs
from .base import (
    EmitFn, StopFn, describe_call, execute_tool, is_generic_done, is_real_action,
)
from .system_prompt import SYSTEM_PROMPT


class GeminiAgent:
    def __init__(self, api_key: str, model: str, agent_cfg: dict):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model or "gemini-2.5-flash"
        self.cfg = agent_cfg or {}
        self.controller = DesktopController(
            max_width=int(self.cfg.get("screenshot_max_width", 1280)))

    def run(self, instruction: str, emit: EmitFn, should_stop: StopFn):
        """Returns (kind, text): kind is 'reply' for a plain conversational
        answer (shown as a neutral message, no 'done' styling), 'result' for a
        task actually completed via the done() tool, or 'status' if cancelled."""
        from google.genai import types

        tool = tool_specs.gemini_tool()
        gen_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[tool],
            temperature=0.2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        contents = [types.Content(role="user", parts=[types.Part(text=instruction)])]
        include_shot = bool(self.cfg.get("include_screenshot", True))
        max_steps = int(self.cfg.get("max_steps", 40))
        did_action = False  # did we ever perform a real desktop action?

        for step in range(max_steps):
            if should_stop():
                return ("status", "Stopped.")

            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=contents, config=gen_config)
            except Exception as e:
                # Raise rather than emit+return: AgentWorker's except-clause
                # turns this into the single failure card (red).
                raise RuntimeError(f"Gemini API error: {e}") from e

            candidate = (response.candidates or [None])[0]
            if candidate is None or candidate.content is None:
                raise RuntimeError("Empty response from Gemini.")

            parts = candidate.content.parts or []
            contents.append(candidate.content)

            calls = [p.function_call for p in parts if getattr(p, "function_call", None)]
            narration = " ".join(p.text.strip() for p in parts
                                 if getattr(p, "text", None) and p.text.strip())

            if not calls:
                # Plain-text answer, no tool call. This is the final message —
                # a conversational reply, or a task summary if we did work.
                kind = "result" if did_action else "reply"
                return (kind, narration)

            # A done() call ends the run. Its accompanying narration is the real
            # answer (not a mid-task "thought"), and a generic "Done" summary is
            # dropped in favour of that narration — so a simple greeting shows a
            # single reply card, never a separate "Done".
            done_call = next((c for c in calls if c.name == "done"), None)
            action_calls = [c for c in calls if c.name != "done"]

            if action_calls and narration:
                emit("thought", narration)

            response_parts = []
            for call in action_calls:
                name = call.name
                args = dict(call.args or {})
                emit("action", describe_call(name, args))
                if should_stop():
                    return ("status", "Stopped.")
                if is_real_action(name):
                    did_action = True
                result = execute_tool(self.controller, name, args, include_shot)
                response_parts.append(types.Part.from_function_response(
                    name=name, response={"result": result.text}))
                if result.screenshot:
                    response_parts.append(types.Part.from_bytes(
                        data=result.screenshot, mime_type=result.screenshot_mime))

            if done_call is not None:
                summary = str((done_call.args or {}).get("summary", "")).strip()
                if is_generic_done(summary):
                    summary = narration  # may be "" -> panel just fades out
                return (("result" if did_action else "reply"), summary)

            contents.append(types.Content(role="user", parts=response_parts))

        raise RuntimeError(
            "Reached the maximum number of steps before completing the task.")
