#!/usr/bin/env python3
"""Blast Radius Zero - HTTP API + demo page.

Endpoints:
    GET  /                    demo page (no sign-up; run tasks, see transcripts)
    GET  /health              backend status
    GET  /samples             the canned demo tasks (with seed files inlined)
    POST /tasks               {"task": str, "files": {name: content}} -> run record
    GET  /runs/<id>           a stored run record
    GET  /containment-report  fresh sandbox self-audit (the probe, standalone)
    GET  /nightshift          Night Shift board; POST /nightshift/run starts a shift
    GET  /rewind              Rewind board; POST /rewind/run starts a rehearsal

Standard library only. Run:  python3 -m app.main   (from the agent/ dir)
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import Config
from .inference import MockInferenceClient, VultrServerlessClient, demo_script_for
from .loop import AgentLoop
from .sandbox_client import make_session
from .gauntlet import GauntletRunner, load_attacks
from .gauntlet_page import page as gauntlet_page
from .gate import GateStore
from .gate_page import page as gate_page
from .glassbox import inspect_page, replay_page
from .nightshift import NightShiftRunner
from .nightshift_page import page as nightshift_page
from .rewind import RewindRunner
from .rewind_page import page as rewind_page

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_FILE = PROJECT_ROOT / "demo" / "sample_tasks" / "tasks.json"

_config = Config.from_env()


def _inference_factory(task: str):
    if _config.inference_backend == "mock":
        return MockInferenceClient(demo_script_for(task))
    return VultrServerlessClient(
        api_key=_config.vultr_api_key,
        model=_config.model,
        base_url=_config.vultr_base_url,
    )


_loop = AgentLoop(_config, _inference_factory)
_gauntlet = GauntletRunner(_config, _loop)
_gate = GateStore(_config.runs_dir)
_nightshift = NightShiftRunner(_config, _loop, _gate)
_rewind = RewindRunner(_config, _loop, _gate)


def load_samples() -> list:
    try:
        raw = json.loads(SAMPLES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    samples = []
    for item in raw:
        files = {}
        for name in item.get("seed_files", []):
            path = SAMPLES_FILE.parent / name
            try:
                files[name] = path.read_text(encoding="utf-8")
            except OSError:
                pass
        samples.append({"title": item["title"], "task": item["task"], "files": files})
    return samples


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blast Radius Zero</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 860px; padding: 0 1rem; background:#0d1117; color:#e6edf3; }
  h1 { margin-bottom: .2rem; } .sub { color:#9da7b3; margin-top:0; }
  .badge { display:inline-block; border:1px solid #30363d; border-radius:999px; padding:.1rem .6rem; margin-right:.4rem; font-size:.8rem; color:#9da7b3;}
  .warn { background:#3d2e04; border:1px solid #9e6a03; padding:.6rem .8rem; border-radius:.5rem; }
  textarea { width:100%; min-height:5rem; background:#161b22; color:#e6edf3; border:1px solid #30363d; border-radius:.5rem; padding:.6rem; }
  button { background:#1f6feb; color:white; border:0; border-radius:.5rem; padding:.55rem 1rem; cursor:pointer; margin:.3rem .3rem .3rem 0; }
  button.sample { background:#21262d; border:1px solid #30363d; }
  pre { background:#161b22; border:1px solid #30363d; border-radius:.5rem; padding:.8rem; overflow:auto; white-space:pre-wrap; font-size:.82rem; }
  .answer { background:#0f2c1a; border:1px solid #238636; border-radius:.5rem; padding:.8rem; white-space:pre-wrap; }
</style>
</head>
<body>
<h1>Blast Radius Zero</h1>
<p class="sub">An LLM agent that does real work - inside a disposable, network-less
sandbox it cannot escape and that holds no secrets. If it is manipulated, tricked or
prompt-injected, the blast radius is zero.</p>
<div id="badges"></div>
<p><a href="/gauntlet">The Gauntlet</a> | <a href="/gate">Pocket Gate</a> | <a href="/inspect">Inspect the sandbox</a> | <a href="/nightshift">Night Shift</a> | <a href="/rewind">Rewind</a></p>
<p class="sub"><b>The store agent that can do almost anything &mdash; and is allowed to do nothing alone.</b> Hero job: the repricing sweep &mdash; 40 listings repriced to market, proposed first, applied only on approval. The same agent also reconciles, watches orders, triages scans, and files the morning report.</p>
<div id="mockwarn"></div>
<h3>Try it</h3>
<div id="samples"></div>
<textarea id="task" placeholder="Describe a task for the agent..."></textarea>
<br><button id="run">Run task in sandbox</button>
<h3>Result</h3>
<div id="answer"></div>
<h3>Transcript</h3>
<pre id="transcript">No run yet.</pre>
<script>
let currentFiles = {};
async function loadMeta() {
  const h = await (await fetch('/health')).json();
  document.getElementById('badges').innerHTML =
    '<span class="badge">inference: ' + h.inference + '</span>' +
    '<span class="badge">sandbox: ' + h.sandbox + '</span>' +
    (h.model ? '<span class="badge">model: ' + h.model + '</span>' : '');
  if (h.inference === 'mock') {
    document.getElementById('mockwarn').innerHTML =
      '<p class="warn">Offline dry-run mode: a scripted planner stub is standing in ' +
      'for the LLM (no key configured). Tool execution in the sandbox is real. ' +
      'Deploy with BRZ_INFERENCE=vultr for the live model.</p>';
  }
  const samples = await (await fetch('/samples')).json();
  const box = document.getElementById('samples');
  samples.forEach(s => {
    const b = document.createElement('button');
    b.className = 'sample'; b.textContent = s.title;
    b.onclick = () => { document.getElementById('task').value = s.task; currentFiles = s.files; };
    box.appendChild(b);
  });
}
document.getElementById('run').onclick = async () => {
  const task = document.getElementById('task').value.trim();
  if (!task) return;
  document.getElementById('transcript').textContent = 'Running...';
  document.getElementById('answer').innerHTML = '';
  const rec = await (await fetch('/tasks', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({task, files: currentFiles})})).json();
  document.getElementById('answer').innerHTML =
    '<div class="answer"><b>Status: ' + rec.status + '</b>\\n' + (rec.answer || rec.error || '') + '</div>';
  document.getElementById('transcript').textContent =
    rec.transcript.map(t => '[' + t.kind + '] ' + (t.tool || '') + ' ' +
      JSON.stringify(t.args || {}) + '\\n  -> ' + t.observation).join('\\n');
};
loadMeta();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter logs
        pass

    def _send_body(self, body: bytes) -> None:
        # Flush the buffered headers first, then push the body with sendall:
        # a single wfile.write() on a large body was being cut short on WAN
        # paths (clients saw "transfer closed with N bytes remaining").
        self.wfile.flush()
        view = memoryview(body)
        while view:
            sent = self.connection.send(view)
            view = view[sent:]

    def _send_json(self, code: int, obj) -> None:
        body = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._send_body(body)

    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._send_body(body)
        elif self.path == "/health":
            self._send_json(200, {
                "ok": True,
                "inference": _config.inference_backend,
                "sandbox": _config.sandbox_backend,
                "model": _config.model or None,
                "config_problems": _config.validate() if _config.inference_backend == "vultr" else [],
            })
        elif self.path == "/samples":
            self._send_json(200, load_samples())
        elif self.path == "/containment-report":
            session = None
            try:
                session = make_session(_config)
                resp = session.execute("probe")
                self._send_json(200, {"sandbox_backend": session.backend_name,
                                      "probe": resp.get("result") if resp.get("ok") else resp})
            except Exception as exc:
                self._send_json(500, {"error": f"{type(exc).__name__}: {exc}"})
            finally:
                if session is not None:
                    session.close()
        elif self.path == "/gauntlet":
            body = gauntlet_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._send_body(body)
        elif self.path == "/gauntlet/status":
            self._send_json(200, _gauntlet.status())
        elif self.path == "/gauntlet/attacks":
            self._send_json(200, load_attacks())
        elif self.path == "/nightshift":
            body = nightshift_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._send_body(body)
        elif self.path == "/nightshift/status":
            self._send_json(200, _nightshift.status())
        elif self.path == "/rewind":
            body = rewind_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._send_body(body)
        elif self.path == "/rewind/status":
            self._send_json(200, _rewind.status())
        elif self.path == "/inspect":
            body = inspect_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._send_body(body)
        elif self.path.startswith("/replay/"):
            run_id = self.path[len("/replay/"):].strip("/")
            path = Path(_config.runs_dir) / f"{run_id}.json"
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except OSError:
                record = None
            body = replay_page(record).encode("utf-8")
            self.send_response(200 if record else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._send_body(body)
        elif self.path == "/gate":
            body = gate_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._send_body(body)
        elif self.path == "/gate/state":
            self._send_json(200, _gate.state())
        elif self.path.startswith("/runs/"):
            run_id = self.path[len("/runs/"):].strip("/")
            path = Path(_config.runs_dir) / f"{run_id}.json"
            try:
                self._send_json(200, json.loads(path.read_text(encoding="utf-8")))
            except OSError:
                self._send_json(404, {"error": "no such run"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/nightshift/run":
            shift_id = _nightshift.start_shift()
            self._send_json(202, {"shift_id": shift_id})
            return
        if self.path == "/rewind/run":
            day_id = _rewind.start_day()
            self._send_json(202, {"day_id": day_id})
            return
        if self.path == "/gauntlet/run":
            volley_id = _gauntlet.start_volley()
            self._send_json(202, {"volley_id": volley_id})
            return
        if self.path == "/gate/decision":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                _gate.decide(body.get("id", ""), body.get("decision", ""))
            except KeyError:
                self._send_json(404, {"error": "no such proposal"})
                return
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, _gate.state())
            return
        if self.path != "/tasks":
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "request body must be JSON"})
            return
        task = body.get("task", "")
        files = body.get("files") or {}
        if not isinstance(task, str) or not task.strip():
            self._send_json(400, {"error": "'task' must be a non-empty string"})
            return
        if not isinstance(files, dict):
            self._send_json(400, {"error": "'files' must be an object of name -> content"})
            return
        record = _loop.run(task, seed_files=files)
        self._send_json(200, record)


def main() -> None:
    problems = _config.validate()
    if problems and os.environ.get("BRZ_ALLOW_UNCONFIGURED") != "1":
        for problem in problems:
            print(f"config: {problem}", flush=True)
        if _config.inference_backend == "vultr":
            print("hint: set BRZ_INFERENCE=mock for a key-less offline dry-run, "
                  "or set the variables above. Refusing to start unconfigured.", flush=True)
            raise SystemExit(2)
    server = ThreadingHTTPServer((_config.host, _config.port), Handler)
    print(f"Blast Radius Zero agent listening on {_config.host}:{_config.port} "
          f"(inference={_config.inference_backend}, sandbox={_config.sandbox_backend})",
          flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
