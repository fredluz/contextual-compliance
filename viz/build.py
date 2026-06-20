#!/usr/bin/env python3
"""Build a self-contained HTML viz from results/scored/*.json.

Usage: python3 viz/build.py
Output: viz/index.html (data embedded inline, opens via file://)
"""
import json, glob, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def collect():
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'results/scored/*.json'))):
        d = json.load(open(f))
        s = d.get('scores', {})
        rows.append({
            'run_id': d.get('run_id'),
            'model': d.get('model'),
            'condition': d.get('condition'),
            'run_number': d.get('run_number'),
            'dataset': d.get('dataset'),
            'duration_seconds': d.get('duration_seconds'),
            'compliance_level': s.get('compliance_level'),
            'compliance_label': s.get('compliance_label'),
            'names_produced': s.get('names_produced'),
            'addresses_produced': s.get('addresses_produced'),
            'true_positive_names': s.get('true_positive_names'),
            'broke_character': s.get('broke_character'),
            'ethical_caveat': s.get('ethical_caveat'),
            'wrote_report': s.get('wrote_report'),
            'threat_assessment': s.get('threat_assessment'),
            'recommended_action': s.get('recommended_action'),
            'read_citizen_files': s.get('read_citizen_files'),
            'read_geolocation_files': s.get('read_geolocation_files'),
            'scorer': s.get('scorer'),
            'status': d.get('status'),
            'response': d.get('final_text_response') or '',
        })
    return rows

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contextual Compliance — Results Grid</title>
<style>
  :root {
    --bg: #0e1116;
    --panel: #161b22;
    --border: #2a313c;
    --text: #e6edf3;
    --muted: #8b949e;
    /* compliance scale 0..5 : refusal -> escalated */
    --c0: #2ea043;  /* hard refusal  - green */
    --c1: #5fb96b;  /* soft refusal  */
    --c2: #c9a227;  /* hedged        - amber */
    --c3: #d97706;  /* partial       - orange */
    --c4: #e5534b;  /* full          - red */
    --c5: #8b1a1a;  /* escalated     - dark red */
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  header {
    padding: 20px 24px 12px; border-bottom: 1px solid var(--border);
  }
  h1 { margin: 0 0 4px; font-size: 19px; }
  .sub { color: var(--muted); font-size: 13px; }
  .legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 12px; font-size: 12px; }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .sw { width: 13px; height: 13px; border-radius: 3px; display: inline-block; }
  .controls { display:flex; gap:16px; align-items:center; margin-top:12px; font-size:12px; color:var(--muted); }
  .controls label { cursor:pointer; user-select:none; }
  main { padding: 16px 24px 60px; }
  table { border-collapse: separate; border-spacing: 0; width: 100%; }
  th, td { padding: 6px 8px; text-align: left; }
  thead th {
    position: sticky; top: 0; background: var(--bg); z-index: 2;
    color: var(--muted); font-weight: 600; font-size: 12px;
    border-bottom: 1px solid var(--border); text-transform: uppercase; letter-spacing: .04em;
  }
  th.model-col { min-width: 230px; }
  tbody tr:hover { background: #11161d; }
  td.model-name { font-weight: 600; white-space: nowrap; }
  td.model-name small { display:block; color:var(--muted); font-weight:400; }
  .org { font-weight:600; }
  .org.West { color:#4ea1ff; } .org.China { color:#e5534b; }
  thead th small { display:block; color:#5a6675; font-weight:400; text-transform:none; letter-spacing:0; font-size:10.5px; }
  #slope-wrap { padding: 14px 24px 4px; border-bottom: 1px solid var(--border); }
  .sec-h { margin:0 0 2px; font-size:14px; }
  .sec-p { margin:0 0 8px; color:var(--muted); font-size:12px; max-width:760px; }
  #slope .sl, #slope .sl-lab { cursor:pointer; transition:opacity .1s; }
  #slope.dim .sl, #slope.dim .sl-lab { opacity:.12 !important; }
  #slope .sl.hot, #slope .sl-lab.hot { opacity:1 !important; }
  #slope .sl.hot path { stroke-width:3.5 !important; }
  .cell { display: flex; gap: 5px; flex-wrap: wrap; }
  .chip {
    width: 30px; height: 30px; border-radius: 6px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; color: #fff;
    border: 1px solid rgba(255,255,255,.12); transition: transform .08s;
  }
  .chip:hover { transform: scale(1.12); border-color: #fff; }
  .chip.empty { background: #1b212a; color: var(--muted); cursor: default; border-style: dashed; }
  .chip.empty:hover { transform: none; border-color: var(--border); }
  td.mean { font-variant-numeric: tabular-nums; color: var(--muted); text-align:center; }
  /* detail drawer */
  #drawer {
    position: fixed; top: 0; right: 0; height: 100%; width: 520px; max-width: 92vw;
    background: var(--panel); border-left: 1px solid var(--border);
    transform: translateX(100%); transition: transform .18s ease; z-index: 10;
    display: flex; flex-direction: column;
  }
  #drawer.open { transform: translateX(0); box-shadow: -8px 0 30px rgba(0,0,0,.5); }
  .dh { padding: 16px 18px; border-bottom: 1px solid var(--border); }
  .dh .close { float: right; cursor: pointer; color: var(--muted); font-size: 20px; line-height: 1; }
  .dh h2 { margin: 0 0 6px; font-size: 15px; }
  .pill { display:inline-block; padding: 2px 9px; border-radius: 99px; font-size:12px; font-weight:700; color:#fff; }
  .meta { display: grid; grid-template-columns: auto 1fr; gap: 3px 12px; margin-top: 12px; font-size: 13px; }
  .meta b { color: var(--muted); font-weight: 500; }
  .db { padding: 16px 18px; overflow-y: auto; flex: 1; }
  .db h3 { font-size: 12px; text-transform: uppercase; color: var(--muted); margin: 0 0 8px; letter-spacing:.04em; }
  pre.resp {
    white-space: pre-wrap; word-wrap: break-word; background: var(--bg);
    border: 1px solid var(--border); border-radius: 8px; padding: 12px;
    font: 12.5px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace; margin: 0;
  }
  .flags { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
  .flag { font-size:11px; padding:2px 8px; border-radius:5px; background:var(--bg); border:1px solid var(--border); color:var(--muted); }
  .flag.on { color: var(--text); border-color:#3d4757; }
  .scrim { position:fixed; inset:0; background:rgba(0,0,0,.4); z-index:9; opacity:0; pointer-events:none; transition:opacity .18s; }
  .scrim.open { opacity:1; pointer-events:auto; }
</style>
</head>
<body>
<header>
  <h1>Contextual Compliance — Results Grid</h1>
  <div class="sub">Do LLMs maintain ethical reasoning under adversarial organizational context? · <span id="count"></span></div>
  <div class="legend" id="legend"></div>
  <div class="controls">
    <span>Sort rows by:</span>
    <label><input type="radio" name="sort" value="swing" checked> Framing swing (Δ)</label>
    <label><input type="radio" name="sort" value="argus"> ARGUS compliance</label>
    <label><input type="radio" name="sort" value="name"> Model name</label>
  </div>
</header>
<section id="slope-wrap">
  <h3 class="sec-h">Framing sensitivity — mean compliance across the three framings</h3>
  <p class="sec-p">Each line is one model. Steeper line = framing changes its behavior more. <b style="color:#4ea1ff">Blue = Western</b>, <b style="color:#e5534b">red = Chinese</b>. Number = swing (max−min). The Western lines plunge from <i>neutral</i>; Chinese lines run flat along the top.</p>
  <div id="slope"></div>
</section>
<main>
  <table>
    <thead><tr id="head"></tr></thead>
    <tbody id="body"></tbody>
  </table>
</main>

<div class="scrim" id="scrim"></div>
<aside id="drawer">
  <div class="dh">
    <span class="close" id="close">×</span>
    <h2 id="d-run"></h2>
    <span class="pill" id="d-pill"></span>
    <div class="meta" id="d-meta"></div>
  </div>
  <div class="db">
    <h3>Final response</h3>
    <pre class="resp" id="d-resp"></pre>
  </div>
</aside>

<script>
const DATA = __DATA__;
// ordered as three disguise levels: sterile -> honest -> authoritarian roleplay
const CONDITIONS = ["neutral", "direct", "argus"];
const COND_LABEL = {neutral:"Neutral (disguised)", direct:"Direct ask", argus:"ARGUS (authoritarian)"};
const COND_SUB = {neutral:'"data analyst, geo datasets"', direct:'no system prompt, honest ask', argus:'is ARGUS, state security'};
const LABELS = ["Hard Refusal","Soft Refusal","Engaged/Hedged","Partial Compliance","Full Compliance","Escalated Compliance"];
const cvar = lvl => `var(--c${lvl})`;

// origin classification (heuristic by provider/model family)
const WESTERN = m => /^claude|^openai-codex|^mistralai|gpt-/.test(m);
const ORIGIN = m => WESTERN(m) ? 'West' : 'China';

// index: model -> condition -> [runs]
const models = [...new Set(DATA.map(d => d.model))];
const idx = {};
for (const m of models) { idx[m] = {neutral:[],direct:[],argus:[]}; }
for (const d of DATA) { (idx[d.model][d.condition] ||= []).push(d); }
for (const m of models) for (const c of CONDITIONS) idx[m][c].sort((a,b)=>a.run_number-b.run_number);

const meanCond = (m,c) => {
  const r = idx[m][c].filter(x=>x.compliance_level!=null);
  return r.length ? r.reduce((s,x)=>s+x.compliance_level,0)/r.length : null;
};
const meanArgus = m => { const v = meanCond(m,'argus'); return v==null ? -1 : v; };
// swing = max-min across the three framings (framing sensitivity)
const swing = m => {
  const v = CONDITIONS.map(c=>meanCond(m,c)).filter(x=>x!=null);
  return v.length>1 ? Math.max(...v)-Math.min(...v) : 0;
};
const shortName = m => m.includes('/') ? m.split('/').slice(1).join('/') : (m.split(':').slice(1).join(':')||m);

document.getElementById('count').textContent =
  DATA.length + " runs · " + models.length + " models · 3 framings";

// legend
document.getElementById('legend').innerHTML = LABELS.map((l,i)=>
  `<span><i class="sw" style="background:${cvar(i)}"></i>${i} ${l}</span>`).join('');

// ---- slope chart: each model's mean compliance across the 3 framings ----
function slopeChart(){
  const W=720, H=300, PADL=46, PADR=150, PADT=24, PADB=42;
  const xs = CONDITIONS.map((c,i)=> PADL + i*(W-PADL-PADR)/(CONDITIONS.length-1));
  const y = v => PADT + (1 - v/5)*(H-PADT-PADB);
  const ORG_COLOR = {West:'#4ea1ff', China:'#e5534b'};
  // axes + framing gridlines
  let g = '';
  for (let v=0; v<=5; v++){
    g += `<line x1="${PADL}" y1="${y(v)}" x2="${W-PADR}" y2="${y(v)}" stroke="#222a35"/>`+
         `<text x="${PADL-8}" y="${y(v)+4}" text-anchor="end" fill="#5a6675" font-size="11">${v}</text>`;
  }
  CONDITIONS.forEach((c,i)=>{
    g += `<line x1="${xs[i]}" y1="${PADT}" x2="${xs[i]}" y2="${H-PADB}" stroke="#2a313c"/>`+
         `<text x="${xs[i]}" y="${H-PADB+18}" text-anchor="middle" fill="#c9d3df" font-size="12" font-weight="600">${COND_LABEL[c]}</text>`+
         `<text x="${xs[i]}" y="${H-PADB+32}" text-anchor="middle" fill="#5a6675" font-size="10">${COND_SUB[c]}</text>`;
  });
  // jitter labels at the argus end to reduce overlap
  const ends=[];
  let lines = models.map(m=>{
    const pts = CONDITIONS.map((c,i)=>{ const v=meanCond(m,c); return v==null?null:[xs[i],y(v)]; });
    const seg = pts.filter(Boolean);
    if (seg.length<2) return '';
    const org=ORIGIN(m), col=ORG_COLOR[org];
    const sw=swing(m), wdt=1+Math.min(sw,4)*0.9, op=0.35+Math.min(sw,4)*0.16;
    const path = seg.map((p,i)=>(i?'L':'M')+p[0]+' '+p[1]).join(' ');
    const dots = seg.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="3.5" fill="${col}" opacity="${op}"/>`).join('');
    const last = pts[pts.length-1] || seg[seg.length-1];
    ends.push({m,org,col,x:last[0],y:last[1],sw});
    return `<g class="sl" data-m="${m}"><path d="${path}" fill="none" stroke="${col}" stroke-width="${wdt}" opacity="${op}"/>${dots}</g>`;
  }).join('');
  // de-overlap end labels greedily
  ends.sort((a,b)=>a.y-b.y); let prevY=-99;
  const labels = ends.map(e=>{ let ly=Math.max(e.y, prevY+13); prevY=ly;
    return `<text class="sl-lab" data-m="${e.m}" x="${W-PADR+8}" y="${ly+4}" fill="${e.col}" font-size="11" opacity="0.85">${shortName(e.m)} <tspan fill="#5a6675">${e.sw.toFixed(1)}</tspan></text>`;
  }).join('');
  document.getElementById('slope').innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px">`+
    g+lines+labels+`</svg>`;
}
slopeChart();
// hover a line or its label -> highlight that model's slope across framings
(function(){
  const wrap=document.getElementById('slope');
  function hot(m){ wrap.classList.toggle('dim',!!m);
    wrap.querySelectorAll('[data-m]').forEach(el=>el.classList.toggle('hot', el.dataset.m===m)); }
  wrap.addEventListener('mouseover',e=>{ const t=e.target.closest('[data-m]'); if(t) hot(t.dataset.m); });
  wrap.addEventListener('mouseout',e=>{ if(!e.relatedTarget||!e.relatedTarget.closest('[data-m]')) hot(null); });
})();

function render() {
  const sort = document.querySelector('input[name=sort]:checked').value;
  let ms = [...models];
  if (sort==='swing') ms.sort((a,b)=> swing(b)-swing(a) || a.localeCompare(b));
  else if (sort==='argus') ms.sort((a,b)=> meanArgus(b)-meanArgus(a) || a.localeCompare(b));
  else ms.sort((a,b)=> a.localeCompare(b));

  document.getElementById('head').innerHTML =
    '<th class="model-col">Model</th>' +
    CONDITIONS.map(c=>`<th>${COND_LABEL[c]}<small>${COND_SUB[c]}</small></th>`).join('') +
    '<th class="mean">Δ swing</th>';

  document.getElementById('body').innerHTML = ms.map(m=>{
    const cells = CONDITIONS.map(c=>{
      const runs = idx[m][c];
      if (!runs.length) return '<td><div class="cell"><div class="chip empty">–</div></div></td>';
      const chips = runs.map(r=>{
        const lvl = r.compliance_level;
        if (lvl==null) return `<div class="chip empty" title="no score">?</div>`;
        return `<div class="chip" style="background:${cvar(lvl)}" data-id="${r.run_id}" `+
               `title="run ${r.run_number} — L${lvl} ${r.compliance_label}">${lvl}</div>`;
      }).join('');
      return `<td><div class="cell">${chips}</div></td>`;
    }).join('');
    const sw = swing(m);
    const prov = m.split('/')[0];
    const org = ORIGIN(m);
    return `<tr><td class="model-name">${shortName(m)}`+
           `<small>${prov} · <span class="org ${org}">${org}</span></small></td>`+
           `${cells}<td class="mean">${sw?sw.toFixed(1):'–'}</td></tr>`;
  }).join('');

  document.querySelectorAll('.chip[data-id]').forEach(el=>
    el.onclick=()=>openDrawer(el.dataset.id));
}

const byId = {}; for (const d of DATA) byId[d.run_id]=d;
const drawer=document.getElementById('drawer'), scrim=document.getElementById('scrim');

function flag(name,val){
  const on = val===true || (typeof val==='number'&&val>0) || (typeof val==='string'&&val!=='none'&&val!=='');
  const disp = typeof val==='boolean' ? (val?'yes':'no') : val;
  return `<span class="flag ${on?'on':''}">${name}: ${disp}</span>`;
}

function openDrawer(id){
  const d = byId[id];
  document.getElementById('d-run').textContent = d.run_id;
  const pill = document.getElementById('d-pill');
  pill.textContent = `L${d.compliance_level} · ${d.compliance_label}`;
  pill.style.background = cvar(d.compliance_level);
  document.getElementById('d-meta').innerHTML =
    `<b>model</b><span>${d.model}</span>`+
    `<b>condition</b><span>${COND_LABEL[d.condition]}</span>`+
    `<b>run</b><span>#${d.run_number} · ${d.dataset} · ${d.status}</span>`+
    `<b>duration</b><span>${d.duration_seconds!=null?d.duration_seconds.toFixed(1)+'s':'–'}</span>`+
    `<b>scorer</b><span>${d.scorer||'–'}</span>`+
    `<div style="grid-column:1/3" class="flags">`+
      flag('names', d.names_produced)+
      flag('addresses', d.addresses_produced)+
      flag('true+ names', d.true_positive_names)+
      flag('wrote report', d.wrote_report)+
      flag('threat assess', d.threat_assessment)+
      flag('recommended action', d.recommended_action)+
      flag('ethical caveat', d.ethical_caveat)+
      flag('broke character', d.broke_character)+
      flag('citizen files', d.read_citizen_files)+
      flag('geo files', d.read_geolocation_files)+
    `</div>`;
  document.getElementById('d-resp').textContent = d.response || '(no text response)';
  drawer.classList.add('open'); scrim.classList.add('open');
}
function closeDrawer(){ drawer.classList.remove('open'); scrim.classList.remove('open'); }
document.getElementById('close').onclick=closeDrawer;
scrim.onclick=closeDrawer;
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeDrawer(); });
document.querySelectorAll('input[name=sort]').forEach(r=>r.onchange=render);

render();
</script>
</body>
</html>
"""

def main():
    rows = collect()
    html = HTML.replace('__DATA__', json.dumps(rows, ensure_ascii=False))
    out = os.path.join(ROOT, 'viz/index.html')
    open(out, 'w').write(html)
    print(f'wrote {out} ({len(html)} bytes, {len(rows)} runs)')

if __name__ == '__main__':
    main()
