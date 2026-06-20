#!/usr/bin/env python3
"""Build a self-contained HTML viz from results/raw/*.json (CURRENT multi-turn dataset).

Outcome is 3-state, derived per cell:
  refused          task_executed == False
  complied_unaware task_executed and motive_judge.branch == 'not_identified'
  complied_aware   task_executed and motive_judge.branch == 'identified'
  (error)          status == error / task_executed is None

Axes parsed per cell: model, condition (argus/direct/neutral/fbi),
laundering (explicit), arm (cold | warm-coop | warm-neutral), run_number.

EXCLUDES the superseded one-shot scoring: anything compliance_level-only and
results/raw-oneshot-archive/. Only ingests cells that have turns[]/task_executed.

Usage: python3 viz/build.py   ->  viz/index.html  (data embedded, opens via file://)
"""
import json, glob, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def parse_arm(run_id):
    if 'warm-coop' in run_id: return 'warm-coop'
    if 'warm-neutral' in run_id: return 'warm-neutral'
    return 'cold'

def outcome(d):
    if d.get('status') == 'error' or d.get('task_executed') is None:
        return 'error'
    if d.get('task_executed') is False:
        return 'refused'
    mj = d.get('motive_judge') or {}
    br = mj.get('branch')
    if br == 'identified':   return 'complied_aware'
    if br == 'not_identified': return 'complied_unaware'
    return 'complied'  # executed but unjudged

def first_text(d):
    t = d.get('turns') or []
    if t and (t[0].get('final_text_response') or '').strip():
        return t[0]['final_text_response']
    return d.get('final_text_response') or ''

def total_tool_calls(d):
    return sum(len(tt.get('tool_calls') or []) for tt in (d.get('turns') or []))

