#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/Code/contextual-compliance"
LOG="results/size-probe-3run-detached.log"
WAIT_FOR="results/raw/qwen_qwen3.7-plus_direct_explicit_real_3.json"

echo "--- $(date '+%H:%M:%S') watcher: waiting for qwen/qwen3.7-plus direct run3 before opus; leaving small-qwen queue running ---" >> "$LOG"
while [[ ! -f "$WAIT_FOR" ]]; do
  sleep 5
done

echo "--- $(date '+%H:%M:%S') watcher: qwen/qwen3.7-plus complete; starting claude:opus while size-probe continues ---" >> "$LOG"
for c in argus neutral direct; do
  for r in 1 2 3; do
    echo "--- $(date '+%H:%M:%S') claude:opus / $c / run$r ---" >> "$LOG"
    bun scripts/run-cell.ts --model "claude:opus" --condition "$c" --run "$r" --dataset real --skip-existing --timeout 360 >> "$LOG" 2>&1
  done
done
echo "OPUS DONE: $(date '+%H:%M:%S')" >> "$LOG"
