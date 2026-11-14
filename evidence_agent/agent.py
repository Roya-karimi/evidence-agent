"""The agent loop.

  1. Send the system prompt and the claim to the model, with the tool schemas.
  2. The model answers with one or more tool calls.
  3. Python checks each call against the tool's schema, runs it, and sends the result back.
  4. Repeat until the model submits a verdict that passes the checks below,
     or the step limit is reached.

A verdict is accepted only if
  - its arguments fit the submit_verdict schema and the explanation is not empty;
  - it is the only call in its turn (the model has seen every result it relies on);
  - with tools: at least one evidence tool has returned a result, every cited ID was
    returned by a tool, and a `supported` or `contradicted` verdict cites at least one
    record whose estimates were retrieved;
  - without tools: every cited ID exists in the records, and a `supported` or
    `contradicted` verdict cites at least one.
A rejected submission is returned to the model as an error, so it can correct it.

These checks are structural. They show that a verdict cites evidence that was looked up,
not that the verdict is scientifically right; that is what the evaluation measures.

Every step is recorded in `trace`, so each verdict can be audited afterwards.

`status` in the result separates three outcomes:
  ok                 a verdict was accepted
  no_valid_verdict   the model did not produce an acceptable verdict within the step limit
  operational_error  the model call itself failed (network, API, time limit)
"""

import json

from .prompts import system_prompt
from .tools import submit_verdict_tool

ASSERTING = ("supported", "contradicted")


def _ids_in(result) -> tuple:
    """(IDs a tool result mentions, IDs whose record it actually opened)."""
    if not isinstance(result, dict):
        return set(), set()
    matches = result.get("matches")          # a list in find_records; a true/false flag in compare_field
    seen = {m["locus_id"] for m in matches if isinstance(m, dict) and "locus_id" in m} if isinstance(matches, list) else set()
    opened = set()
    if result.get("found"):
        rid = result.get("locus_id") or result.get("record_id")
        if rid:
            opened.add(rid)
    return seen | opened, opened


def _submission_problems(arguments, submit, mode, alone, evidence_calls, seen, opened, records) -> list:
    problems = submit.problems(arguments)
    if problems:
        return problems
    if not arguments["explanation"].strip():
        problems.append("explanation is empty")
    if not alone:
        problems.append("submit_verdict must be the only tool call in its turn")
    ids = arguments["evidence_ids"]
    if mode == "agent":
        if evidence_calls == 0:
            problems.append("no evidence tool has returned a result yet; look up the records first")
        unknown = [i for i in ids if i not in seen]
        if unknown:
            problems.append(f"evidence_ids not returned by any tool: {unknown}")
        if arguments["verdict"] in ASSERTING and not any(i in opened for i in ids):
            problems.append("a supported or contradicted verdict must cite at least one record "
                            "whose estimates were retrieved")
    else:
        unknown = [i for i in ids if i not in records]
        if unknown:
            problems.append(f"evidence_ids not in the records: {unknown}")
        if arguments["verdict"] in ASSERTING and not ids:
            problems.append("a supported or contradicted verdict must cite at least one record")
    return problems


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
    seen, opened, evidence_calls, models = set(), set(), 0, set()

    def finish(status, verdict=None, evidence_ids=(), explanation="", error=None, steps=max_steps):
        return {"status": status, "verdict": verdict, "evidence_ids": list(evidence_ids),
                "explanation": explanation, "error": error, "steps": steps,
                "tool_calls": sum(1 for t in trace if "tool" in t), "usage": usage,
                "seconds": round(seconds, 2), "model_returned": sorted(models), "trace": trace}

    for step in range(1, max_steps + 1):
        try:
            resp = llm.chat(messages, schemas)
        except Exception as exc:                       # network, API or time-limit failure
            trace.append({"step": step, "event": "model_call_failed", "error": f"{type(exc).__name__}: {exc}"})
            return finish("operational_error", error=f"{type(exc).__name__}: {exc}", steps=step)
        seconds += resp.seconds
        for k in usage:
            usage[k] += resp.usage.get(k, 0) or 0
        if getattr(resp, "model", None):
            models.add(resp.model)
        messages.append(resp.assistant_message)

        if not resp.tool_calls:
            trace.append({"step": step, "event": "no_tool_call", "content": resp.content})
            messages.append({"role": "user", "content": "Please continue and finish with submit_verdict."})
            continue

        for call in resp.tool_calls:
            entry = {"step": step, "tool": call.name, "arguments": call.arguments}
            if getattr(resp, "response_id", None):
                entry["response_id"] = resp.response_id

            if call.name == submit.name:
                problems = _submission_problems(call.arguments, submit, mode, len(resp.tool_calls) == 1,
                                                evidence_calls, seen, opened, domain["records"])
                if not problems:
                    trace.append(entry)
                    return finish("ok", call.arguments["verdict"], call.arguments["evidence_ids"],
                                  call.arguments["explanation"], steps=step)
                result = {"error": "Submission rejected: " + "; ".join(problems)}
                entry["rejected"] = problems
            elif call.name not in registry:
                result = {"error": f"Unknown tool '{call.name}'"}
            else:
                problems = registry[call.name].problems(call.arguments)
                if problems:
                    result = {"error": "Invalid arguments: " + "; ".join(problems)}
                else:
                    try:
                        result = registry[call.name].function(**call.arguments)
                    except Exception as exc:          # the tool refused the input: tell the model, let it retry
                        result = {"error": f"{type(exc).__name__}: {exc}"}
                    else:                             # bookkeeping is outside the try, so a bug here cannot
                        evidence_calls += 1           # be mistaken for a tool error
                        new_seen, new_opened = _ids_in(result)
                        seen |= new_seen
                        opened |= new_opened

            entry["result"] = result
            trace.append(entry)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

    return finish("no_valid_verdict", error=f"no valid verdict within {max_steps} steps")
