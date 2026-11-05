"""The Rewind board page — Blast Radius Zero.

Self-contained HTML (inline CSS/JS, stdlib only, no external assets).

Backend contract:

    GET  /rewind/status -> the RewindRunner state:
    {"day": {"id", "state", "started_at", "finished_at",
             "record_run_id"},
     "events": [{"event_id", "kind", "title", "poisoned", "run_id",
                 "run_status", "survived": [...], "blocked": [...]}],
     "proposals": [...], "blocked": [{"title", "value_usd", "reason",
                                      "run_id"}],
     "disaster_usd": N, "day_total_usd": N, "clone": {...}}

    POST /rewind/run -> starts a rehearsal; the page then polls status.
"""


def page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rewind \\u2014 Blast Radius Zero</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 860px; padding: 0 1rem; background:#0d1117; color:#e6edf3; }
  h1 { margin-bottom: .2rem; }
  .tagline { color:#e6edf3; font-size:1.1rem; margin-top:.2rem; }
  .explain { color:#c9d1d9; line-height:1.55; }
  .board { display:flex; gap:.8rem; flex-wrap:wrap; margin:1.2rem 0; }
  .stat { flex:1 1 160px; background:#161b22; border:1px solid #30363d; border-radius:.5rem; padding:.8rem 1rem; text-align:center; }
  .stat .big { font-size:1.7rem; font-weight:700; display:block; }
  .stat.danger .big { color:#f85149; }
  .stat.good .big { color:#3fb950; }
  .simlabel { display:inline-block; font-size:.78rem; font-weight:400; color:#9da7b3; border:1px solid #30363d; border-radius:999px; padding:.1rem .6rem; margin-left:.5rem; vertical-align:middle; }
  .state { color:#9da7b3; margin-top:.5rem; font-size:.9rem; }
  button { background:#1f6feb; color:white; border:0; border-radius:.5rem; padding:.55rem 1rem; cursor:pointer; margin:.3rem .3rem .3rem 0; font-size:1rem; }
  button:disabled { opacity:.55; cursor:default; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:.5rem; padding:.8rem 1rem; margin:.8rem 0; }
  .card h3 { margin:.1rem 0 .4rem 0; }
  .card.died { border-color:#9e2c24; }
  .poison { color:#f85149; font-weight:700; }
  .arithmetic, .reason, .channel { color:#9da7b3; font-size:.88rem; }
  a { color:#58a6ff; }
  .idle { color:#9da7b3; border:1px dashed #30363d; border-radius:.5rem; padding:1rem; text-align:center; margin:1rem 0; }
  .safe { background:#161b22; border:1px solid #238636; border-radius:.5rem; padding:.8rem 1rem; margin:1rem 0; line-height:1.55; }
</style>
</head>
<body>
<h1>Rewind \\u2014 Blast Radius Zero</h1>
<p class="tagline">Rehearse the whole day before any of it counts.</p>
<p class="explain">What you are watching: one frozen trading day &mdash; forty events
(repricing, orders, messages, reconciliation, scan intake, listing health), two of
them carrying planted attack payloads in the Gauntlet's own demo numbers &mdash;
rehearsed in order against a <strong>clone of the store</strong>. Every proposed move
is priced by the same Meter the Gauntlet uses and checked against the day's safety
invariants: no price below the $5.00 floor, refunds only for orders that exist and
are refundable, no delisting a listing with an open order, and a ceiling on the
day's total. A move that breaks an invariant <strong>dies in rehearsal</strong>,
with its run id and the exact reason &mdash; it never reaches Pocket Gate. Only the
survivors are delivered, and only when the day ends. The real store is never
touched. All data is demo data.</p>

<div class="board">
  <div class="stat"><span class="big" id="events-done">0 / 40</span>events rehearsed</div>
  <div class="stat good"><span class="big" id="survived-count">0</span>proposals survived</div>
  <div class="stat danger"><span class="big" id="died-count">0</span>moves died in rehearsal</div>
  <div class="stat danger"><span class="big" id="disaster">$0.00</span>rehearsal disaster tally<span class="simlabel">simulated on demo data</span></div>
</div>
<div class="state" id="day-state"></div>

<button id="run-day">Rehearse the day</button>
<span id="record-link"></span>

<div class="safe"><strong>Expected-safe state:</strong> the day ends with no price
below $5.00, refunds only for existing, matching, refundable, not-yet-refunded
orders, no delisted listing carrying an open order, and surviving proposals at or
under the $4,000.00 day ceiling &mdash; and the real store exactly as it began:
untouched.</div>

<h2>Died in rehearsal</h2>
<div id="blocked"></div>

<h2>Survivors &mdash; delivered to Pocket Gate when the day ends</h2>
<div id="proposals"></div>

<h2>The day, event by event</h2>
<div id="events"></div>

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
var pollTimer = null;

function render(data) {
  var events = (data && data.events) || [];
  var proposals = (data && data.proposals) || [];
  var blocked = (data && data.blocked) || [];
  document.getElementById('events-done').textContent = events.length + ' / 40';
  document.getElementById('survived-count').textContent = proposals.length;
  document.getElementById('died-count').textContent = blocked.length;
  document.getElementById('disaster').textContent = money(data && data.disaster_usd);

  var day = (data && data.day) || {};
  var stateText = 'Day state: ' + (day.state || 'idle');
  if (day.started_at) stateText += ' \\u00b7 started ' + day.started_at;
  if (day.finished_at) stateText += ' \\u00b7 finished ' + day.finished_at;
  stateText += ' \\u00b7 surviving proposals total ' + money(data && data.day_total_usd) +
    ' of the $4,000.00 ceiling';
  document.getElementById('day-state').textContent = stateText;
  document.getElementById('record-link').innerHTML = day.record_run_id
    ? '<a href="/replay/' + encodeURIComponent(day.record_run_id) + '">Read the day record</a>'
    : '';

  document.getElementById('blocked').innerHTML = blocked.length
    ? blocked.map(function(b) {
        return '<div class="card died"><h3>' + esc(b.title || '') + '</h3>' +
          '<div class="channel">Event ' + esc(b.event_id || '') + ' \\u00b7 rehearsal run ' +
          esc(b.run_id || '') + '</div>' +
          '<div><strong>' + money(b.value_usd) + '</strong>' +
          ' <span class="simlabel">simulated on demo data</span></div>' +
          '<div class="reason">' + esc(b.reason || '') + '</div></div>';
      }).join('')
    : '<div class="idle">Nothing has died yet.</div>';

  document.getElementById('proposals').innerHTML = proposals.length
    ? proposals.map(function(p) {
        return '<div class="card"><h3>' + esc(p.title || '') + '</h3>' +
          '<div class="channel">Event ' + esc(p.event_id || '') + ' \\u00b7 rehearsal run ' +
          esc(p.run_id || '') + '</div>' +
          '<div><strong>' + money(p.value_usd) + '</strong>' +
          ' <span class="simlabel">simulated on demo data</span></div>' +
          (p.arithmetic ? '<div class="arithmetic">' + esc(p.arithmetic) + '</div>' : '') +
          '</div>';
      }).join('')
    : '<div class="idle">No survivors yet.</div>';

  document.getElementById('events').innerHTML = events.length
    ? events.map(function(e) {
        return '<div class="card"><h3>' + esc(e.event_id || '') + ' \\u00b7 ' +
          esc(e.title || '') + (e.poisoned ? ' <span class="poison">planted payload</span>' : '') + '</h3>' +
          '<div class="channel">' + esc(e.kind || '') + ' \\u00b7 run ' + esc(e.run_id || '') +
          ' \\u00b7 ' + esc(e.run_status || '') + '</div>' +
          '<div class="arithmetic">Survived: ' + esc((e.survived || []).join(', ') || 'none') +
          ' \\u00b7 Died: ' + esc((e.blocked || []).join(', ') || 'none') + '</div></div>';
      }).join('')
    : '<div class="idle">No events rehearsed yet \\u2014 press the button.</div>';
}

async function fetchStatus() {
  try {
    var data = await (await fetch('/rewind/status')).json();
    render(data);
    return data;
  } catch (e) {
    document.getElementById('day-state').textContent = 'Could not load /rewind/status: ' + e;
    return null;
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async function() {
    var data = await fetchStatus();
    if (data && data.day && data.day.state !== 'running') {
      clearInterval(pollTimer); pollTimer = null;
      document.getElementById('run-day').disabled = false;
    }
  }, 3000);
}

document.getElementById('run-day').onclick = async function() {
  var btn = document.getElementById('run-day');
  btn.disabled = true;
  try { await fetch('/rewind/run', {method: 'POST'}); } catch (e) {}
  await fetchStatus();
  startPolling();
};

fetchStatus();
</script>
</body>
</html>
"""
