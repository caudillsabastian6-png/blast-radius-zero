#!/usr/bin/env python3
"""Blast Radius Zero - sandbox worker executor.

This process is the ONLY thing that ever executes commands the LLM asks for.
It runs inside the sandbox (a hardened, network-less Docker container in
production; a scrubbed subprocess for local development) and speaks a tiny
JSON-lines protocol over stdin/stdout:

    request : {"id": <int>, "op": <str>, "args": {...}}
    response: {"id": <int>, "ok": <bool>, "result": {...} | "error": <str>}

Ops:
    run_shell   {cmd, timeout}      run a shell command with cwd = workspace
    write_file  {path, content}     write a text file inside the workspace
    read_file   {path}              read a text file from the workspace
    list_files  {path}              list files under a workspace path
    probe       {}                  self-audit: what can this sandbox see?

File ops are jailed to the workspace directory: absolute paths outside it and
".." escapes are rejected. run_shell is confined by the sandbox boundary
itself (in production: a throwaway container with --network none, a read-only
root filesystem, dropped capabilities and no secrets in its environment).

Standard library only. Python 3.11+.
"""

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

MAX_OUTPUT_CHARS = 8000          # per-call stdout/stderr cap returned to agent
MAX_FILE_CHARS = 200_000         # largest file write/read via file ops
MAX_LIST_ENTRIES = 500
DEFAULT_TIMEOUT = 20
MAX_TIMEOUT = 120

WORKSPACE = Path(os.environ.get("BRZ_WORKSPACE", "/workspace")).resolve()

SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL")


class JailError(Exception):
    """Raised when a file op tries to escape the workspace."""


def jail(raw_path: str) -> Path:
    """Resolve a user-supplied path and confine it to the workspace."""
    if raw_path is None or raw_path == "":
        return WORKSPACE
    candidate = Path(raw_path)
    resolved = candidate.resolve() if candidate.is_absolute() else (WORKSPACE / candidate).resolve()
    if resolved != WORKSPACE and WORKSPACE not in resolved.parents:
        raise JailError(f"path escapes the sandbox workspace: {raw_path!r}")
    return resolved


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated, {len(text) - limit} more chars]"


def op_run_shell(args: dict) -> dict:
    cmd = args.get("cmd", "")
    if not isinstance(cmd, str) or not cmd.strip():
        raise ValueError("run_shell requires a non-empty 'cmd' string")
    timeout = min(int(args.get("timeout", DEFAULT_TIMEOUT)), MAX_TIMEOUT)
    shell = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
    try:
        proc = subprocess.run(
            [shell, "-c", cmd],
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": _truncate(proc.stdout or ""),
            "stderr": _truncate(proc.stderr or ""),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": None,
            "stdout": _truncate((exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
            "stderr": _truncate((exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")),
            "timed_out": True,
            "timeout_seconds": timeout,
        }


def op_write_file(args: dict) -> dict:
    path = jail(args.get("path", ""))
    content = args.get("content", "")
    if not isinstance(content, str):
        raise ValueError("write_file 'content' must be a string")
    if len(content) > MAX_FILE_CHARS:
        raise ValueError(f"write_file content exceeds {MAX_FILE_CHARS} chars")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"path": str(path.relative_to(WORKSPACE)), "bytes_written": len(content.encode("utf-8"))}


def op_read_file(args: dict) -> dict:
    path = jail(args.get("path", ""))
    if not path.is_file():
        raise ValueError(f"no such file in workspace: {args.get('path')!r}")
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "path": str(path.relative_to(WORKSPACE)),
        "content": _truncate(text, MAX_FILE_CHARS),
        "truncated": len(text) > MAX_FILE_CHARS,
    }


def op_list_files(args: dict) -> dict:
    root = jail(args.get("path", ""))
    if not root.exists():
        raise ValueError(f"no such path in workspace: {args.get('path')!r}")
    entries = []
    if root.is_file():
        entries.append({"path": str(root.relative_to(WORKSPACE)), "size": root.stat().st_size})
    else:
        for current, _dirs, files in os.walk(root):
            for name in sorted(files):
                full = Path(current) / name
                entries.append({
                    "path": str(full.relative_to(WORKSPACE)),
                    "size": full.stat().st_size,
                })
                if len(entries) >= MAX_LIST_ENTRIES:
                    break
            if len(entries) >= MAX_LIST_ENTRIES:
                break
    return {"entries": entries, "count": len(entries)}


def op_probe(args: dict) -> dict:
    """Self-audit: report exactly what this sandbox can see and reach."""
    env_names = sorted(os.environ.keys())
    secret_like = [n for n in env_names if any(m in n.upper() for m in SECRET_MARKERS)]

    network = {"target": "1.1.1.1:443", "reachable": False, "error": None}
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=2):
            network["reachable"] = True
    except OSError as exc:
        network["error"] = f"{type(exc).__name__}: {exc}"

    return {
        "hostname": socket.gethostname(),
        "uid": os.getuid() if hasattr(os, "getuid") else None,
        "workspace": str(WORKSPACE),
        "env_var_names": env_names,
        "secret_like_env_vars": secret_like,
        "docker_socket_present": os.path.exists("/var/run/docker.sock"),
        "network_test": network,
    }


OPS = {
    "run_shell": op_run_shell,
    "write_file": op_write_file,
    "read_file": op_read_file,
    "list_files": op_list_files,
    "probe": op_probe,
}


def handle(request: dict) -> dict:
    req_id = request.get("id")
    op = request.get("op")
    args = request.get("args") or {}
    fn = OPS.get(op)
    if fn is None:
        return {"id": req_id, "ok": False, "error": f"unknown op: {op!r}"}
    try:
        return {"id": req_id, "ok": True, "result": fn(args)}
    except (JailError, ValueError) as exc:
        return {"id": req_id, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    except Exception as exc:  # never crash the executor loop on one bad call
        return {"id": req_id, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {"id": None, "ok": False, "error": f"bad json: {exc}"}
        else:
            response = handle(request)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
