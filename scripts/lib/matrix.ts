import { CONDITIONS, type CliFilters, type MatrixCell, type ModelSpec } from "./types";

export const MODELS: ModelSpec[] = [
  { id: "claude:sonnet", backend: "claude", cliModel: "claude:sonnet" },
  { id: "openai-codex/gpt-5.5", backend: "omp", cliModel: "openai-codex/gpt-5.5" },
  { id: "opencode-go/deepseek-v4-flash", backend: "omp", cliModel: "opencode-go/deepseek-v4-flash" },
  { id: "opencode-go/deepseek-v4-pro", backend: "omp", cliModel: "opencode-go/deepseek-v4-pro" },
  { id: "opencode-go/glm-5", backend: "omp", cliModel: "opencode-go/glm-5" },
  { id: "opencode-go/glm-5.1", backend: "omp", cliModel: "opencode-go/glm-5.1" },
  { id: "opencode-go/kimi-k2.5", backend: "omp", cliModel: "opencode-go/kimi-k2.5" },
  { id: "opencode-go/kimi-k2.6", backend: "omp", cliModel: "opencode-go/kimi-k2.6" },
  { id: "opencode-go/kimi-k2.7-code", backend: "omp", cliModel: "opencode-go/kimi-k2.7-code" },
  { id: "opencode-go/mimo-v2-pro", backend: "omp", cliModel: "opencode-go/mimo-v2-pro" },
  { id: "opencode-go/mimo-v2.5", backend: "omp", cliModel: "opencode-go/mimo-v2.5" },
  { id: "opencode-go/mimo-v2.5-pro", backend: "omp", cliModel: "opencode-go/mimo-v2.5-pro" },
  { id: "opencode-go/minimax-m2.5", backend: "omp", cliModel: "opencode-go/minimax-m2.5" },
  { id: "opencode-go/minimax-m2.7", backend: "omp", cliModel: "opencode-go/minimax-m2.7" },
  { id: "opencode-go/minimax-m3", backend: "omp", cliModel: "opencode-go/minimax-m3" },
  { id: "opencode-go/qwen3.5-plus", backend: "omp", cliModel: "opencode-go/qwen3.5-plus" },
  { id: "opencode-go/qwen3.6-plus", backend: "omp", cliModel: "opencode-go/qwen3.6-plus" },
  { id: "opencode-go/qwen3.7-max", backend: "omp", cliModel: "opencode-go/qwen3.7-max" },
  { id: "opencode-go/qwen3.7-plus", backend: "omp", cliModel: "opencode-go/qwen3.7-plus" },
];

export function buildMatrix(filters: CliFilters): MatrixCell[] {
  const cells: MatrixCell[] = [];

  for (const model of MODELS) {
    if (filters.model !== undefined && filters.model !== model.id && filters.model !== model.cliModel) {
      continue;
    }

    for (const run of [1, 2, 3]) {
      if (filters.run !== undefined && filters.run !== run) {
        continue;
      }

      for (const condition of CONDITIONS) {
        if (filters.condition !== undefined && filters.condition !== condition) {
          continue;
        }

        cells.push({
          model,
          condition,
          run,
          runId: `${model.id}__${condition}__run${run}`,
        });
      }
    }
  }

  return cells;
}
