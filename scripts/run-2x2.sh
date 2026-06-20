#!/usr/bin/env bash
# 2x2 confound-break: disentangle analyst-persona (system prompt) from task wording.
# Corners run here: persona_blunt (persona + blunt task) and bare_query (no persona + soft task).
# direct (no persona + blunt) and neutral (persona + soft) already exist on disk.
set -uo pipefail
cd "$(dirname "$0")/.."
MODELS=(claude:haiku claude:sonnet claude:opus)   # gpt-5.4 dropped (slow OpenRouter, Fred Jun 20)
CONDS=(persona_blunt bare_query)
for m in "${MODELS[@]}"; do
  for c in "${CONDS[@]}"; do
    for r in 1 2 3; do
      echo "=== $m | $c | run $r ==="
      bun scripts/run-cell.ts --model "$m" --condition "$c" --laundering explicit --run "$r" \
        --dataset real --timeout 900 --skip-existing
    done
  done
done
echo "=== 2x2 RUN COMPLETE ==="
