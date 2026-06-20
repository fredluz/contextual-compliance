#!/usr/bin/env bash
# gpt-5.4 + gpt-5.4-nano via OpenRouter (proven working by cc-or-toolcall; no codex path exists
# for these two). 2 models x 3 conditions x 3 runs = 18 cold cells. Serial, --skip-existing.
# Waits for the glm backfire run to finish first so only ONE backend runs at a time (RAM-fragile box).
cd ~/Code/contextual-compliance || exit 1

waited=0
while tmux has-session -t cc-backfire-glm 2>/dev/null; do
  if [ "$waited" -ge 1800 ]; then
    echo "WAIT-TIMEOUT (${waited}s): proceeding even though cc-backfire-glm is still up"
    break
  fi
  echo "waiting for cc-backfire-glm to finish... ${waited}s"
  sleep 30
  waited=$((waited + 30))
done

for m in openrouter/openai/gpt-5.4 openrouter/openai/gpt-5.4-nano; do
  for c in argus neutral direct; do
    for r in 1 2 3; do
      echo "=== $m | $c | run$r ==="
      bun scripts/run-cell.ts --model "$m" --condition "$c" --run "$r" --skip-existing --timeout 600
    done
  done
done
echo GPT54-COMPLETE
