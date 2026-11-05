"""Vultr Serverless Inference adapter - the real inference path.

Written against Vultr's documented OpenAI-compatible chat API:

    POST {base_url}/chat/completions
    Authorization: Bearer <INFERENCE_API_KEY>
    {"model": "<model-id>", "messages": [...], "temperature": ..., "max_tokens": ...}

Default base_url is https://api.vultrinference.com/v1 (overridable via
VULTR_INFERENCE_BASE_URL). The API key is read from the environment by
app/config.py and held only in this process's memory. It is never logged,
never written to disk, and never passed into the sandbox.

Standard library only (urllib), so the agent runs anywhere Python 3.11+ runs.
"""

import json
import urllib.error
import urllib.request

from .base import InferenceError


class VultrServerlessClient:
    def __init__(self, api_key: str, model: str,
                 base_url: str = "https://api.vultrinference.com/v1",
                 timeout: int = 90, temperature: float = 0.2, max_tokens: int = 1024):
        if not api_key:
            raise InferenceError("Vultr inference API key is empty")
        if not model:
            raise InferenceError("Vultr inference model ID is empty")
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._temperature = temperature
        self._max_tokens = max_tokens

    def chat(self, messages: list[dict]) -> str:
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        request = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500] if exc.fp else ""
            raise InferenceError(f"Vultr inference HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise InferenceError(f"Vultr inference request failed: {exc}") from exc
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise InferenceError(f"unexpected Vultr inference response shape: {exc}") from exc
