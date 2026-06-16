import { join } from "node:path";
import type { CommandResult, RunnerCommand, RunnerExecution, RunnerInput } from "../types";
import { systemPromptFor, userMessageFor } from "../prompts";

export function buildClaudeCommand(input: RunnerInput): RunnerCommand {
  const argv = [
    join(Bun.env.HOME ?? "", ".clawd", "bin", "claude"),
    "-p",
    "--model",
    input.model.cliModel,
    "--output-format",
    "stream-json",
    "--verbose",
    "--no-session-persistence",
    "--safe-mode",
    "--disable-slash-commands",
    "--permission-mode",
    "acceptEdits",
    "--allowedTools",
    "Read,Write,Edit,Bash",
    "--add-dir",
    input.workspacePath,
  ];

  const redactedArgv = [...argv];
  const systemPrompt = systemPromptFor(input.condition);
  if (systemPrompt !== undefined) {
    argv.push("--system-prompt", systemPrompt);
    redactedArgv.push("--system-prompt", `[system-prompt:${input.condition}]`);
  }

  const userMessage = userMessageFor(input.condition);
  argv.push(userMessage);
  redactedArgv.push(userMessage);

  return { argv, redactedArgv, cwd: input.workspacePath };
}

export async function runClaude(input: RunnerInput, timeoutSeconds: number): Promise<RunnerExecution> {
  const command = buildClaudeCommand(input);
  const result = await executeCommand(command, timeoutSeconds);
  return { command, result };
}

async function executeCommand(command: RunnerCommand, timeoutSeconds: number): Promise<CommandResult> {
  const started = Date.now();
  let timedOut = false;
  let timeout: Timer | undefined;

  try {
    const proc = Bun.spawn(command.argv, {
      cwd: command.cwd,
      stdout: "pipe",
      stderr: "pipe",
      stdin: "ignore",
      env: sanitizedEnvironment(),
    });

    const stdoutPromise = new Response(proc.stdout).text();
    const stderrPromise = new Response(proc.stderr).text();

    timeout = setTimeout(() => {
      timedOut = true;
      proc.kill("SIGTERM");
      setTimeout(() => proc.kill("SIGKILL"), 5_000).unref?.();
    }, timeoutSeconds * 1_000);

    const exitCode = await proc.exited;
    const [stdout, stderr] = await Promise.all([stdoutPromise, stderrPromise]);
    return { stdout, stderr, exitCode, timedOut, durationMs: Date.now() - started };
  } catch (error) {
    const message = error instanceof Error ? error.stack ?? error.message : String(error);
    return { stdout: "", stderr: message, exitCode: null, timedOut, durationMs: Date.now() - started };
  } finally {
    clearTimeout(timeout);
  }
}

function sanitizedEnvironment(): Record<string, string> {
  const env: Record<string, string> = {};
  for (const [key, value] of Object.entries(Bun.env)) {
    if (value !== undefined) {
      env[key] = value;
    }
  }

  const home = env.HOME ?? "";
  env.PATH = [join(home, ".bun", "bin"), join(home, ".clawd", "bin"), env.PATH ?? ""].filter((part) => part.length > 0).join(":");

  env.CLAUDE_CODE_SAFE_MODE = "1";
  return env;
}
