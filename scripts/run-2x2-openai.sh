#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
MODELS=(openai-codex/gpt-5.5 openai-codex/gpt-5.4-mini)
CONDS=(persona_blunt bare_query)
for m in "${MODELS[@]}"; do for c in "${CONDS[@]}"; do for r in 1 2 3; do
  echo "=== $m | $c | run $r ==="
  bun scripts/run-cell.ts --model "$m" --condition "$c" --laundering explicit --run "$r" --dataset real --timeout 900 --skip-existing
done; done; done
echo "=== 2x2 OPENAI COMPLETE ==="
