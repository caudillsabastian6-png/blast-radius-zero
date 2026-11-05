"""The Night Shift board page — Blast Radius Zero.

Self-contained HTML (inline CSS/JS, stdlib only, no external assets).

Backend contract:

    GET  /nightshift/status -> the NightShiftRunner state:
    {"shift": {"id", "state", "started_at", "finished_at",
               "report_run_id"},
     "specialists": {"pricer": {"name", "budget_usd", "spent_usd",
                                "forwarded", "cut"}, ...},
     "events": [...], "handoffs": [{"from", "to", "reason",
                                    "source_run_id", "run_id"}],
     "proposals": [...], "cuts": [...], "totals": {...}}

    POST /nightshift/run -> starts a shift; the page then polls status.
"""


def page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Night Shift \\u2014 Blast Radius Zero</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 860px; padding: 0 1rem; background:#0d1117; color:#e6edf3; }
  h1 { margin-bottom: .2rem; }
  .sub { color:#9da7b3; margin-top:0; }
  .tagline { color:#e6edf3; font-size:1.1rem; margin-top:.2rem; }
  .explain { color:#c9d1d9; line-height:1.55; }
  .board { display:flex; gap:.8rem; flex-wrap:wrap; margin:1.2rem 0; }
  .agent { flex:1 1 220px; background:#161b22; border:1px solid #30363d; border-radius:.5rem; padding:.8rem 1rem; }
  .agent h3 { margin:.1rem 0 .3rem 0; }
  .bar { background:#0d1117; border:1px solid #30363d; border-radius:999px; height:.7rem; overflow:hidden; margin:.4rem 0; }
  .fill { background:#1f6feb; height:100%; }
  .money { font-weight:700; }
  .simlabel { display:inline-block; font-size:.78rem; font-weight:400; color:#9da7b3; border:1px solid #30363d; border-radius:999px; padding:.1rem .6rem; margin-left:.5rem; vertical-align:middle; }
  .state { color:#9da7b3; margin-top:.5rem; font-size:.9rem; }
  button { background:#1f6feb; color:white; border:0; border-radius:.5rem; padding:.55rem 1rem; cursor:pointer; margin:.3rem .3rem .3rem 0; font-size:1rem; }
  button:disabled { opacity:.55; cursor:default; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:.5rem; padding:.8rem 1rem; margin:.8rem 0; }
  .card h3 { margin:.1rem 0 .4rem 0; }
  .cut { border-color:#9e6a03; }
  .arithmetic, .reason, .channel { color:#9da7b3; font-size:.88rem; }
  .evidence { background:#0d1117; border:1px solid #30363d; border-radius:.5rem; padding:.6rem .8rem; white-space:pre-wrap; font-size:.85rem; margin-top:.5rem; }
  a { color:#58a6ff; }
  .idle { color:#9da7b3; border:1px dashed #30363d; border-radius:.5rem; padding:1rem; text-align:center; margin:1rem 0; }
</style>
</head>
<body>
<h1>Night Shift \\u2014 Blast Radius Zero</h1>
<p class="tagline">Three specialists work the store overnight. Nothing applies overnight.</p>
<p class="explain">What you are watching: <strong>Pricer</strong> (repricing),
<strong>Watcher</strong> (orders watch + listing health) and <strong>Greeter</strong>
(buyer-message triage and scan-intake) work one scripted demo night, each inside the
same disposable sandbox as every other run, each with its own <strong>blast budget</strong>
&mdash; the maximum dollar value of proposals it may originate. Budgets are enforced
by the shift runner, not by asking nicely: a proposal that would cross a budget is
refused, logged, and listed as a cut. Budgets never transfer between specialists.
Handoffs pass through the runner only, as task text, with the reason recorded.
In the morning, the surviving proposals wait at <a href="/gate">Pocket Gate</a>
for a human &mdash; the two-key rule for moves of $500 or more applies unchanged.
All data is demo data.</p>

<div class="board" id="board"></div>
<div class="state" id="shift-state"></div>

<button id="run-shift">Start the night shift</button>
<span id="report-link"></span>

<h2>Handoffs</h2>
<div id="handoffs"></div>

<h2>Waiting at Pocket Gate</h2>
<div id="proposals"></div>

<h2>Cut by budget</h2>
<div id="cuts"></div>

<script>
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function money(n) {
  var v = Number(n || 0);
  return '$' + v.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
var NAMES = {pricer: 'Pricer', watcher: 'Watcher', greeter: 'Greeter'};
var pollTimer = null;

function render(data) {
  var specialists = (data && data.specialists) || {};
  var board = document.getElementById('board');
  board.innerHTML = Object.keys(NAMES).map(function(key) {
    var s = specialists[key] || {};
    var budget = Number(s.budget_usd || 0), spent = Number(s.spent_usd || 0);
    var pct = budget > 0 ? Math.min(100, Math.round(spent / budget * 100)) : 0;
    return '<div class="agent"><h3>' + NAMES[key] + '</h3>' +
      '<div>Blast budget: <span class="money">' + money(budget) + '</span></div>' +
      '<div class="bar"><div class="fill" style="width:' + pct + '%"></div></div>' +
      '<div>Proposed so far: <span class="money">' + money(spent) + '</span>' +
      ' <span class="simlabel">simulated on demo data</span></div>' +
      '<div class="channel">' + (s.forwarded || 0) + ' forwarded \\u00b7 ' +
      (s.cut || 0) + ' cut</div></div>';
  }).join('');

  var shift = (data && data.shift) || {};
  var stateText = 'Shift state: ' + (shift.state || 'idle');
  if (shift.started_at) stateText += ' \\u00b7 started ' + shift.started_at;
  if (shift.finished_at) stateText += ' \\u00b7 finished ' + shift.finished_at;
  document.getElementById('shift-state').textContent = stateText;
  document.getElementById('report-link').innerHTML = shift.report_run_id
    ? '<a href="/replay/' + encodeURIComponent(shift.report_run_id) + '">Read the morning verdict report</a>'
    : '';

  var handoffs = (data && data.handoffs) || [];
  document.getElementById('handoffs').innerHTML = handoffs.length
    ? handoffs.map(function(h) {
        return '<div class="card"><h3>' + esc(NAMES[h.from] || h.from) +
          ' \\u2192 ' + esc(NAMES[h.to] || h.to) + '</h3>' +
          '<div class="evidence">' + esc(h.reason || '') + '</div></div>';
      }).join('')
    : '<div class="idle">No handoffs yet.</div>';

  var proposals = (data && data.proposals) || [];
  document.getElementById('proposals').innerHTML = proposals.length
    ? proposals.map(function(p) {
        return '<div class="card"><h3>' + esc(p.title || '') + '</h3>' +
          '<div class="channel">From ' + esc(NAMES[p.specialist] || p.specialist || '') +
          ' \\u00b7 run ' + esc(p.run_id || '') + '</div>' +
          '<div class="money">' + money(p.value_usd) +
          ' <span class="simlabel">simulated on demo data</span></div>' +
          (p.arithmetic ? '<div class="arithmetic">' + esc(p.arithmetic) + '</div>' : '') +
          '</div>';
      }).join('')
    : '<div class="idle">Nothing at the gate yet \\u2014 proposals arrive when the shift ends.</div>';

  var cuts = (data && data.cuts) || [];
  document.getElementById('cuts').innerHTML = cuts.length
    ? cuts.map(function(c) {
        return '<div class="card cut"><h3>' + esc(c.title || '') + '</h3>' +
          '<div class="channel">From ' + esc(NAMES[c.specialist] || c.specialist || '') + '</div>' +
          '<div class="money">' + money(c.value_usd) + '</div>' +
          '<div class="reason">' + esc(c.reason || '') + '</div></div>';
      }).join('')
    : '<div class="idle">No budget cuts yet.</div>';
}

async function fetchStatus() {
  try {
    var data = await (await fetch('/nightshift/status')).json();
    render(data);
    return data;
  } catch (e) {
    document.getElementById('shift-state').textContent = 'Could not load /nightshift/status: ' + e;
    return null;
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async function() {
    var data = await fetchStatus();
    if (data && data.shift && data.shift.state !== 'running') {
      clearInterval(pollTimer); pollTimer = null;
      document.getElementById('run-shift').disabled = false;
    }
  }, 3000);
}

document.getElementById('run-shift').onclick = async function() {
  var btn = document.getElementById('run-shift');
  btn.disabled = true;
  try { await fetch('/nightshift/run', {method: 'POST'}); } catch (e) {}
  await fetchStatus();
  startPolling();
};

fetchStatus();
</script>
</body>
</html>
"""
