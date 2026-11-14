"""Connection to the language model.

OpenAIChat calls the real API. ScriptedLLM replays fixed responses so the
agent loop can be tested offline, with no key and no cost.
"""

import json
import os
import time
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list
    assistant_message: dict          # appended to the conversation as-is
    usage: dict = field(default_factory=dict)
    seconds: float = 0.0
    model: str | None = None         # the model snapshot the API reports having used
    response_id: str | None = None


class OpenAIChat:
    """Chat Completions API with tool calling.

    Reads OPENAI_API_KEY and OPENAI_MODEL from the environment (or a .env file).
    Each request has a time limit, a retry limit and an output-token limit, so one
    claim cannot hang or grow without bound.
    """

    def __init__(self, model: str | None = None, temperature: float = 0.0,
                 timeout_seconds: float = 60.0, max_retries: int = 2, max_output_tokens: int = 1000):
        from openai import OpenAI  # imported here so tests run without the package

        self.client = OpenAI(timeout=timeout_seconds, max_retries=max_retries)
        self.model = model or os.environ["OPENAI_MODEL"]
        self.temperature = temperature
        self.settings = {"temperature": temperature, "timeout_seconds": timeout_seconds,
                         "max_retries": max_retries, "max_output_tokens": max_output_tokens}

    def chat(self, messages: list, tools: list) -> LLMResponse:
        start = time.perf_counter()
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="required",      # every turn must be a tool call
            temperature=self.temperature,
            max_completion_tokens=self.settings["max_output_tokens"],
        )
        msg = resp.choices[0].message
        calls = []
        for tc in msg.tool_calls or []:
            try:        # may be any JSON value; the agent loop validates it before use
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_unparseable": tc.function.arguments}
            calls.append(ToolCall(tc.id, tc.function.name, args))
        usage = resp.usage.model_dump() if resp.usage else {}
        assistant_message = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            assistant_message["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        return LLMResponse(
            content=msg.content,
            tool_calls=calls,
            assistant_message=assistant_message,
            usage=usage,
            seconds=time.perf_counter() - start,
            model=getattr(resp, "model", None),
            response_id=getattr(resp, "id", None),
        )


class ScriptedLLM:
    """Plays back a list of planned turns. Each turn is a list of (tool_name, args).

    A turn may also be an Exception, which is raised to simulate an API failure.
    """

    def __init__(self, turns: list):
        self.turns = list(turns)
        self.n = 0

    def chat(self, messages: list, tools: list) -> LLMResponse:
        planned = self.turns.pop(0) if self.turns else []
        if isinstance(planned, Exception):
            raise planned
        calls, raw = [], []
        for name, args in planned:
            self.n += 1
            call_id = f"call_{self.n}"
            calls.append(ToolCall(call_id, name, args))
            raw.append({"id": call_id, "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)}})
        message = {"role": "assistant", "content": None}
        if raw:
            message["tool_calls"] = raw
        return LLMResponse(content=None, tool_calls=calls, assistant_message=message)
