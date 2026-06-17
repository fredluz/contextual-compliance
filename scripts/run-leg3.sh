#!/usr/bin/env bash
# Leg-3 refusal-flip run: 7 refuser pairs x 2 warm arms x 3 runs = 42 cells, serial.
# Refuser population from leg-1: Claude{haiku,sonnet,opus} x {argus,direct} + gpt-5.4-mini x argus.
set -u
cd ~/Code/contextual-compliance

PAIRS=(
  "claude:haiku argus"
  "claude:haiku direct"
  "claude:sonnet argus"
  "claude:sonnet direct"
  "claude:opus argus"
  "claude:opus direct"
  "openai-codex/gpt-5.4-mini argus"
)

for arm in warm-coop warm-neutral; do
  for pair in "${PAIRS[@]}"; do
    model="${pair%% *}"
    condition="${pair##* }"
    echo "=== LEG3 ${model} ${condition} arm=${arm} @ $(date +%H:%M:%S) ==="
    bun scripts/run.ts --model "${model}" --condition "${condition}" --arm "${arm}" --dataset real --timeout 900 --skip-existing
  done
done
echo "=== LEG3 DONE ==="