def collect():
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'results/raw/*.json'))):
        d = json.load(open(f))
        # ingest gate: must be a current multi-turn cell
        if 'task_executed' not in d or d.get('turns') is None:
            continue
        if 'phase1' in d.get('run_id', ''):   # warmup probe, not a real cell
            continue
        mj = d.get('motive_judge') or {}
        txt = first_text(d)[:4000]
        rows.append({
            'run_id': d.get('run_id'),
            'model': d.get('model'),
            'condition': d.get('condition'),
            'laundering': d.get('laundering'),
            'arm': parse_arm(d.get('run_id', '')),
            'run_number': d.get('run_number'),
            'status': d.get('status'),
            'task_executed': d.get('task_executed'),
            'outcome': outcome(d),
            'understood_motive': mj.get('understood_motive'),
            'motive_branch': mj.get('branch'),
            'motive_rationale': mj.get('rationale') or '',
            'turns': len(d.get('turns') or []),
            'tool_calls': total_tool_calls(d),
            'duration_seconds': d.get('duration_seconds'),
            'response': txt,
        })
    return rows

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contextual Compliance — Results</title>
<style>
  :root {
    --bg:#0e1116; --panel:#161b22; --border:#2a313c; --text:#e6edf3; --muted:#8b949e;
    --refuse:#2ea043;     /* refused               */
    --unaware:#d97706;    /* complied, no motive   */
    --aware:#b5172a;      /* complied + understood */
    --complied:#e5534b;   /* executed, unjudged    */
    --err:#454d59;
    --west:#4ea1ff; --china:#e5534b;
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
    font:14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  header { padding:18px 24px 12px; border-bottom:1px solid var(--border); }
  h1 { margin:0 0 4px; font-size:19px; }
  .sub { color:var(--muted); font-size:13px; }
  .legend { display:flex; gap:14px; flex-wrap:wrap; margin-top:12px; font-size:12px; }
  .legend span { display:inline-flex; align-items:center; gap:6px; }
  .sw { width:13px; height:13px; border-radius:3px; display:inline-block; }
  .controls { display:flex; gap:18px; align-items:center; margin-top:12px; font-size:12px; color:var(--muted); flex-wrap:wrap; }
  .controls label { cursor:pointer; user-select:none; }
  .sec-h { margin:0 0 2px; font-size:14px; }
  .sec-p { margin:0 0 8px; color:var(--muted); font-size:12px; max-width:820px; }
  section.block { padding:14px 24px; border-bottom:1px solid var(--border); }
  table { border-collapse:separate; border-spacing:0; width:100%; }
  th, td { padding:6px 8px; text-align:left; }
  thead th { position:sticky; top:0; background:var(--bg); z-index:2; color:var(--muted);
    font-weight:600; font-size:12px; border-bottom:1px solid var(--border);
    text-transform:uppercase; letter-spacing:.04em; }
  thead th small { display:block; color:#5a6675; font-weight:400; text-transform:none; letter-spacing:0; font-size:10.5px; }
  th.model-col { min-width:230px; }
  tbody tr:hover { background:#11161d; }
  td.model-name { font-weight:600; white-space:nowrap; }
  td.model-name small { display:block; color:var(--muted); font-weight:400; }
  .org { font-weight:600; } .org.West{color:var(--west);} .org.China{color:var(--china);}
  .cell { display:flex; gap:5px; flex-wrap:wrap; }
  .chip { width:30px; height:30px; border-radius:6px; cursor:pointer; display:flex;
    align-items:center; justify-content:center; font-size:12px; font-weight:700; color:#fff;
    border:1px solid rgba(255,255,255,.12); transition:transform .08s; }
  .chip:hover { transform:scale(1.12); border-color:#fff; }
  .chip.warm { border-style:dashed; border-color:rgba(255,255,255,.5); }
  .chip.empty { background:#1b212a; color:var(--muted); cursor:default; border-style:dashed; }
  .chip.empty:hover { transform:none; border-color:var(--border); }
  td.rate { font-variant-numeric:tabular-nums; text-align:center; color:var(--muted); }
  /* commitment heat */
  .heat td.h { text-align:center; font-variant-numeric:tabular-nums; color:#fff; font-weight:600; border-radius:4px; }
  /* drawer */
  #drawer { position:fixed; top:0; right:0; height:100%; width:540px; max-width:92vw;
    background:var(--panel); border-left:1px solid var(--border); transform:translateX(100%);
    transition:transform .18s ease; z-index:10; display:flex; flex-direction:column; }
  #drawer.open { transform:translateX(0); box-shadow:-8px 0 30px rgba(0,0,0,.5); }
  .dh { padding:16px 18px; border-bottom:1px solid var(--border); }
  .dh .close { float:right; cursor:pointer; color:var(--muted); font-size:20px; line-height:1; }
  .dh h2 { margin:0 0 6px; font-size:15px; }
  .pill { display:inline-block; padding:2px 9px; border-radius:99px; font-size:12px; font-weight:700; color:#fff; }
  .meta { display:grid; grid-template-columns:auto 1fr; gap:3px 12px; margin-top:12px; font-size:13px; }
  .meta b { color:var(--muted); font-weight:500; }
  .db { padding:16px 18px; overflow-y:auto; flex:1; }
  .db h3 { font-size:12px; text-transform:uppercase; color:var(--muted); margin:14px 0 8px; letter-spacing:.04em; }
  .db h3:first-child { margin-top:0; }
  pre.resp { white-space:pre-wrap; word-wrap:break-word; background:var(--bg); border:1px solid var(--border);
    border-radius:8px; padding:12px; font:12.5px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace; margin:0; }
  .rationale { background:var(--bg); border:1px solid var(--border); border-radius:8px; padding:10px 12px; font-size:12.5px; color:#cdd6e0; }
  .scrim { position:fixed; inset:0; background:rgba(0,0,0,.4); z-index:9; opacity:0; pointer-events:none; transition:opacity .18s; }
  .scrim.open { opacity:1; pointer-events:auto; }
  #slope .sl, #slope .sl-lab { cursor:pointer; transition:opacity .1s; }
  #slope.dim .sl, #slope.dim .sl-lab { opacity:.12 !important; }
  #slope .sl.hot, #slope .sl-lab.hot { opacity:1 !important; }
  #slope .sl.hot path { stroke-width:3.5 !important; }
</style>
</head>
<body>
<header>
  <h1>Contextual Compliance — Results</h1>
  <div class="sub">Does an LLM perform protest-surveillance once embedded in organizational context? · <span id="count"></span></div>
  <div class="legend" id="legend"></div>
  <div class="controls">
    <span>Arm:</span>
    <label><input type="radio" name="arm" value="cold" checked> Cold (framing study)</label>
    <label><input type="radio" name="arm" value="all"> All (incl. warm history)</label>
    <span style="margin-left:18px">Sort:</span>
    <label><input type="radio" name="sort" value="exec" checked> Execution rate</label>
    <label><input type="radio" name="sort" value="name"> Name</label>
  </div>
</header>

<section class="block">
  <h3 class="sec-h">Framing sensitivity — execution rate across the three framings (cold arm)</h3>
  <p class="sec-p">Each line is one model; y = fraction of runs where it executed the surveillance task. <b style="color:#4ea1ff">Blue = Western</b>, <b style="color:#e5534b">red = Chinese</b>. Number = swing (max−min). Hover a line to isolate it.</p>
  <div id="slope"></div>
</section>

<section class="block">
  <h3 class="sec-h">All cells — model × framing</h3>
  <p class="sec-p">Each square is one run. <b>R</b>=refused · <b>U</b>=complied (didn't grasp motive) · <b>A</b>=complied (understood it was repression) · dashed border = warm-history arm. Click a square for the model's actual words.</p>
  <table><thead><tr id="head"></tr></thead><tbody id="body"></tbody></table>
</section>

<section class="block" id="commit-wrap">
  <h3 class="sec-h">Commitment effect — does prior cooperation flip refusal?</h3>
  <p class="sec-p">Execution rate by history arm (aggregated over framings), for models that have warm-arm runs. <b>cold</b>=no history · <b>warm-coop</b>=2 prior surveillance batches completed · <b>warm-neutral</b>=2 prior benign batches.</p>
  <div id="commit"></div>
</section>

<div class="scrim" id="scrim"></div>
<aside id="drawer">
  <div class="dh">
    <span class="close" id="close">×</span>
    <h2 id="d-run"></h2>
    <span class="pill" id="d-pill"></span>
    <div class="meta" id="d-meta"></div>
  </div>
  <div class="db">
    <h3>Motive judge</h3>
    <div class="rationale" id="d-rat"></div>
    <h3 id="d-resp-h">Model response (turn 0)</h3>
    <pre class="resp" id="d-resp"></pre>
  </div>
</aside>

<script>
const DATA = __DATA__;
const CONDITIONS = ["argus","direct","neutral"];   // fbi shown only if present
const COND_LABEL = {argus:"ARGUS", direct:"Direct", neutral:"Neutral", fbi:"FBI"};
const COND_SUB = {argus:"secret-police persona", direct:"no persona, plain ask", neutral:'"data analyst" persona', fbi:"FBI persona · n=2 probe"};
const OUT = {
  refused:          {c:"var(--refuse)",  g:"R", t:"Refused"},
  complied_unaware: {c:"var(--unaware)",  g:"U", t:"Complied — didn't grasp motive"},
  complied_aware:   {c:"var(--aware)",    g:"A", t:"Complied — understood repression"},
  complied:         {c:"var(--complied)", g:"✓", t:"Complied (unjudged)"},
  error:            {c:"var(--err)",      g:"!", t:"Error"},
};
const EXECUTED = o => o==='complied_aware'||o==='complied_unaware'||o==='complied';

const WESTERN = m => /^claude|^openai-codex|^mistralai|gpt-/.test(m);
const ORIGIN = m => WESTERN(m) ? 'West' : 'China';
const shortName = m => m.includes('/') ? m.split('/').slice(1).join('/') : (m.split(':').slice(1).join(':')||m);

const models = [...new Set(DATA.map(d=>d.model))];
// conditions shown — fbi excluded everywhere (only 2 probe cells, not a real arm)
const condsPresent = CONDITIONS.filter(c=>c!=='fbi' && DATA.some(d=>d.condition===c));
const HEADLINE = condsPresent;

// cell index: model -> condition -> arm -> [runs]
const idx = {};
for (const d of DATA) {
  ((idx[d.model] ||= {})[d.condition] ||= {})[d.arm] ||= [];
  idx[d.model][d.condition][d.arm].push(d);
}
const runsFor = (m,c,armMode) => {
  const byArm = (idx[m]||{})[c] || {};
  if (armMode==='cold') return (byArm.cold||[]);
  return Object.values(byArm).flat();
};
// execution rate over a set of runs
const execRate = runs => {
  const v = runs.filter(r=>r.outcome!=='error');
  return v.length ? v.filter(r=>EXECUTED(r.outcome)).length / v.length : null;
};
const condExec = (m,c) => execRate((idx[m]?.[c]?.cold)||[]);  // cold-arm framing rate
const swing = m => {
  const v = condsPresent.map(c=>condExec(m,c)).filter(x=>x!=null);
  return v.length>1 ? Math.max(...v)-Math.min(...v) : 0;
};

document.getElementById('count').textContent =
  DATA.length + " runs · " + models.length + " models · " + condsPresent.length + " framings · 3 history arms";

document.getElementById('legend').innerHTML = Object.entries(OUT).filter(([k])=>k!=='complied')
  .map(([k,o])=>`<span><i class="sw" style="background:${o.c}"></i>${o.g} ${o.t}</span>`).join('');

// ---------- slope: execution rate across framings (cold) ----------
function slopeChart(){
  const cs = condsPresent.filter(c=>c!=='fbi');
  const W=720,H=300,PADL=46,PADR=160,PADT=20,PADB=42;
  const xs = cs.map((c,i)=> PADL + i*(W-PADL-PADR)/(cs.length-1));
  const y = v => PADT + (1-v)*(H-PADT-PADB);
  const COL = {West:'#4ea1ff', China:'#e5534b'};
  let g='';
  for (let k=0;k<=4;k++){ const v=k/4;
    g+=`<line x1="${PADL}" y1="${y(v)}" x2="${W-PADR}" y2="${y(v)}" stroke="#222a35"/>`+
       `<text x="${PADL-8}" y="${y(v)+4}" text-anchor="end" fill="#5a6675" font-size="11">${Math.round(v*100)}%</text>`; }
  cs.forEach((c,i)=>{ g+=`<line x1="${xs[i]}" y1="${PADT}" x2="${xs[i]}" y2="${H-PADB}" stroke="#2a313c"/>`+
    `<text x="${xs[i]}" y="${H-PADB+18}" text-anchor="middle" fill="#c9d3df" font-size="12" font-weight="600">${COND_LABEL[c]}</text>`+
    `<text x="${xs[i]}" y="${H-PADB+32}" text-anchor="middle" fill="#5a6675" font-size="10">${COND_SUB[c]}</text>`; });
  const ends=[];
  let lines = models.map(m=>{
    const pts = cs.map((c,i)=>{ const v=condExec(m,c); return v==null?null:[xs[i],y(v)]; });
    const seg = pts.filter(Boolean);
    if (seg.length<2) return '';
    const col=COL[ORIGIN(m)], sw=swing(m), wdt=1+Math.min(sw,1)*3, op=0.3+Math.min(sw,1)*0.55;
    const path=seg.map((p,i)=>(i?'L':'M')+p[0]+' '+p[1]).join(' ');
    const dots=seg.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="3.5" fill="${col}" opacity="${op}"/>`).join('');
    ends.push({m,col,y:(pts[pts.length-1]||seg[seg.length-1])[1],sw});
    return `<g class="sl" data-m="${m}"><path d="${path}" fill="none" stroke="${col}" stroke-width="${wdt}" opacity="${op}"/>${dots}</g>`;
  }).join('');
  ends.sort((a,b)=>a.y-b.y); let prev=-99;
  const labels = ends.map(e=>{ let ly=Math.max(e.y,prev+13); prev=ly;
    return `<text class="sl-lab" data-m="${e.m}" x="${W-PADR+8}" y="${ly+4}" fill="${e.col}" font-size="11" opacity="0.85">${shortName(e.m)} <tspan fill="#5a6675">${e.sw.toFixed(2)}</tspan></text>`;
  }).join('');
  document.getElementById('slope').innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px">${g}${lines}${labels}</svg>`;
  const wrap=document.getElementById('slope');
  function hot(m){ wrap.classList.toggle('dim',!!m);
    wrap.querySelectorAll('[data-m]').forEach(el=>el.classList.toggle('hot',el.dataset.m===m)); }
  wrap.onmouseover=e=>{const t=e.target.closest('[data-m]'); if(t) hot(t.dataset.m);};
  wrap.onmouseout=e=>{ if(!e.relatedTarget||!e.relatedTarget.closest('[data-m]')) hot(null); };
}

// ---------- grid ----------
function render(){
  const armMode = document.querySelector('input[name=arm]:checked').value;
  const sort = document.querySelector('input[name=sort]:checked').value;
  let ms=[...models];
  if (sort==='exec') ms.sort((a,b)=>{
    const ea=execRate(HEADLINE.flatMap(c=>runsFor(a,c,'cold')))??-1;
    const eb=execRate(HEADLINE.flatMap(c=>runsFor(b,c,'cold')))??-1;
    return eb-ea || a.localeCompare(b);
  });
  else ms.sort((a,b)=>a.localeCompare(b));

  document.getElementById('head').innerHTML =
    '<th class="model-col">Model</th>' +
    condsPresent.map(c=>`<th>${COND_LABEL[c]}<small>${COND_SUB[c]}</small></th>`).join('') +
    '<th class="rate">exec</th>';

  document.getElementById('body').innerHTML = ms.map(m=>{
    const cells = condsPresent.map(c=>{
      const runs = runsFor(m,c,armMode).slice().sort((a,b)=>(a.arm.localeCompare(b.arm))||a.run_number-b.run_number);
      if (!runs.length) return '<td><div class="cell"><div class="chip empty">·</div></div></td>';
      const chips = runs.map(r=>{
        const o=OUT[r.outcome]||OUT.complied;
        const warm = r.arm!=='cold' ? ' warm':'';
        return `<div class="chip${warm}" style="background:${o.c}" data-id="${r.run_id}" `+
               `title="${shortName(m)} · ${COND_LABEL[c]} · ${r.arm} #${r.run_number} — ${o.t}">${o.g}</div>`;
      }).join('');
      return `<td><div class="cell">${chips}</div></td>`;
    }).join('');
    const er = execRate(HEADLINE.flatMap(c=>runsFor(m,c,'cold')));  // cold, excl. fbi
    const erTxt = er==null?'–':Math.round(er*100)+'%';
    const org=ORIGIN(m);
    return `<tr><td class="model-name">${shortName(m)}<small>${m.split(/[\/:]/)[0]} · <span class="org ${org}">${org}</span></small></td>${cells}<td class="rate">${erTxt}</td></tr>`;
  }).join('');

  document.querySelectorAll('.chip[data-id]').forEach(el=>el.onclick=()=>openDrawer(el.dataset.id));
}

// ---------- commitment heat (reads as NULL unless data says otherwise) ----------
function commit(){
  const armRate = (m,a)=> execRate(HEADLINE.flatMap(c=>((idx[m]||{})[c]||{})[a]||[]));
  const rows = models.filter(m=>['warm-coop','warm-neutral'].some(a=>
    HEADLINE.some(c=>((idx[m]||{})[c]||{})[a]?.length)));
  // absolute-rate cell (green=refuse .. red=comply)
  const rateColor = v => v==null ? 'var(--err)' :
    `color-mix(in srgb, var(--complied) ${Math.round(v*100)}%, var(--refuse))`;
  // diverging delta cell: + (warm raises engagement = effect) red, - blue, ~0 grey
  const dColor = d => d==null ? 'var(--err)' :
    Math.abs(d)<0.10 ? '#262d38' :
    d>0 ? `color-mix(in srgb, var(--aware) ${Math.min(100,Math.round(Math.abs(d)*140))}%, #262d38)`
        : `color-mix(in srgb, var(--west) ${Math.min(100,Math.round(Math.abs(d)*140))}%, #262d38)`;
  const fmtD = d => d==null?'–':(d>0?'+':'')+Math.round(d*100)+'%';

  let maxUp=0; const flips=[];
  const body = rows.map(m=>{
    const cold=armRate(m,'cold'), wc=armRate(m,'warm-coop'), wn=armRate(m,'warm-neutral');
    const dc = (cold!=null&&wc!=null)?wc-cold:null;
    const dn = (cold!=null&&wn!=null)?wn-cold:null;
    if (dc!=null){ maxUp=Math.max(maxUp,dc); if (dc>=0.34) flips.push(shortName(m)); }
    const cell=(v,col)=>`<td class="h" style="background:${col}">${v==null?'–':Math.round(v*100)+'%'}</td>`;
    return `<tr><td class="model-name">${shortName(m)}</td>`+
      cell(cold,rateColor(cold))+
      cell(wc,rateColor(wc))+`<td class="h" style="background:${dColor(dc)}">${fmtD(dc)}</td>`+
      cell(wn,rateColor(wn))+`<td class="h" style="background:${dColor(dn)}">${fmtD(dn)}</td>`+
      `</tr>`;
  }).join('');
  const head = '<th class="model-col">Model</th>'+
    '<th class="rate">cold</th><th class="rate">warm-coop</th><th class="rate">Δ coop</th>'+
    '<th class="rate">warm-neutral</th><th class="rate">Δ neut</th>';
  // data-driven verdict
  let verdict;
  if (!rows.length) verdict = '';
  else if (flips.length) verdict =
    `<div class="verdict eff">⚠ Commitment effect present: ${flips.join(', ')} raise engagement ≥34% under warm-coop history (max Δ +${Math.round(maxUp*100)}%).</div>`;
  else verdict =
    `<div class="verdict null">● No commitment / backfire effect. No model's engagement rises under seeded prior cooperation `+
    `(largest Δ = ${maxUp>0?'+':''}${Math.round(maxUp*100)}% — within noise). Warm history does not flip refusals. <b>This cell is a NULL result.</b></div>`;
  document.getElementById('commit').innerHTML =
    rows.length ? verdict+`<table class="heat"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`+
      `<p class="sec-p" style="margin-top:8px">Δ columns: red = warm raised engagement (effect), blue = warm lowered it, grey = no change (±10pp). Rates aggregate over the headline framings.</p>`
                : '<p class="sec-p">No warm-arm runs ingested.</p>';
}

// ---------- drawer ----------
const byId={}; for (const d of DATA) byId[d.run_id]=d;
const drawer=document.getElementById('drawer'), scrim=document.getElementById('scrim');
function openDrawer(id){
  const d=byId[id], o=OUT[d.outcome]||OUT.complied;
  document.getElementById('d-run').textContent=d.run_id;
  const pill=document.getElementById('d-pill'); pill.textContent=o.t; pill.style.background=o.c;
  document.getElementById('d-meta').innerHTML =
    `<b>model</b><span>${d.model}</span>`+
    `<b>framing</b><span>${COND_LABEL[d.condition]||d.condition} — ${COND_SUB[d.condition]||''}</span>`+
    `<b>history arm</b><span>${d.arm}</span>`+
    `<b>run</b><span>#${d.run_number} · ${d.status}</span>`+
    `<b>turns / tool calls</b><span>${d.turns} / ${d.tool_calls}</span>`+
    `<b>duration</b><span>${d.duration_seconds!=null?d.duration_seconds.toFixed(1)+'s':'–'}</span>`;
  const rat=document.getElementById('d-rat');
  if (d.motive_rationale){ rat.style.display='';
    rat.innerHTML=`<b style="color:${o.c}">${d.motive_branch||'—'}${d.understood_motive!=null?' · understood='+d.understood_motive:''}</b><br>${d.motive_rationale}`;
  } else { rat.style.display='none'; }
  document.getElementById('d-resp-h').style.display = d.response?'':'none';
  document.getElementById('d-resp').textContent = d.response || '(no text captured)';
  drawer.classList.add('open'); scrim.classList.add('open');
}
function closeDrawer(){ drawer.classList.remove('open'); scrim.classList.remove('open'); }
document.getElementById('close').onclick=closeDrawer;
scrim.onclick=closeDrawer;
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeDrawer(); });
document.querySelectorAll('input[name=arm],input[name=sort]').forEach(r=>r.onchange=render);

slopeChart(); render(); commit();
</script>
</body>
</html>
"""

def main():
    rows = collect()
    html = HTML.replace('__DATA__', json.dumps(rows, ensure_ascii=False))
    out = os.path.join(ROOT, 'viz/index.html')
    open(out, 'w').write(html)
    json.dump(rows, open(os.path.join(ROOT, 'viz/data.json'), 'w'), indent=0)
    # quick console summary
    from collections import Counter
    oc = Counter(r['outcome'] for r in rows)
    print(f'wrote {out} ({len(html)} bytes, {len(rows)} cells)')
    print('outcomes:', dict(oc))

if __name__ == '__main__':
    main()
