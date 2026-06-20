#!/usr/bin/env bash
# Warm arms (warm-coop + warm-neutral) for codex-spark + gpt-5.4 — fill the context-trick gap
# so we can see whether the blind-complier (spark) and the full model (5.4) eval-hack under
# fabricated history like gpt-5.5 does. All 3 framings (argus kept in data, excluded from views).
# spark FIRST (reliable Codex CLI); gpt-5.4 second (OpenRouter, watch for child-kill-hang). NOT nano.
# 2 models x 3 framings x 2 arms x 3 runs = 36 cells. Serial, --skip-existing.
cd ~/Code/contextual-compliance || exit 1
for m in openai-codex/gpt-5.3-codex-spark openrouter/openai/gpt-5.4; do
  for c in argus neutral direct; do
    for arm in warm-coop warm-neutral; do
      for r in 1 2 3; do
        echo "=== $m | $c | $arm | run$r ==="
        bun scripts/run-cell.ts --model "$m" --condition "$c" --run "$r" --arm "$arm" --skip-existing --timeout 600
      done
    done
  done
done
echo WARM-EXTRA-COMPLETE
