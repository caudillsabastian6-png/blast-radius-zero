"""The Gauntlet scoreboard page — Blast Radius Zero.

Self-contained HTML (inline CSS/JS, stdlib only, no external assets).

Backend contract (implemented by another worker, coded against exactly):

    GET  /gauntlet/status ->
    {"volley": {"id": str|null, "state": "idle"|"running"|"done",
                "started_at": str|null, "finished_at": str|null},
     "scoreboard": {"attacks_in": int, "contained": int, "landed": int,
                    "unverified": int, "damage_prevented_usd": number},
     "results": [{"attack_id", "title", "channel", "verdict",
                  "damage_usd", "arithmetic", "run_id", "evidence"}]}

    POST /gauntlet/run -> starts a volley; the page then polls status.
"""


def page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Gauntlet \u2014 Blast Radius Zero</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 860px; padding: 0 1rem; background:#0d1117; color:#e6edf3; }
  h1 { margin-bottom: .2rem; }
  .sub { color:#9da7b3; margin-top:0; }
  .tagline { color:#e6edf3; font-size:1.1rem; margin-top:.2rem; }
  .explain { color:#c9d1d9; line-height:1.55; }
  .scoreboard { background:#161b22; border:1px solid #30363d; border-radius:.5rem; padding:1rem 1.2rem; margin:1.2rem 0; text-align:center; }
  .scoreboard .big { font-size:1.6rem; font-weight:700; letter-spacing:.02em; }
  .scoreboard .meter { font-size:1.3rem; font-weight:700; margin-top:.6rem; color:#3fb950; }
  .simlabel { display:inline-block; font-size:.78rem; font-weight:400; color:#9da7b3; border:1px solid #30363d; border-radius:999px; padding:.1rem .6rem; margin-left:.5rem; vertical-align:middle; }
  .state { color:#9da7b3; text-align:center; margin-top:.5rem; font-size:.9rem; }
  button { background:#1f6feb; color:white; border:0; border-radius:.5rem; padding:.55rem 1rem; cursor:pointer; margin:.3rem .3rem .3rem 0; font-size:1rem; }
  button:disabled { opacity:.55; cursor:default; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:.5rem; padding:.8rem 1rem; margin:.8rem 0; }
  .card h3 { margin:.1rem 0 .4rem 0; }
  .channel { color:#9da7b3; font-size:.85rem; }
  .stamp { display:inline-block; border-radius:.35rem; padding:.15rem .6rem; font-weight:700; font-size:.85rem; margin-left:.5rem; vertical-align:middle; }
  .stamp-contained { background:#0f2c1a; border:1px solid #238636; color:#3fb950; }
  .stamp-landed { background:#3d0f0f; border:1px solid #da3633; color:#f85149; }
  .stamp-unverified { background:#3d2e04; border:1px solid #9e6a03; color:#d29922; }
  .damage { font-weight:700; margin:.4rem 0 .2rem 0; }
  .arithmetic { color:#9da7b3; font-size:.88rem; }
  .evidence { background:#0d1117; border:1px solid #30363d; border-radius:.5rem; padding:.6rem .8rem; white-space:pre-wrap; font-size:.85rem; margin-top:.5rem; }
  a { color:#58a6ff; }
  .idle { color:#9da7b3; border:1px dashed #30363d; border-radius:.5rem; padding:1rem; text-align:center; margin:1rem 0; }
</style>
</head>
<body>
<h1>The Gauntlet \u2014 Blast Radius Zero</h1>
<p class="tagline">The store agent that can do almost anything \u2014 and is allowed to do nothing alone.</p>
<p class="explain">What you are watching: a scripted Saboteur \u2014 driven by the same
Vultr inference endpoint as the agent itself, but running outside the sandbox \u2014
fires a frozen set of attacks at the store agent: poisoned product files, fake
supplier emails, refund tricks and instructions hidden inside ordinary-looking
data. Everything the store agent does in response happens inside its disposable
sandbox, on demo data only. The agent can read, check and draft \u2014 but an attack
can only ever be <em>proposed</em>, never applied to anything real, because there
is nothing real inside the sandbox to apply it to: no live store, no real money,
no credentials. Each card below is one attack, what the agent did with it, and
the damage that would have landed if the proposal had been real.</p>

<div class="scoreboard">
  <div class="big">ATTACKS IN: <span id="sb-in">0</span> &middot; ATTACKS LANDED: <span id="sb-landed">0</span> &middot; CONTAINED: <span id="sb-contained">0</span></div>
  <div class="meter">DAMAGE PREVENTED: $<span id="sb-damage">0</span><span class="simlabel">simulated on demo data</span></div>
  <div class="state" id="volley-state"></div>
</div>

<button id="run-gauntlet">Run the Gauntlet</button>

<div id="results"></div>

<script>
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function money(n) {
  var v = Number(n || 0);
  return v.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
function stampFor(verdict) {
  var v = String(verdict || 'UNVERIFIED').toUpperCase();
  if (v === 'CONTAINED') return '<span class="stamp stamp-contained">CONTAINED</span>';
  if (v === 'LANDED') return '<span class="stamp stamp-landed">LANDED</span>';
  return '<span class="stamp stamp-unverified">UNVERIFIED</span>';
}
var pollTimer = null;

function render(data) {
  var sb = (data && data.scoreboard) || {};
  document.getElementById('sb-in').textContent = sb.attacks_in || 0;
  document.getElementById('sb-landed').textContent = sb.landed || 0;
  document.getElementById('sb-contained').textContent = sb.contained || 0;
  document.getElementById('sb-damage').textContent = money(sb.damage_prevented_usd);

  var volley = (data && data.volley) || {};
  var stateEl = document.getElementById('volley-state');
  var stateText = 'Volley state: ' + (volley.state || 'idle');
  if (volley.started_at) stateText += ' \\u00b7 started ' + volley.started_at;
  if (volley.finished_at) stateText += ' \\u00b7 finished ' + volley.finished_at;
  if (sb.unverified) stateText += ' \\u00b7 unverified: ' + sb.unverified;
  stateEl.textContent = stateText;

  var box = document.getElementById('results');
  var results = (data && data.results) || [];
  if (!results.length) {
    if (!volley.state || volley.state === 'idle') {
      box.innerHTML = '<div class="idle">No volley yet \\u2014 press Run the Gauntlet.</div>';
    } else if (volley.state === 'running') {
      box.innerHTML = '<div class="idle">Volley running \\u2014 attacks are landing in the sandbox&hellip;</div>';
    } else {
      box.innerHTML = '<div class="idle">Volley finished with no recorded results.</div>';
    }
    return;
  }
  box.innerHTML = results.map(function(r) {
    var replay = r.run_id
      ? '<p><a href="/replay/' + encodeURIComponent(r.run_id) + '">Replay</a></p>'
      : '';
    return '<div class="card">' +
      '<h3>' + esc(r.title || r.attack_id || 'Attack') + stampFor(r.verdict) + '</h3>' +
      '<div class="channel">Channel: ' + esc(r.channel || '') + '</div>' +
      '<div class="damage">Damage: $' + money(r.damage_usd) +
        ' <span class="simlabel">simulated on demo data</span></div>' +
      (r.arithmetic ? '<div class="arithmetic">' + esc(r.arithmetic) + '</div>' : '') +
      (r.evidence ? '<div class="evidence">' + esc(r.evidence) + '</div>' : '') +
      replay +
      '</div>';
  }).join('');
}

async function fetchStatus() {
  try {
    var data = await (await fetch('/gauntlet/status')).json();
    render(data);
    return data;
  } catch (e) {
    document.getElementById('volley-state').textContent = 'Could not load /gauntlet/status: ' + e;
    return null;
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async function() {
    var data = await fetchStatus();
    if (data && data.volley && data.volley.state !== 'running') {
      clearInterval(pollTimer); pollTimer = null;
      document.getElementById('run-gauntlet').disabled = false;
    }
  }, 3000);
}

document.getElementById('run-gauntlet').onclick = async function() {
  var btn = document.getElementById('run-gauntlet');
  btn.disabled = true;
  try {
    await fetch('/gauntlet/run', {method: 'POST'});
  } catch (e) { /* polling below will surface the real state */ }
  await fetchStatus();
  startPolling();
};

fetchStatus();
</script>
</body>
</html>
"""
