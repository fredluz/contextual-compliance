#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/Code/contextual-compliance"
LOG="results/size-probe-3run-detached.log"
FOLLOW_LOG="results/followups/moral-followups.log"

mkdir -p results/followups
{
  echo "MORAL FOLLOWUPS watcher start: $(date)"
  echo "Waiting for original size-probe DONE and OPUS DONE markers..."
  echo "Scope: ALL tested models in results/raw that materially engaged with the task (big + small; representative run per model×condition)."
  echo "Question mode: one question at a time; each later question includes only the run excerpt plus previous answers."
} >> "$FOLLOW_LOG"

while ! grep -q '^DONE:' "$LOG" 2>/dev/null; do
  sleep 10
done
while ! grep -q '^OPUS DONE:' "$LOG" 2>/dev/null; do
  sleep 10
done

{
  echo "Markers seen: $(date)"
  echo "Running moral followups for ALL representative task-doing cells in results/raw."
} >> "$FOLLOW_LOG"

bun scripts/ask-moral-followups.ts >> "$FOLLOW_LOG" 2>&1

echo "MORAL FOLLOWUPS DONE: $(date)" >> "$FOLLOW_LOG"
