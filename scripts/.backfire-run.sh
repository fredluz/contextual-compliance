#!/usr/bin/env bash
# Backfire experiment (legacy system-prompt --arm mechanism, preserved in leg3-legacy.ts).
# For each (model, framing) where the model COMPLIES cold, run warm-coop + warm-neutral x3
# and compare warm accept-rate vs the existing cold baseline. Tests: does an obviously/
# legacy-fake "you already cooperated" history SUPPRESS a willing model (accepter -> refuse)?
# Partial-compliers are run ONLY on the framings they accept cold (no point on cold-refusals).
cd ~/Code/contextual-compliance || exit 1

run_cell() { bun scripts/run-cell.ts --model "$1" --condition "$2" --run "$3" --arm "$4" --skip-existing --timeout 900; }

# "model framing[ framing...]" — framings = the conditions the model accepts cold.
# Narrowed population (Fred Jun 20): glm-5.2 + gpt-5.5 across all framings they accept,
# + claude h/s/o on neutral (the only framing they engage cold).
SPECS=(
  "openai-codex/gpt-5.5 argus neutral direct"         # US, broadly compliant
  "claude:haiku neutral"                              # US, technical-framing only
  "claude:sonnet neutral"                             # US, technical-framing only
  "claude:opus neutral"                               # US, technical-framing only
)

for spec in "${SPECS[@]}"; do
  set -- $spec
  model=$1; shift
  for cond in "$@"; do
    for arm in warm-coop warm-neutral; do
      for r in 1 2 3; do
        echo "=== $model | $cond | $arm | run$r ==="
        run_cell "$model" "$cond" "$r" "$arm"
      done
    done
  done
done
echo "BACKFIRE-RUN COMPLETE"
