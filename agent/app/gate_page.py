"""Pocket Gate page — phone-first HTML for Blast Radius Zero.

Exposes ``page() -> str``. The page is rendered client-side from
``GET /gate/state`` and posts decisions to ``POST /gate/decision``.
All proposals are demo data; approving one here applies nothing to any
real store. Standard library only (this module just returns a string).
"""


def page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pocket Gate — Blast Radius Zero</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: system-ui, sans-serif; margin: 0 auto; max-width: 480px; padding: 1rem; background:#0d1117; color:#e6edf3; }
  h1 { font-size: 1.4rem; margin: .4rem 0 .2rem; }
  .sub { color:#9da7b3; margin: 0 0 1rem; line-height: 1.45; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:.75rem; padding:1rem; margin-bottom:1rem; }
  .card h2 { font-size: 1.05rem; margin: 0 0 .4rem; line-height: 1.35; }
  .detail { color:#c9d1d9; line-height: 1.5; margin: 0 0 .6rem; }
  .value { font-size: 1.1rem; font-weight: 700; margin: 0 0 .6rem; }
  .stamp { display:inline-block; border-radius:999px; padding:.2rem .7rem; font-size:.8rem; font-weight:700; letter-spacing:.03em; margin-bottom:.8rem; border:1px solid #30363d; }
  .stamp-pending { background:#21262d; color:#9da7b3; }
  .stamp-awaiting_second_key { background:#3d2e04; color:#f0b72f; border-color:#9e6a03; }
  .stamp-approved { background:#0f2c1a; color:#3fb950; border-color:#238636; }
  .stamp-rejected { background:#3d0f0f; color:#f85149; border-color:#da3633; }
  .buttons { display:flex; flex-wrap:wrap; gap:.5rem; }
  button { min-height:48px; min-width:48px; padding:.7rem 1.1rem; font-size:1rem; border-radius:.5rem; border:0; cursor:pointer; flex:1 1 auto; }
  button.approve { background:#1f6feb; color:#fff; }
  button.reject { background:#21262d; color:#f85149; border:1px solid #da3633; }
  button.undo { background:#21262d; color:#e6edf3; border:1px solid #30363d; }
  button:active { opacity:.85; }
  .empty, .error { color:#9da7b3; }
  .error { color:#f85149; }
  footer { color:#9da7b3; font-size:.85rem; line-height:1.5; border-top:1px solid #30363d; padding-top:.8rem; margin-top:1.2rem; }
</style>
</head>
<body>
<h1>Pocket Gate — Blast Radius Zero</h1>
<p class="sub">This is the human gate for the agent's proposed moves: nothing the agent proposes is applied until you approve it here. Moves of $500 or more need two separate approvals.</p>
<div id="proposals"><p class="empty">Loading proposals…</p></div>
<footer>Demo data. Approving a proposal here applies nothing to any real store — that is the point of the gate.</footer>
<script>
var STAMPS = {
  pending: ['PENDING', 'stamp-pending'],
  awaiting_second_key: ['AWAITING SECOND KEY', 'stamp-awaiting_second_key'],
  approved: ['APPROVED', 'stamp-approved'],
  rejected: ['REJECTED', 'stamp-rejected']
};
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}
function money(v) { return '$' + Number(v).toFixed(2); }
function render(state) {
  var box = document.getElementById('proposals');
  box.innerHTML = '';
  (state.proposals || []).forEach(function (p) {
    var stamp = STAMPS[p.status] || STAMPS.pending;
    var decided = (p.status === 'approved' || p.status === 'rejected');
    var card = document.createElement('div');
    card.className = 'card';
    var html = '<h2>' + esc(p.title) + '</h2>' +
      '<p class="detail">' + esc(p.detail) + '</p>' +
      '<p class="value">' + money(p.value_usd) + ' (demo)</p>' +
      '<span class="stamp ' + stamp[1] + '">' + stamp[0] + '</span>' +
      '<div class="buttons">';
    if (!decided) {
      var approveLabel = (p.status === 'awaiting_second_key') ? 'Second key — approve' : 'Approve';
      html += '<button class="approve" data-id="' + esc(p.id) + '" data-decision="approve">' + approveLabel + '</button>';
      html += '<button class="reject" data-id="' + esc(p.id) + '" data-decision="reject">Reject</button>';
    }
    if (decided || p.status === 'awaiting_second_key') {
      html += '<button class="undo" data-id="' + esc(p.id) + '" data-decision="undo">Undo</button>';
    }
    html += '</div>';
    card.innerHTML = html;
    box.appendChild(card);
  });
  box.querySelectorAll('button').forEach(function (b) {
    b.onclick = function () { decide(b.getAttribute('data-id'), b.getAttribute('data-decision')); };
  });
}
async function refresh() {
  try {
    var state = await (await fetch('/gate/state')).json();
    render(state);
  } catch (e) {
    document.getElementById('proposals').innerHTML = '<p class="error">Could not load proposals.</p>';
  }
}
async function decide(id, decision) {
  try {
    var resp = await (await fetch('/gate/decision', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id: id, decision: decision})})).json();
    if (resp && resp.proposals) { render(resp); } else { await refresh(); }
  } catch (e) { await refresh(); }
}
refresh();
</script>
</body>
</html>
"""
