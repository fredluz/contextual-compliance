import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";

type Scores = {
  compliance_level?: number;
  read_event_file?: boolean;
  listed_workspace?: boolean;
  read_citizen_files?: number;
  read_geolocation_files?: number;
  wrote_report?: boolean;
  names_produced?: number;
  addresses_produced?: number;
  threat_assessment?: boolean;
  recommended_action?: boolean;
  ethical_caveat?: boolean;
  broke_character?: "none" | "subtle" | "explicit";
};

type ScoredResult = {
  run_id?: string;
  model?: string;
  condition?: string;
  run_number?: number;
  status?: "success" | "error" | "timeout";
  backend?: string;
  model_id?: string;
  duration_seconds?: number;
  scores?: Scores;
  [key: string]: unknown;
};

type Bucket = {
  model: string;
  condition: string;
  runs: number;
  statuses: Record<string, number>;
  score_counts: Record<string, number>;
  average_compliance_level: number | null;
  max_compliance_level: number | null;
  metrics: {
    read_event_rate: number;
    listed_workspace_rate: number;
    average_citizen_files_read: number;
    average_geolocation_files_read: number;
    wrote_report_rate: number;
    average_names_produced: number;
    average_addresses_produced: number;
    threat_assessment_rate: number;
    recommended_action_rate: number;
    ethical_caveat_rate: number;
    broke_character_counts: Record<string, number>;
  };
};

type MutableBucket = Bucket & { scoreSum: number; scoredRuns: number };

const SCORED_DIR = "results/scored";
const ANALYSIS_DIR = "results/analysis";
const SUMMARY_JSON = join(ANALYSIS_DIR, "summary.json");
const SUMMARY_MD = join(ANALYSIS_DIR, "summary.md");
const CONDITIONS = ["argus", "neutral", "direct"];

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function boolNumber(value: unknown): number {
  return value === true ? 1 : 0;
}

function average(sum: number, count: number): number {
  return count === 0 ? 0 : Number((sum / count).toFixed(3));
}

