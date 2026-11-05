"""Glass Box pages — Blast Radius Zero.

inspect_page(): the "Inspect our sandbox" page — the claim, how to verify
it yourself, and the architecture in plain English.

replay_page(record): a plain-English replay of ONE run record (the shape
produced by agent/app/loop.py). All record text is html-escaped: run
records contain untrusted content (tasks, file contents, tool output).

Stdlib only, no external assets.
"""

import html
import json

_STYLE = """
  body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 860px; padding: 0 1rem; background:#0d1117; color:#e6edf3; }
  h1 { margin-bottom: .2rem; }
  h2 { margin-top: 1.8rem; }
  .sub { color:#9da7b3; margin-top:0; }
  p, li { line-height:1.55; color:#c9d1d9; }
  .badge { display:inline-block; border:1px solid #30363d; border-radius:999px; padding:.1rem .6rem; margin-right:.4rem; font-size:.8rem; color:#9da7b3;}
  code { background:#161b22; border:1px solid #30363d; border-radius:.3rem; padding:.1rem .35rem; font-size:.88em; }
  pre { background:#161b22; border:1px solid #30363d; border-radius:.5rem; padding:.8rem; overflow:auto; white-space:pre-wrap; font-size:.82rem; }
  .answer { background:#0f2c1a; border:1px solid #238636; border-radius:.5rem; padding:.8rem; white-space:pre-wrap; }
  .claim { background:#161b22; border:1px solid #30363d; border-radius:.5rem; padding:.8rem 1rem; font-size:1.05rem; }
  .step { background:#161b22; border:1px solid #30363d; border-radius:.5rem; padding:.6rem .8rem; margin:.5rem 0; }
  a { color:#58a6ff; }
"""


