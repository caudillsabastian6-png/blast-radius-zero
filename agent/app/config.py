"""Configuration for the Blast Radius Zero agent.

Everything is read from environment variables. The Vultr Serverless
Inference API key is supplied ONLY this way at deploy/run time - it is never
hard-coded, never committed, and never passed into the sandbox worker (the
worker's environment is built from a strict whitelist in sandbox_client.py).
"""

import os
from dataclasses import dataclass


@dataclass
class Config:
    # Which inference adapter to use: "vultr" (real) or "mock" (offline tests/demo dry-run).
    inference_backend: str = "vultr"
    # Vultr Serverless Inference (OpenAI-compatible API).
    vultr_api_key: str = ""
    vultr_base_url: str = "https://api.vultrinference.com/v1"
    model: str = ""
    # Which sandbox backend to use: "docker" (production boundary) or "local" (dev only).
    sandbox_backend: str = "docker"
    worker_image: str = "brz-worker:latest"
    # Agent loop limits.
    max_steps: int = 12
    tool_timeout: int = 20
    max_output_chars: int = 4000
    # HTTP server.
    host: str = "0.0.0.0"
    port: int = 8080
    runs_dir: str = "runs"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            inference_backend=os.environ.get("BRZ_INFERENCE", "vultr").lower(),
            vultr_api_key=os.environ.get("VULTR_INFERENCE_API_KEY", ""),
            vultr_base_url=os.environ.get(
                "VULTR_INFERENCE_BASE_URL", "https://api.vultrinference.com/v1"
            ).rstrip("/"),
            model=os.environ.get("BRZ_MODEL", ""),
            sandbox_backend=os.environ.get("BRZ_SANDBOX", "docker").lower(),
            worker_image=os.environ.get("BRZ_WORKER_IMAGE", "brz-worker:latest"),
            max_steps=int(os.environ.get("BRZ_MAX_STEPS", "12")),
            tool_timeout=int(os.environ.get("BRZ_TOOL_TIMEOUT", "20")),
            max_output_chars=int(os.environ.get("BRZ_MAX_OUTPUT_CHARS", "4000")),
            host=os.environ.get("BRZ_HOST", "0.0.0.0"),
            port=int(os.environ.get("BRZ_PORT", "8080")),
            runs_dir=os.environ.get("BRZ_RUNS_DIR", "runs"),
        )

    def validate(self) -> list[str]:
        problems = []
        if self.inference_backend == "vultr":
            if not self.vultr_api_key:
                problems.append("VULTR_INFERENCE_API_KEY is not set")
            if not self.model:
                problems.append("BRZ_MODEL is not set (pick a model ID from GET /v1/models)")
        elif self.inference_backend != "mock":
            problems.append(f"unknown BRZ_INFERENCE backend: {self.inference_backend!r}")
        if self.sandbox_backend not in ("docker", "local"):
            problems.append(f"unknown BRZ_SANDBOX backend: {self.sandbox_backend!r}")
        return problems
