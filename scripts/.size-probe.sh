#!/bin/bash
cd ~/Code/contextual-compliance
LOG=results/size-probe-3run-detached.log
echo "DETACHED size-axis probe — 5 models × 3 framings × 3 runs, dataset=real, --skip-existing" >> "$LOG"
echo "start: $(date '+%A %H:%M:%S')" >> "$LOG"
MODELS=("openai-codex/gpt-5.4-mini" "claude:haiku" "qwen/qwen3.7-plus" "qwen/qwen3-8b" "qwen/qwen3-4b")
for m in "${MODELS[@]}"; do
  for c in argus neutral direct; do
    for r in 1 2 3; do
      echo "--- $(date '+%H:%M:%S') $m / $c / run$r ---" >> "$LOG"
      bun scripts/run-cell.ts --model "$m" --condition "$c" --run "$r" --dataset real --skip-existing --timeout 360 >> "$LOG" 2>&1
    done
  done
done
echo "DONE: $(date '+%H:%M:%S')" >> "$LOG"