def _doc(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{_STYLE}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def inspect_page() -> str:
    body = """<h1>Inspect our sandbox</h1>
<p class="sub">The Glass Box &mdash; Blast Radius Zero</p>

<div class="claim">Reasoning lives on Vultr Serverless Inference; this VM only
runs sandboxed tools &mdash; and no API keys or credentials exist inside the
sandbox.</div>

<h2>Verify it yourself</h2>
<p><a href="/containment-report">Open the live containment report</a> &mdash; a
fresh self-audit, run on demand inside a real sandbox session. Each probe line
proves one part of the claim:</p>
<ul>
  <li><strong>Environment variable names</strong> &mdash; shows exactly which
  variables the sandbox can see, so you can check the list yourself instead of
  trusting us that it is short.</li>
  <li><strong>Secret-like variables</strong> &mdash; flags anything whose name
  looks like a key, token, password or credential; the expected result is that
  there are none, because nothing secret is ever passed in.</li>
  <li><strong>Docker socket</strong> &mdash; checks whether the container
  runtime socket is reachable from inside; it is not mounted, so the sandbox
  cannot spawn or control other containers to escape through.</li>
  <li><strong>Network reachability</strong> &mdash; tries to reach the outside
  world; the sandbox has no network, so there is nowhere for data to be sent
  even if the model were talked into trying.</li>
</ul>
<p>Prefer to run the code yourself? From the repository root:</p>
<pre>python3 tests/run_tests.py</pre>
<p>The suite has 55 tests. The original 22 cover three areas: <strong>containment</strong>
(the sandbox cannot see secrets, reach the network, or escape),
<strong>protocol</strong> (the model&rsquo;s replies are parsed strictly &mdash;
anything that is not one well-formed JSON action is rejected), and
<strong>loop</strong> (the agent loop forwards tool calls to the sandbox and
executes nothing itself). The remaining tests cover the Gauntlet classifier
and frozen attack set, the Pocket Gate two-key rule, and page rendering.
Docker-specific containment assertions run when a
Docker daemon and the worker image are present, and skip cleanly otherwise.</p>
<p>Code judges: read these three files first &mdash</p>
<ul>
  <li><code>worker/executor.py</code> &mdash; the sandbox itself: the worker
  that runs tools inside the disposable container.</li>
  <li><code>agent/app/sandbox_client.py</code> &mdash; the environment
  whitelist and container hardening applied to every sandbox session.</li>
  <li><code>agent/app/loop.py</code> &mdash; the agent loop, where file
  contents are data, never instructions: tool output comes back strictly as
  an observation, and the system prompt forbids obeying instructions embedded
  in files.</li>
</ul>

<h2>Watch it work</h2>
<p><a href="/gauntlet">Watch it refuse attacks in the Gauntlet</a> &mdash; a
scripted Saboteur fires a frozen set of attacks at the agent and the
scoreboard shows what landed and what was contained.</p>
<p><a href="/gauntlet/attacks">Read the frozen attack set</a> &mdash; every
attack the Gauntlet fires, exactly as specified, so the test cannot quietly
get easier.</p>

<h2>How it fits together</h2>
<div class="step"><strong>1. Task in.</strong> A task (and any files it needs)
arrives at the agent service. Files are treated as data from the start.</div>
<div class="step"><strong>2. Inference plans.</strong> The model, running on
Vultr Serverless Inference, replies with exactly one JSON action at a time:
call a tool, or give the final report. It never executes anything itself.</div>
<div class="step"><strong>3. Tools run in the sandbox.</strong> Each tool call
is forwarded to a disposable, network-less sandbox session that holds no
secrets. Only the observation &mdash; what the tool returned &mdash; comes
back.</div>
<div class="step"><strong>4. Dry-run / proposals only.</strong> Work inside
the sandbox can read, check and draft, but it changes nothing real: the store,
the money and the credentials are simply not in there.</div>
<div class="step"><strong>5. Human gate.</strong> Anything that would matter
in the real world leaves as a proposal for a human to approve. The agent is
allowed to do nothing alone.</div>
"""
    return _doc("Inspect our sandbox \u2014 Blast Radius Zero", body)


def _truncate(text: str, limit: int = 500) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"... [truncated, {len(text)} chars total]"


def _args_summary(args) -> str:
    if not args:
        return "no arguments"
    try:
        text = json.dumps(args, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        text = str(args)
    return _truncate(text, 200)


def _narrate(entry: dict) -> str:
    kind = entry.get("kind", "")
    observation = str(entry.get("observation") or "")
    if kind == "seed":
        args = entry.get("args") or {}
        path = args.get("path", "a file") if isinstance(args, dict) else "a file"
        return f"The workspace was seeded with {html.escape(str(path))}."
    if kind == "tool":
        tool = html.escape(str(entry.get("tool") or "a tool"))
        summary = html.escape(_args_summary(entry.get("args")))
        outcome = "it worked" if entry.get("ok") else "it failed"
        obs = html.escape(_truncate(observation))
        return (
            f"The agent asked the sandbox to {tool} ({summary}) "
            f"&mdash; {outcome}: {obs}"
        )
    if kind == "tool_error":
        tool = html.escape(str(entry.get("tool") or "a tool"))
        summary = html.escape(_args_summary(entry.get("args")))
        obs = html.escape(_truncate(observation))
        return (
            f"The agent asked the sandbox to {tool} ({summary}) "
            f"&mdash; it failed: {obs}"
        )
    if kind == "protocol_error":
        return "The model&rsquo;s reply didn&rsquo;t parse and it was asked to retry."
    if kind == "final":
        obs = html.escape(_truncate(observation))
        return f"The agent&rsquo;s report: {obs}"
    # Unknown kinds: narrate generically, still escaped.
    label = html.escape(str(kind or "step"))
    obs = html.escape(_truncate(observation))
    return f"[{label}] {obs}" if obs else f"[{label}]"


def replay_page(record: dict) -> str:
    if record is None:
        body = """<h1>Replay</h1>
<p class="sub">Blast Radius Zero</p>
<p>No such run &mdash; there is no recorded run with that id, so there is
nothing to replay.</p>
<p><a href="/gauntlet">Back to the Gauntlet</a></p>
"""
        return _doc("Replay \u2014 Blast Radius Zero", body)

    task = html.escape(str(record.get("task") or ""))
    status = html.escape(str(record.get("status") or "unknown"))
    started = html.escape(str(record.get("started_at") or "unknown"))
    finished = html.escape(str(record.get("finished_at") or "not finished"))
    backend_line = (
        f"sandbox: {html.escape(str(record.get('sandbox_backend') or 'unknown'))}"
        f" &middot; inference: {html.escape(str(record.get('inference_backend') or 'unknown'))}"
        f" &middot; model: {html.escape(str(record.get('model') or 'unknown'))}"
    )
    answer = record.get("answer")
    error = record.get("error")

    steps = []
    for entry in record.get("transcript") or []:
        if isinstance(entry, dict):
            steps.append(f'<div class="step">{_narrate(entry)}</div>')
    steps_html = "\n".join(steps) if steps else '<div class="step">No transcript steps were recorded.</div>'

    if answer:
        final_html = (
            '<h2>Final answer</h2>\n'
            f'<div class="answer">{html.escape(str(answer))}</div>'
        )
    elif error:
        final_html = (
            '<h2>Final answer</h2>\n'
            f'<div class="answer">No answer &mdash; the run ended with an error: '
            f"{html.escape(str(error))}</div>"
        )
    else:
        final_html = (
            '<h2>Final answer</h2>\n'
            '<div class="answer">No final answer was recorded for this run.</div>'
        )

    body = f"""<h1>Replay</h1>
<p class="sub">Blast Radius Zero &mdash; one run, in plain English</p>
<p><span class="badge">status: {status}</span></p>
<h2>The instruction</h2>
<pre>{task}</pre>
<p>Started: {started} &middot; Finished: {finished}<br>{backend_line}</p>
<h2>What happened</h2>
{steps_html}
{final_html}
<p>Run status: <strong>{status}</strong></p>
<p><a href="/gauntlet">Back to the Gauntlet</a></p>
"""
    return _doc("Replay \u2014 Blast Radius Zero", body)
