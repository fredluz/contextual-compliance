import { join } from "node:path";
import { CONDITIONS } from "./lib/types";
import { MODELS } from "./lib/matrix";

const args = parseArgs(Bun.argv.slice(2));
const runCellPath = new URL("./run-cell.ts", import.meta.url).pathname;

for (const run of [1, 2, 3]) {
  if (args.run !== undefined && args.run !== run) {
    continue;
  }

  for (const model of MODELS) {
    if (args.model !== undefined && args.model !== model.id && args.model !== model.cliModel) {
      continue;
    }

    for (const condition of CONDITIONS) {
      if (args.condition !== undefined && args.condition !== condition) {
        continue;
      }

      const home = Bun.env.HOME ?? "";
      const env = {
        ...Bun.env,
        PATH: [join(home, ".bun", "bin"), join(home, ".clawd", "bin"), Bun.env.PATH ?? ""].filter((part) => part.length > 0).join(":"),
      };
      const argv = [
        process.execPath,
        runCellPath,
        "--model",
        model.cliModel,
        "--condition",
        condition,
        "--dataset",
        args.dataset,
        "--run",
        String(run),
        "--timeout",
        String(args.timeoutSeconds),
      ];
      if (args.skipExisting) {
        argv.push("--skip-existing");
      }

      const proc = Bun.spawn(argv, { stdout: "pipe", stderr: "pipe", stdin: "ignore", env });
      const [stdout, stderr, exitCode] = await Promise.all([
        new Response(proc.stdout).text(),
        new Response(proc.stderr).text(),
        proc.exited,
      ]);
      if (stdout.trim().length > 0) {
        console.log(stdout.trim());
      }
      if (stderr.trim().length > 0) {
        console.error(stderr.trim());
      }
      if (exitCode !== 0) {
        console.error(JSON.stringify({ model: model.cliModel, condition, run, exit_code: exitCode }));
      }
    }
  }
}

type Args = {
  model?: string;
  condition?: string;
  run?: number;
  dataset: string;
  timeoutSeconds: number;
  skipExisting: boolean;
};

function parseArgs(argv: string[]): Args {
  const parsed: Args = { dataset: "real", timeoutSeconds: 300, skipExisting: false };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--model") {
      parsed.model = valueAfter(argv, ++index, arg);
    } else if (arg === "--condition") {
      parsed.condition = valueAfter(argv, ++index, arg);
    } else if (arg === "--dataset") {
      parsed.dataset = valueAfter(argv, ++index, arg);
    } else if (arg === "--run") {
      parsed.run = Number.parseInt(valueAfter(argv, ++index, arg), 10);
    } else if (arg === "--timeout" || arg === "--timeout-seconds") {
      parsed.timeoutSeconds = Number.parseInt(valueAfter(argv, ++index, arg), 10);
    } else if (arg === "--skip-existing") {
      parsed.skipExisting = true;
    } else if (arg === "--help" || arg === "-h") {
      console.log("Usage: bun scripts/run.ts [--model <id>] [--condition <argus|neutral|direct>] [--run <n>] [--dataset phase1|real] [--skip-existing] [--timeout 300]");
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return parsed;
}

function valueAfter(argv: string[], index: number, flag: string): string {
  const value = argv[index];
  if (!value || value.startsWith("--")) {
    throw new Error(`${flag} requires a value`);
  }
  return value;
}
