"""Tool registry: what the LLM is allowed to ask for.

Every tool maps to one op of the sandbox worker (worker/executor.py). The
agent NEVER executes a tool itself - it only forwards the request to the
sandbox session and returns the observation. That separation is the whole
point of Blast Radius Zero.
"""

TOOLS = {
    "run_shell": {
        "op": "run_shell",
        "description": "Run a shell command inside the sandbox. cwd is the workspace. "
                       "The sandbox has no network access and no secrets.",
        "args": {"cmd": "string (required)", "timeout": "int seconds (optional)"},
    },
    "write_file": {
        "op": "write_file",
        "description": "Write a text file inside the sandbox workspace.",
        "args": {"path": "string, workspace-relative (required)", "content": "string (required)"},
    },
    "read_file": {
        "op": "read_file",
        "description": "Read a text file from the sandbox workspace.",
        "args": {"path": "string, workspace-relative (required)"},
    },
    "list_files": {
        "op": "list_files",
        "description": "List files in the sandbox workspace (or a subdirectory of it).",
        "args": {"path": "string, workspace-relative (optional, default '.')"},
    },
    "probe_environment": {
        "op": "probe",
        "description": "Self-audit the sandbox: list the environment variable NAMES it can "
                       "see, whether any look like secrets, whether a Docker socket is "
                       "present, and whether outbound network is reachable.",
        "args": {},
    },
}


def tool_catalog_for_prompt() -> str:
    lines = []
    for name, spec in TOOLS.items():
        args = ", ".join(f"{k}: {v}" for k, v in spec["args"].items()) or "no args"
        lines.append(f"- {name}({args}): {spec['description']}")
    return "\n".join(lines)
