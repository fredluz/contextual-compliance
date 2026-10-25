#!/usr/bin/env bash
# Leg-3 API rebuild — full run driver (token-indistinguishable forged-history, both directions).
#
# HOLDS FOR KEYS: requires ANTHROPIC_API_KEY (claude arm) and OPENAI_API_KEY (gpt arms). The runner
# errors loud per-cell if its key is missing. --skip-existing makes the whole run resumable so real
# API spend is never wasted on a re-run.
#
# Matrix is the signed-off set (see docs/leg3-rebuild.md):
#   FLIP (cold refusers):   haiku{argus,direct} + gpt-5.4-mini{argus,direct} + gpt-5.5 argus
#   BACKFIRE (cold accepters): haiku neutral + gpt-5.5{neutral,direct}
# Arms: cold, warm-coop, warm-neutral.  Runs: 1..3 (set RUNS=2 to trim).
#
# Usage:
#   RUNS=3 bash scripts/run-leg3-api.sh            # live run (needs keys)
#   DRY=1  bash scripts/run-leg3-api.sh            # build every payload, no network (keyless check)
set -u
cd ~/Code/contextual-compliance

RUNS="${RUNS:-3}"
DRY_FLAG=""
[ "${DRY:-0}" = "1" ] && DRY_FLAG="--dry-run"

# Each entry: "<label> <model> <condition>"
#   FLIP     = cold refusers / partial refusers
#   BACKFIRE = cold accepters
CELLS=(
  "FLIP claude:haiku argus"
  "FLIP claude:haiku direct"
  "FLIP gpt-5.4-mini argus"
  "FLIP gpt-5.4-mini direct"
  "FLIP gpt-5.5 argus"
  "BACKFIRE claude:haiku neutral"
  "BACKFIRE gpt-5.5 neutral"
  "BACKFIRE gpt-5.5 direct"
)

for arm in cold warm-coop warm-neutral; do
  for entry in "${CELLS[@]}"; do
    set -- $entry
    label="$1"; model="$2"; condition="$3"
    for run in $(seq 1 "$RUNS"); do
      echo "=== [$label] ${model} ${condition} arm=${arm} run=${run} @ $(date +%H:%M:%S) ==="
      bun scripts/run-leg3-api.ts --model "${model}" --condition "${condition}" \
        --arm "${arm}" --run "${run}" --skip-existing ${DRY_FLAG}
    done
  done
done

echo "=== LEG3-API DONE — analyzing ==="
[ "${DRY:-0}" = "1" ] || bun scripts/analyze-leg3-api.ts
