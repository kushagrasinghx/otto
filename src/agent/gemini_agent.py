"""Gemini-powered Windows agent (default brain)."""

from __future__ import annotations

from ..desktop.tools import DesktopController
from . import tool_specs
from .base import EmitFn, StopFn, describe_call, execute_tool
from .system_prompt import SYSTEM_PROMPT


class GeminiAgent:
    def __init__(self, api_key: str, model: str, agent_cfg: dict):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model or "gemini-2.5-flash"
        self.cfg = agent_cfg or {}
        self.controller = DesktopController(
            max_width=int(self.cfg.get("screenshot_max_width", 1280)))

    def run(self, instruction: str, emit: EmitFn, should_stop: StopFn) -> str:
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

        for step in range(max_steps):
            if should_stop():
                return "Stopped by user."

            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=contents, config=gen_config)
            except Exception as e:
                emit("error", f"Gemini API error: {e}")
                return f"Gemini API error: {e}"

            candidate = (response.candidates or [None])[0]
            if candidate is None or candidate.content is None:
                emit("error", "Empty response from Gemini.")
                return "Empty response from model."

            parts = candidate.content.parts or []
            contents.append(candidate.content)

            calls = [p.function_call for p in parts if getattr(p, "function_call", None)]
            texts = [p.text for p in parts if getattr(p, "text", None)]
            for t in texts:
                if t and t.strip():
                    emit("thought", t.strip())

            if not calls:
                # Model spoke without acting; nudge it to continue.
                if texts:
                    contents.append(types.Content(role="user", parts=[types.Part(
                        text="Continue. Take the next action with a tool, or call "
                             "done if the task is complete.")]))
                    continue
                return "Model produced no action."

            # Execute each requested call; build a single response Content.
            response_parts = []
            for call in calls:
                name = call.name
                args = dict(call.args or {})
                emit("action", describe_call(name, args))
                if should_stop():
                    return "Stopped by user."

                result = execute_tool(self.controller, name, args, include_shot)

                if result.is_done:
                    emit("result", result.text)
                    return result.text

                response_parts.append(types.Part.from_function_response(
                    name=name, response={"result": result.text}))
                if result.screenshot:
                    response_parts.append(types.Part.from_bytes(
                        data=result.screenshot, mime_type=result.screenshot_mime))

            contents.append(types.Content(role="user", parts=response_parts))

        emit("error", "Reached the step limit before finishing.")
        return "Reached the maximum number of steps before completing the task."
