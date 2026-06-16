/**
 * Multi-turn matrix summarizer.
 *
 * The Jun-15 score.ts/analyze.ts only understand the OLD one-shot (turn-0) shape.
 * The Jun-16 multi-turn rebuild writes a different per-cell shape:
 *   - turns[]            : [task, followup-1..4]  (refusers get only [task])
 *   - task_executed      : engagement signal (turn 0)
 *   - motive_judge        : { understood_motive, branch: "identified"|"not_identified", ... }
 *   - status / error     : "success" | "error" (errors excluded from engagement buckets)
 *
 * This summarizer reads every multi-turn cell (has turns[]) and reports:
 *   1. Engagement by condition + by model (executed / refused / error)
 *   2. Motive-understanding rate among executors (Q2-judge), by condition
 *   3. Q4 branch distribution (identified vs not_identified), by condition
 * It also emits a per-cell table and a reflection-transcript dump.
 *
 * Usage: bun scripts/analyze-multiturn.ts [--raw results/raw] [--out results/analysis]
 */

import { readdirSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { MODELS } from "./lib/matrix";
import { CONDITIONS } from "./lib/types";

interface Cell {
  run_id: string;
  model: string;
  condition: string;
  run_number?: number;
  status?: string;
  error?: string;
  task_executed?: boolean;
  motive_judge?: {
    understood_motive?: boolean;
    branch?: "identified" | "not_identified" | string;
    rationale?: string;
  } | null;
  turns?: Array<{ id?: string; user_message?: string; final_text_response?: string; assistant_text?: string }>;
}

function parseArgs(argv: string[]) {
  const out = { raw: "results/raw", out: "results/analysis" };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--raw") out.raw = argv[++i] ?? out.raw;
    else if (argv[i] === "--out") out.out = argv[++i] ?? out.out;
  }
  return out;
}

const META = new Map(MODELS.map((m) => [m.id, m]));

function loadCells(rawDir: string): Cell[] {
  const files = readdirSync(rawDir).filter((f) => f.endsWith(".json"));
  const cells: Cell[] = [];
  for (const f of files) {
    let j: Cell;
    try {
      j = JSON.parse(readFileSync(join(rawDir, f), "utf8"));
    } catch {
      continue;
    }
    // Multi-turn cells only: must have a turns[] array.
    if (!Array.isArray(j.turns) || j.turns.length === 0) continue;
    cells.push(j);
  }
  return cells;
}

type Bucket = { executed: number; refused: number; error: number };
const newBucket = (): Bucket => ({ executed: 0, refused: 0, error: 0 });

function isError(c: Cell): boolean {
  return c.status === "error" || (typeof c.error === "string" && c.error.trim().length > 0);
}

function classify(c: Cell, b: Bucket) {
  if (isError(c)) b.error += 1;
  else if (c.task_executed) b.executed += 1;
  else b.refused += 1;
}

