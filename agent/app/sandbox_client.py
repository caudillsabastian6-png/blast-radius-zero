"""Sandbox session clients.

A session is a live worker executor (worker/executor.py) spoken to over
JSON-lines on stdio. Two backends:

- DockerSandboxSession (production): starts ONE hardened container per run -
  no network, read-only root filesystem, tmpfs workspace, all capabilities
  dropped, no-new-privileges, unprivileged user, CPU/memory/pids limits, and
  an environment built from scratch (the worker never sees the agent's
  environment, so the inference API key cannot leak into it). The container
  is destroyed when the run ends. THIS is the security boundary.

- LocalSandboxSession (development/tests only): runs the same executor as a
  local subprocess with a scrubbed whitelist environment and a temp
  workspace. It gives process separation but NOT a security boundary - the
  machine's network and filesystem are still reachable from shell commands.
  It exists so the loop can be developed and tested anywhere, including
  machines without Docker. Never use it for the public demo.

Both backends talk to the identical executor, so tool behaviour is the same;
only the strength of the walls differs, and the run record states which
backend was used.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

WORKER_EXECUTOR = Path(__file__).resolve().parents[2] / "worker" / "executor.py"


class SandboxError(Exception):
    pass


class _StdioSession:
    """Shared JSON-lines plumbing over a worker process's stdio."""

    backend_name = "abstract"

    def __init__(self, proc: subprocess.Popen):
        self._proc = proc
        self._next_id = 0
        self.workspace: str | None = None

    def execute(self, op: str, args: dict | None = None) -> dict:
        if self._proc.poll() is not None:
            raise SandboxError("sandbox worker process has exited")
        self._next_id += 1
        request = {"id": self._next_id, "op": op, "args": args or {}}
        try:
            self._proc.stdin.write(json.dumps(request) + "\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline()
        except (BrokenPipeError, OSError) as exc:
            raise SandboxError(f"sandbox I/O failed: {exc}") from exc
        if not line:
            raise SandboxError("sandbox worker closed its output stream")
        response = json.loads(line)
        if response.get("id") != self._next_id:
            raise SandboxError("sandbox protocol desync: response id mismatch")
        return response

    def close(self) -> None:
        try:
            if self._proc.poll() is None:
                self._proc.stdin.close()
                self._proc.wait(timeout=5)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass


class LocalSandboxSession(_StdioSession):
    """DEV ONLY - see module docstring. Not a security boundary."""

    backend_name = "local-subprocess (development only, NOT a security boundary)"

    # The worker's environment is built from this whitelist ONLY. Nothing is
    # inherited from the agent process - in particular no API keys.
    _ENV_WHITELIST = ("PATH", "LANG", "LC_ALL", "TERM")

    def __init__(self, workspace: str | None = None, keep_workspace: bool = False):
        self._owns_workspace = workspace is None
        self._keep_workspace = keep_workspace
        ws = workspace or tempfile.mkdtemp(prefix="brz-sandbox-")
        os.makedirs(ws, exist_ok=True)
        env = {k: os.environ[k] for k in self._ENV_WHITELIST if k in os.environ}
        env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
        env["BRZ_WORKSPACE"] = ws
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        executor = os.environ.get("BRZ_WORKER_EXECUTOR", str(WORKER_EXECUTOR))
        proc = subprocess.Popen(
            [sys.executable, executor],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1, cwd=ws, env=env,
        )
        super().__init__(proc)
        self.workspace = ws

    def close(self) -> None:
        super().close()
        if self._owns_workspace and not self._keep_workspace and self.workspace:
            shutil.rmtree(self.workspace, ignore_errors=True)


class DockerSandboxSession(_StdioSession):
    """Production sandbox: one hardened, disposable container per run."""

    backend_name = "docker (hardened, network-less, disposable)"

    def __init__(self, image: str = "brz-worker:latest"):
        if shutil.which("docker") is None:
            raise SandboxError("docker CLI not found on PATH")
        self._container = f"brz-run-{uuid.uuid4().hex[:12]}"
        cmd = [
            "docker", "run", "--rm", "-i",
            "--name", self._container,
            "--network", "none",                 # no network at all
            "--read-only",                       # root filesystem is read-only
            "--tmpfs", "/workspace:rw,size=64m,mode=1777",  # only writable place
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--user", "65534:65534",             # nobody
            "--memory", "256m",
            "--cpus", "0.5",
            "--pids-limit", "128",
            "--env", "BRZ_WORKSPACE=/workspace",
            "--env", "HOME=/workspace",
            "--env", "PYTHONDONTWRITEBYTECODE=1",
            image,
        ]
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        super().__init__(proc)
        self.workspace = "/workspace (in-container tmpfs)"

    def close(self) -> None:
        super().close()
        # --rm removes the container on exit; force-remove if anything lingers.
        subprocess.run(["docker", "rm", "-f", self._container],
                       capture_output=True, timeout=10)


def make_session(config, workspace: str | None = None,
                 keep_workspace: bool = False) -> _StdioSession:
    if config.sandbox_backend == "docker":
        return DockerSandboxSession(image=config.worker_image)
    if config.sandbox_backend == "local":
        return LocalSandboxSession(workspace=workspace, keep_workspace=keep_workspace)
    raise SandboxError(f"unknown sandbox backend: {config.sandbox_backend!r}")
