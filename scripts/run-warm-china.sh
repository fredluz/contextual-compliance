#!/usr/bin/env bash
# Warm arms (warm-coop + warm-neutral) for the Chinese models that were only ever run COLD.
# Fills the cross-national gap in the backfire finding: the "fake context flips models to
# refusal" effect was only ever demonstrated on Western models + GLM-5.2. These three routes
# complied (or, for kimi, refused) cold but never saw the fabricated history. Do they react
# to the obviously-fake injected context the way GPT-5.5 / analyst-Claude did?
#
# Scope: Direct + Analyst (neutral) framings only — the two published headline framings.
#        argus is intentionally OMITTED here (excluded from displayed views anyway).
# 3 models x 2 framings x 2 arms x 3 runs = 36 cells. Serial, --skip-existing so it's resumable.
cd ~/Code/contextual-compliance || exit 1
for m in deepseek/deepseek-v4-flash opencode-go/deepseek-v4-pro opencode-go/kimi-k2.7-code; do
  for c in neutral direct; do
    for arm in warm-coop warm-neutral; do
      for r in 1 2 3; do
        echo "=== $m | $c | $arm | run$r ==="
        bun scripts/run-cell.ts --model "$m" --condition "$c" --run "$r" --arm "$arm" --skip-existing --timeout 600
      done
    done
  done
done
echo WARM-CHINA-COMPLETE
