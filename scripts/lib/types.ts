export const CONDITIONS = ["argus", "neutral", "direct"] as const;
export type Condition = (typeof CONDITIONS)[number];

export const BACKENDS = ["omp", "claude"] as const;
export type Backend = (typeof BACKENDS)[number];

export type RunStatus = "success" | "error" | "timeout";

export type ModelArchitecture = "dense" | "moe" | "undisclosed";

export interface ModelSpec {
  /** Display id used in run ids and CLI filters. */
  id: string;
  backend: Backend;
  /** Concrete CLI model argument. */
  cliModel: string;
  country?: "Europe" | "China" | "USA";
  family?: string;
  paramsTotalB?: number | null;
  paramsActiveB?: number | null;
  architecture?: ModelArchitecture;
  release_date?: string;
  providerRoute?: "OpenRouter" | "opencode-go" | "openai-codex" | "Claude CLI";
  closedFirstParty?: boolean;
}

export interface MatrixCell {
  model: ModelSpec;
  condition: Condition;
  run: number;
  runId: string;
}

export interface CliFilters {
  model?: string;
  condition?: Condition;
  run?: number;
  timeoutSeconds: number;
}

export interface PreparedWorkspace {
  workspacePath: string;
  baselineFiles: Map<string, string>;
}

export interface CommandResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
  timedOut: boolean;
  durationMs: number;
}

export interface RunnerCommand {
  argv: string[];
  redactedArgv: string[];
  cwd: string;
}

export interface RunnerInput {
  model: ModelSpec;
  condition: Condition;
  workspacePath: string;
}

export interface RunnerExecution {
  command: RunnerCommand;
  result: CommandResult;
}

export interface ToolCallCapture {
  tool: string;
  input?: unknown;
  output_summary?: string;
}

export interface RawResult {
  run_id: string;
  model: string;
  backend: Backend;
  condition: Condition;
  run: number;
  status: RunStatus;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  command: string[];
  workspace_path: string;
  exit_code: number | null;
  timeout_seconds: number;
  stdout: string;
  stderr: string;
  tool_calls: ToolCallCapture[];
  files_written: string[];
  final_text_response: string;
  error?: string;
}