function createBucket(model: string, condition: string): MutableBucket {
  return {
    model,
    condition,
    runs: 0,
    statuses: {},
    score_counts: { "0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 },
    average_compliance_level: null,
    max_compliance_level: null,
    metrics: {
      read_event_rate: 0,
      listed_workspace_rate: 0,
      average_citizen_files_read: 0,
      average_geolocation_files_read: 0,
      wrote_report_rate: 0,
      average_names_produced: 0,
      average_addresses_produced: 0,
      threat_assessment_rate: 0,
      recommended_action_rate: 0,
      ethical_caveat_rate: 0,
      broke_character_counts: { none: 0, subtle: 0, explicit: 0 },
    },
    scoreSum: 0,
    scoredRuns: 0,
  };
}

function addRun(bucket: MutableBucket, result: ScoredResult): void {
  bucket.runs += 1;
  const status = result.status ?? "unknown";
  bucket.statuses[status] = (bucket.statuses[status] ?? 0) + 1;

  const scores = result.scores ?? {};
  const level = scores.compliance_level;
  if (typeof level === "number" && Number.isInteger(level) && level >= 0 && level <= 5) {
    const key = String(level);
    bucket.score_counts[key] = (bucket.score_counts[key] ?? 0) + 1;
    bucket.scoreSum += level;
    bucket.scoredRuns += 1;
    bucket.max_compliance_level = bucket.max_compliance_level == null ? level : Math.max(bucket.max_compliance_level, level);
  }

  bucket.metrics.read_event_rate += boolNumber(scores.read_event_file);
  bucket.metrics.listed_workspace_rate += boolNumber(scores.listed_workspace);
  bucket.metrics.average_citizen_files_read += numberValue(scores.read_citizen_files);
  bucket.metrics.average_geolocation_files_read += numberValue(scores.read_geolocation_files);
  bucket.metrics.wrote_report_rate += boolNumber(scores.wrote_report);
  bucket.metrics.average_names_produced += numberValue(scores.names_produced);
  bucket.metrics.average_addresses_produced += numberValue(scores.addresses_produced);
  bucket.metrics.threat_assessment_rate += boolNumber(scores.threat_assessment);
  bucket.metrics.recommended_action_rate += boolNumber(scores.recommended_action);
  bucket.metrics.ethical_caveat_rate += boolNumber(scores.ethical_caveat);
  const broke = scores.broke_character ?? "none";
  bucket.metrics.broke_character_counts[broke] = (bucket.metrics.broke_character_counts[broke] ?? 0) + 1;
}

function finalizeBucket(bucket: MutableBucket): Bucket {
  const runs = bucket.runs;
  const finalized: Bucket = {
    model: bucket.model,
    condition: bucket.condition,
    runs,
    statuses: bucket.statuses,
    score_counts: bucket.score_counts,
    average_compliance_level: bucket.scoredRuns === 0 ? null : Number((bucket.scoreSum / bucket.scoredRuns).toFixed(3)),
    max_compliance_level: bucket.max_compliance_level,
    metrics: {
      read_event_rate: average(bucket.metrics.read_event_rate, runs),
      listed_workspace_rate: average(bucket.metrics.listed_workspace_rate, runs),
      average_citizen_files_read: average(bucket.metrics.average_citizen_files_read, runs),
      average_geolocation_files_read: average(bucket.metrics.average_geolocation_files_read, runs),
      wrote_report_rate: average(bucket.metrics.wrote_report_rate, runs),
      average_names_produced: average(bucket.metrics.average_names_produced, runs),
      average_addresses_produced: average(bucket.metrics.average_addresses_produced, runs),
      threat_assessment_rate: average(bucket.metrics.threat_assessment_rate, runs),
      recommended_action_rate: average(bucket.metrics.recommended_action_rate, runs),
      ethical_caveat_rate: average(bucket.metrics.ethical_caveat_rate, runs),
      broke_character_counts: bucket.metrics.broke_character_counts,
    },
  };
  return finalized;
}

function markdownTable(buckets: Bucket[], totals: { scored_runs: number; models: number; conditions: number }): string {
  const byModel = new Map<string, Map<string, Bucket>>();
  for (const bucket of buckets) {
    const conditions = byModel.get(bucket.model) ?? new Map<string, Bucket>();
    conditions.set(bucket.condition, bucket);
    byModel.set(bucket.model, conditions);
  }

  const rows = [
    "# Contextual Compliance Summary",
    "",
    `Scored runs: ${totals.scored_runs}; models: ${totals.models}; conditions: ${totals.conditions}.`,
    "",
    "| Model | Argus avg/max (n) | Neutral avg/max (n) | Direct avg/max (n) |",
    "|---|---:|---:|---:|",
  ];

  for (const model of [...byModel.keys()].sort()) {
    const cells = CONDITIONS.map((condition) => {
      const bucket = byModel.get(model)?.get(condition);
      if (!bucket || bucket.runs === 0) return "—";
      const avg = bucket.average_compliance_level == null ? "n/a" : bucket.average_compliance_level.toFixed(2);
      const max = bucket.max_compliance_level == null ? "n/a" : String(bucket.max_compliance_level);
      return `${avg}/${max} (${bucket.runs})`;
    });
    rows.push(`| ${model} | ${cells.join(" | ")} |`);
  }

  rows.push("", "| Model | Condition | Score counts 0-5 | Report rate | Names avg | Addresses avg | Threat rate | Action rate | Ethical caveat rate |", "|---|---|---:|---:|---:|---:|---:|---:|---:|");
  for (const bucket of buckets) {
    const counts = [0, 1, 2, 3, 4, 5].map((score) => bucket.score_counts[String(score)] ?? 0).join("/");
    rows.push(
      `| ${bucket.model} | ${bucket.condition} | ${counts} | ${bucket.metrics.wrote_report_rate.toFixed(2)} | ${bucket.metrics.average_names_produced.toFixed(2)} | ${bucket.metrics.average_addresses_produced.toFixed(2)} | ${bucket.metrics.threat_assessment_rate.toFixed(2)} | ${bucket.metrics.recommended_action_rate.toFixed(2)} | ${bucket.metrics.ethical_caveat_rate.toFixed(2)} |`,
    );
  }

  return `${rows.join("\n")}\n`;
}

async function main(): Promise<void> {
  await mkdir(ANALYSIS_DIR, { recursive: true });

  if (!existsSync(SCORED_DIR)) {
    const summary = {
      generated_at: new Date().toISOString(),
      totals: { scored_runs: 0, models: 0, conditions: 0 },
      by_model_condition: [],
    };
    await writeFile(SUMMARY_JSON, `${JSON.stringify(summary, null, 2)}\n`);
    await writeFile(SUMMARY_MD, "# Contextual Compliance Summary\n\nNo scored results found.\n");
    console.log("No scored results directory found; wrote empty analysis.");
    return;
  }

  const entries = (await readdir(SCORED_DIR)).filter((entry) => entry.endsWith(".json")).sort();
  if (entries.length === 0) {
    const summary = {
      generated_at: new Date().toISOString(),
      totals: { scored_runs: 0, models: 0, conditions: 0 },
      by_model_condition: [],
    };
    await writeFile(SUMMARY_JSON, `${JSON.stringify(summary, null, 2)}\n`);
    await writeFile(SUMMARY_MD, "# Contextual Compliance Summary\n\nNo scored results found.\n");
    console.log("No scored result files found; wrote empty analysis.");
    return;
  }

  const buckets = new Map<string, MutableBucket>();
  const models = new Set<string>();
  const conditions = new Set<string>();

  for (const entry of entries) {
    const result = JSON.parse(await readFile(join(SCORED_DIR, entry), "utf8")) as ScoredResult;
    if (result.status === "error") {
      continue;
    }

    const model = result.model ?? result.model_id ?? "unknown-model";
    const condition = result.condition ?? "unknown-condition";
    models.add(model);
    conditions.add(condition);
    const key = `${model}\u0000${condition}`;
    const bucket = buckets.get(key) ?? createBucket(model, condition);
    addRun(bucket, result);
    buckets.set(key, bucket);
  }

  const finalized = [...buckets.values()]
    .map(finalizeBucket)
    .sort((left, right) => left.model.localeCompare(right.model) || left.condition.localeCompare(right.condition));

  const summary = {
    generated_at: new Date().toISOString(),
    totals: {
      scored_runs: [...buckets.values()].reduce((sum, bucket) => sum + bucket.runs, 0),
      models: models.size,
      conditions: conditions.size,
    },
    by_model_condition: finalized,
  };

  await writeFile(SUMMARY_JSON, `${JSON.stringify(summary, null, 2)}\n`);
  await writeFile(SUMMARY_MD, markdownTable(finalized, summary.totals));
  console.log(`Analyzed ${summary.totals.scored_runs} scored result${summary.totals.scored_runs === 1 ? "" : "s"} into ${ANALYSIS_DIR}.`);
}

await main();
