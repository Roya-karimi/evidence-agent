"""The agent loop.

  1. Send the system prompt and the claim to the model, with the tool schemas.
  2. The model answers with one or more tool calls.
  3. Python runs each tool and sends the result back.
  4. Repeat until the model calls submit_verdict, or the step limit is reached.

Every step is recorded in `trace`, so each verdict can be audited afterwards.
"""

import json

from .prompts import system_prompt
from .tools import VERDICTS, submit_verdict_tool


def run_agent(claim: str, domain: dict, llm, mode: str = "agent", max_steps: int = 8) -> dict:
    tools = domain["tools"] if mode == "agent" else []
    registry = {t.name: t for t in tools}
    submit = submit_verdict_tool(domain.get("system", "v1"))
    schemas = [t.schema() for t in tools] + [submit.schema()]

    messages = [
        {"role": "system", "content": system_prompt(domain, mode)},
        {"role": "user", "content": f"Claim: {claim}"},
    ]
    trace, usage, seconds = [], {"prompt_tokens": 0, "completion_tokens": 0}, 0.0

    for step in range(1, max_steps + 1):
        resp = llm.chat(messages, schemas)
        seconds += resp.seconds
        for k in usage:
            usage[k] += resp.usage.get(k, 0) or 0
        messages.append(resp.assistant_message)

        if not resp.tool_calls:
            trace.append({"step": step, "event": "no_tool_call", "content": resp.content})
            messages.append({"role": "user", "content": "Please continue and finish with submit_verdict."})
            continue

        for call in resp.tool_calls:
            if call.name == submit.name:
                verdict = call.arguments.get("verdict")
                trace.append({"step": step, "tool": call.name, "arguments": call.arguments})
                return {
                    "verdict": verdict if verdict in VERDICTS else None,
                    "evidence_ids": call.arguments.get("evidence_ids", []),
                    "explanation": call.arguments.get("explanation", ""),
                    "error": None if verdict in VERDICTS else f"invalid verdict '{verdict}'",
                    "steps": step,
                    "tool_calls": sum(1 for t in trace if "tool" in t),
                    "usage": usage,
                    "seconds": round(seconds, 2),
                    "trace": trace,
                }

            if call.name in registry:
                try:
                    result = registry[call.name].function(**call.arguments)
                except Exception as exc:          # bad arguments: tell the model, let it retry
                    result = {"error": f"{type(exc).__name__}: {exc}"}
            else:
                result = {"error": f"Unknown tool '{call.name}'"}

            trace.append({"step": step, "tool": call.name, "arguments": call.arguments, "result": result})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

    return {
        "verdict": None, "evidence_ids": [], "explanation": "",
        "error": f"no verdict within {max_steps} steps",
        "steps": max_steps, "tool_calls": sum(1 for t in trace if "tool" in t),
        "usage": usage, "seconds": round(seconds, 2), "trace": trace,
    }
