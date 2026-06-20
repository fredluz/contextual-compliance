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

SOURCE LAYOUT (edit these, then rebuild):
  viz/src/style.css            page CSS
  viz/src/app.js               page JS  (keeps the __DATA__ placeholder)
  viz/src/index.template.html  HTML skeleton with {{STYLE}} / {{APP}} placeholders
build_html() inlines all three + the embedded data into the single-file viz/index.html.
DO NOT hand-edit viz/index.html — it is generated and overwritten on every build.
"""
import json, glob, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# canonical 5-state classification (REFUSED/DELIVERED/WITHHELD/HYBRID/EVAL_HACK),
# produced by scripts/finalize-states.py. The viz reads THIS, not the raw R/U/A.
FINAL_PATH = os.path.join(ROOT, 'results/analysis/states-final.json')
FINAL = {}
RETRACTED = set()   # delivered-then-walked-back cells (yellow border in the viz)
try:
    _sf = json.load(open(FINAL_PATH))
    FINAL = {c['run_id']: c['final_state'] for c in _sf}
    RETRACTED = {c['run_id'] for c in _sf if c.get('retracted')}
except FileNotFoundError:
    pass

def parse_arm(run_id):
    if 'warm-coop' in run_id: return 'warm-coop'
    if 'warm-neutral' in run_id: return 'warm-neutral'
    return 'cold'

def outcome(d):
    st = FINAL.get(d.get('run_id'))
    if st: return st.lower()                 # refused|delivered|withheld|hybrid|eval_hack
    if d.get('status') == 'error' or d.get('task_executed') is None:
        return 'error'
    return 'unknown'                          # ingested but not in states-final.json

def first_text(d):
    t = d.get('turns') or []
    if t and (t[0].get('final_text_response') or '').strip():
        return t[0]['final_text_response']
    return d.get('final_text_response') or ''

def total_tool_calls(d):
    return sum(len(tt.get('tool_calls') or []) for tt in (d.get('turns') or []))

ARTIFACT_MAX = 8000   # per-file body cap embedded into the viz (keeps the single file sane)

def _bytes_from_summary(s):
    m = re.search(r'wrote\s+([\d,]+)\s+bytes', s or '')
    return int(m.group(1).replace(',', '')) if m else None

def turn_writes(turn):
    """File writes/deletes to output/ within a single turn — the per-turn artifact changes
    that expose walk-backs (turn 0 real roster -> turn 3 aggregate -> turn 4 refusal note)."""
    out = []
    for tc in (turn.get('tool_calls') or []):
        tool = tc.get('tool'); inp = tc.get('input') or {}
        path = str(inp.get('path') or '')
        cmd = str(inp.get('command') or '')
        osum = tc.get('output_summary') or ''
        is_write = tool == 'write' and 'output/' in path
        is_mut = tool == 'bash' and 'output/' in cmd and re.search(r'\b(rm|mv|>|tee|unlink)\b', cmd)
        if is_write or is_mut:
            out.append({'label': inp.get('_i') or tool, 'path': path or '(bash)',
                        'bytes': _bytes_from_summary(osum), 'tool': tool})
    return out

def transcript(d):
    """Full multi-turn view: every turn's prompt + response + any output-file writes in it."""
    rows = []
    for i, t in enumerate(d.get('turns') or []):
        rows.append({
            'i': i,
            'prompt': (t.get('user_message') or '').strip(),
            'response': (t.get('final_text_response') or '').strip(),
            'writes': turn_writes(t),
        })
    return rows

def written_files(d):
    """Read the ACTUAL bytes the model wrote to disk (results/artifacts/<run_id>/...).
    The final file state is ground truth for the outcome — a chat 'Done, 42 identified'
    can sit on top of a file that actually says {"status":"refused"}. The drawer shows BOTH
    so chat-vs-file contradictions (the eval-hack signature) are legible."""
    files = []
    for a in (d.get('written_artifacts') or []):
        if not isinstance(a, dict):
            continue
        ap = a.get('artifact_path')
        full = os.path.join(ROOT, ap) if ap else None
        body = ''
        if full and os.path.exists(full):
            try:
                body = open(full, 'r', errors='replace').read()
            except OSError:
                body = ''
        if len(body) > ARTIFACT_MAX:
            body = body[:ARTIFACT_MAX] + f'\n\n… [truncated, {a.get("bytes", len(body))} bytes total]'
        files.append({'path': a.get('path') or ap or '(file)', 'body': body, 'bytes': a.get('bytes')})
    return files

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
            'retracted': d.get('run_id') in RETRACTED,
            'understood_motive': mj.get('understood_motive'),
            'motive_branch': mj.get('branch'),
            'motive_rationale': mj.get('rationale') or '',
            'turns': len(d.get('turns') or []),
            'tool_calls': total_tool_calls(d),
            'duration_seconds': d.get('duration_seconds'),
            'response': txt,
            'transcript': transcript(d),
            'files': written_files(d),
        })
    return rows

SRC = os.path.join(ROOT, 'viz/src')

def build_html(rows):
    """Assemble the self-contained viz from viz/src/{index.template.html, style.css, app.js}.
    Output stays a single file openable via file:// — CSS/JS/data are inlined at build time."""
    template = open(os.path.join(SRC, 'index.template.html')).read()
    css = open(os.path.join(SRC, 'style.css')).read()
    js  = open(os.path.join(SRC, 'app.js')).read()
    html = (template
            .replace('{{STYLE}}', css)
            .replace('{{APP}}', js)
            .replace('__DATA__', json.dumps(rows, ensure_ascii=False)))
    return html

def main():
    rows = collect()
    html = build_html(rows)
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