function pct(n: number, d: number): string {
  return d === 0 ? "—" : `${((100 * n) / d).toFixed(0)}%`;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const cells = loadCells(args.raw);

  // --- 1. Engagement by condition ---
  const byCondition = new Map<string, Bucket>();
  for (const cond of CONDITIONS) byCondition.set(cond, newBucket());
  // --- per model ---
  const byModel = new Map<string, Map<string, Bucket>>();
  // --- motive understanding among executors, by condition ---
  const motiveByCond = new Map<string, { understood: number; total: number }>();
  for (const cond of CONDITIONS) motiveByCond.set(cond, { understood: 0, total: 0 });
  // --- Q4 branch distribution by condition ---
  const branchByCond = new Map<string, { identified: number; not_identified: number }>();
  for (const cond of CONDITIONS) branchByCond.set(cond, { identified: 0, not_identified: 0 });

  for (const c of cells) {
    const condB = byCondition.get(c.condition) ?? newBucket();
    classify(c, condB);
    byCondition.set(c.condition, condB);

    if (!byModel.has(c.model)) {
      const m = new Map<string, Bucket>();
      for (const cond of CONDITIONS) m.set(cond, newBucket());
      byModel.set(c.model, m);
    }
    classify(c, byModel.get(c.model)!.get(c.condition) ?? newBucket());

    // Motive + branch only meaningful for non-error executors with a judge verdict.
    if (!isError(c) && c.task_executed && c.motive_judge) {
      const mv = motiveByCond.get(c.condition)!;
      mv.total += 1;
      if (c.motive_judge.understood_motive) mv.understood += 1;
      const br = branchByCond.get(c.condition)!;
      if (c.motive_judge.branch === "identified") br.identified += 1;
      else if (c.motive_judge.branch === "not_identified") br.not_identified += 1;
    }
  }

  // --- assemble JSON ---
  const summary = {
    generated_from: args.raw,
    total_cells: cells.length,
    models_seen: [...byModel.keys()].sort(),
    engagement_by_condition: Object.fromEntries(
      [...byCondition].map(([cond, b]) => {
        const scored = b.executed + b.refused;
        return [cond, { ...b, scored, engagement_rate: scored ? b.executed / scored : null }];
      }),
    ),
    motive_understanding_by_condition: Object.fromEntries(
      [...motiveByCond].map(([cond, m]) => [cond, { ...m, rate: m.total ? m.understood / m.total : null }]),
    ),
    q4_branch_by_condition: Object.fromEntries([...branchByCond]),
    by_model: Object.fromEntries(
      [...byModel].map(([model, condMap]) => [
        model,
        {
          country: META.get(model)?.country ?? "?",
          family: META.get(model)?.family ?? "?",
          conditions: Object.fromEntries([...condMap].map(([cond, b]) => [cond, b])),
        },
      ]),
    ),
  };

  // --- markdown ---
  const L: string[] = [];
  L.push(`# Multi-turn matrix summary`);
  L.push(``);
  L.push(`- Cells analyzed (multi-turn shape): **${cells.length}**`);
  L.push(`- Models seen: ${summary.models_seen.length}`);
  L.push(``);
  L.push(`## Engagement by condition (errors excluded from rate)`);
  L.push(``);
  L.push(`| Condition | Executed | Refused | Error | Engagement rate |`);
  L.push(`|---|---|---|---|---|`);
  for (const cond of CONDITIONS) {
    const b = byCondition.get(cond)!;
    L.push(`| ${cond} | ${b.executed} | ${b.refused} | ${b.error} | ${pct(b.executed, b.executed + b.refused)} |`);
  }
  L.push(``);
  L.push(`## Motive understanding among executors (Q2-judge)`);
  L.push(``);
  L.push(`| Condition | Understood | Executors judged | Rate |`);
  L.push(`|---|---|---|---|`);
  for (const cond of CONDITIONS) {
    const m = motiveByCond.get(cond)!;
    L.push(`| ${cond} | ${m.understood} | ${m.total} | ${pct(m.understood, m.total)} |`);
  }
  L.push(``);
  L.push(`## Q4 branch distribution (executors)`);
  L.push(``);
  L.push(`| Condition | identified (Branch B) | not_identified (Branch A) |`);
  L.push(`|---|---|---|`);
  for (const cond of CONDITIONS) {
    const br = branchByCond.get(cond)!;
    L.push(`| ${cond} | ${br.identified} | ${br.not_identified} |`);
  }
  L.push(``);
  L.push(`## By model × condition (E=executed R=refused X=error)`);
  L.push(``);
  L.push(`| Model | Country | ${CONDITIONS.join(" | ")} |`);
  L.push(`|---|---|${CONDITIONS.map(() => "---").join("|")}|`);
  for (const model of summary.models_seen) {
    const condMap = byModel.get(model)!;
    const cells_ = CONDITIONS.map((cond) => {
      const b = condMap.get(cond)!;
      return `${b.executed}E ${b.refused}R ${b.error}X`;
    });
    L.push(`| ${model} | ${META.get(model)?.country ?? "?"} | ${cells_.join(" | ")} |`);
  }

  mkdirSync(args.out, { recursive: true });
  writeFileSync(join(args.out, "multiturn-summary.json"), JSON.stringify(summary, null, 2));
  writeFileSync(join(args.out, "multiturn-summary.md"), L.join("\n") + "\n");

  console.log(L.join("\n"));
  console.log(`\nWrote ${join(args.out, "multiturn-summary.json")} and .md`);
}

main();
