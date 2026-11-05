"""The agent's action protocol.

The LLM drives the agent by replying with exactly one JSON object per turn:

    {"action": "tool",  "tool": "<tool name>", "args": {...}}
    {"action": "final", "answer": "<final report to the user>"}

This deliberately uses plain chat completions instead of any one vendor's
native tool-calling format, so ANY chat model served by Vultr Serverless
Inference can drive the agent. Parsing is strict: anything that is not a
single well-formed JSON object of one of these two shapes is rejected and
fed back to the model as an error observation.
"""

import json
from dataclasses import dataclass


@dataclass
class ToolAction:
    tool: str
    args: dict


@dataclass
class FinalAction:
    answer: str


class ProtocolError(Exception):
    pass


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    # Tolerate a ```json fenced block.
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        # Last resort: take the outermost {...} span.
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ProtocolError("reply contained no JSON object")
        try:
            value = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ProtocolError(f"reply was not valid JSON: {exc}")
    if not isinstance(value, dict):
        raise ProtocolError("reply JSON was not an object")
    return value


def parse_action(text: str) -> ToolAction | FinalAction:
    obj = _extract_json_object(text)
    action = obj.get("action")
    if action == "final":
        answer = obj.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ProtocolError("final action requires a non-empty 'answer' string")
        return FinalAction(answer=answer)
    if action == "tool":
        tool = obj.get("tool")
        args = obj.get("args", {})
        if not isinstance(tool, str) or not tool:
            raise ProtocolError("tool action requires a 'tool' name")
        if not isinstance(args, dict):
            raise ProtocolError("tool action 'args' must be an object")
        return ToolAction(tool=tool, args=args)
    raise ProtocolError(f"unknown action: {action!r} (expected 'tool' or 'final')")
