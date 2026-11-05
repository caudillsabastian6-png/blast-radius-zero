"""Inference adapter interface.

The agent loop depends only on this: given the conversation messages, return
the model's next reply as text. The reply is expected to follow the action
protocol in app/protocol.py.
"""

from typing import Protocol


class InferenceError(Exception):
    pass


class InferenceClient(Protocol):
    def chat(self, messages: list[dict]) -> str:
        """Return the assistant's next reply (raw text) for `messages`."""
        ...
