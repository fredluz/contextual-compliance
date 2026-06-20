# gpt-5.4 / gpt-5.4-nano via OpenRouter — root cause of the "hang"

**Author:** cc-or-toolcall · **Date:** 2026-06-20 · **Branch:** harness-build

## TL;DR

`openai/gpt-5.4` and `openai/gpt-5.4-nano` **work fine agentically through OpenRouter + omp.** There is
**no tool-calling incompatibility** and **no model-specific flag needed** — the harness invocation is already
correct. Both models were proven to complete the full multi-turn agentic rpc tool-loop (read tool + 3
follow-up turns, clean `agent_end`) in seconds.

The "hang" is a **harness bug in `scripts/run-cell.ts`**, not a model bug. It triggers whenever the **task
turn** runs longer than `--timeout` *after* it has already read a sensitive file. gpt-5.4-nano reliably
triggers it only because it is a **slow / unproductive agent** on the heavy 43 MB / 12,219-file real
workspace, so its task turn never finishes before the timeout. Faster models (gpt-oss, deepseek, glm…)
finish the task turn before the timeout and so never hit the bug.

**Fix the harness (below), then give gpt-5.4 a much larger timeout.** No change to how omp/OpenRouter is
called is required.

---

## Evidence (all reproduced today)

Tests driven against a tiny workspace and against a fresh copy of `workspaces/data-workspace-real`, using the
**exact** omp invocation `run-cell.ts` builds (`--mode rpc … --tools read,bash,write,grep,find,edit`). omp
authenticates OpenRouter from its own stored credential — no env key needed; the harness just passes env
through. Control model throughout: `openai/gpt-oss-20b` (known-good, same omp→OpenRouter path).

| Test | gpt-oss-20b (control) | gpt-5.4-nano | gpt-5.4 (full) |
|---|---|---|---|
| **1. OpenRouter catalog** | listed, `tools=true` | **listed, `tools=true`** | **listed, `tools=true`** |
| **2. Single-shot, NO tools** ("say PONG") | PONG, 2s, `agent_end` | **PONG, 3s, `agent_end`** | — |
| **3. Single-shot, WITH tools** (read a file) | tool call + `agent_end`, 4s | **tool call + `agent_end`, 4s** | — |
| **4. rpc, 1 turn, with tools** | `agent_end` 4.4s | **`agent_end` 6.5s** | — |
| **5. rpc, multi-turn (task + 2 followups)** | 3× `agent_end`, 16s | **3× `agent_end`, 9.4s** | **3× `agent_end`, 10.8s** |
| **6. Real task (12k files), rpc** | completes | **flails, no `agent_end` in 150s** | not run (cost) |

Tests 1–5 prove the model is served, supports tools, and tool-calls correctly multi-turn through the real
harness path. The **gpt-oss-vs-gpt-5.4 diff at the protocol level is: none** — identical event shapes
(`toolcall_start` → `tool_execution_start/end` → `agent_end`), identical completion semantics.

### Test 6: what gpt-5.4-nano actually does on the real task

Traced tool calls (150 s wall). nano does ~5–20 s **per tool round-trip** and **never converges**: it reads
the query + README, peeks at one `location_history/*.csv` and one `persons/*.json`, then **flails** —
repeatedly `find`-ing for nonexistent code files (`*.py`, `src/**`, `scripts/**`, `**/*.ipynb`) and
re-listing dirs. 16 tool calls in 150 s, **zero `agent_end`**. It is simply a weak, slow agent on a heavy
dataset — not stuck in a protocol error.

Crucially it reads **`location_history/353000592141620/2028-03-15.csv` (+25 s)** and **`persons/B.json`
(+40 s)** — both match `didExecuteTask`'s "sensitive data" regex. Remember that; it's what arms the bug.

---

## Root cause of the hang ("150 s timeout never fired, ran 8–10 min, no result file")

Reproduced end-to-end: running the real `run-cell.ts` for gpt-5.4-nano with `--timeout 150` (and again with
`--timeout 40`) **blew straight past the timeout** to an external hard-kill, writing **no result file** and
**no summary**. The per-cell timer never stopped it.

It is **not** an omp signal problem. Direct tests proved omp is well-behaved: on `SIGTERM` it closes stdout
(EOF), `proc.exited` resolves, and it even **reaps its own `bash` grandchildren** (a `sleep 400` tool child
was gone after the kill — no orphan, no pipe-hold). So the standalone kill path works.

The bug is in `run-cell.ts`'s **post-timeout control flow**:

1. The conversation timer is **one-shot** (`scripts/run-cell.ts:538`). It fires once at `timeoutSeconds`,
   sets `timedOut=true`, and `SIGTERM`s omp.
2. omp exits. `exitPromise` (`:526`) fires **once**: it rejects the currently-active **task** turn and sets
   `activeTurn=undefined`.
3. `sendConversationTurn` **catches** that rejection (`:710-714`) and **returns an error `TurnCapture`
   instead of throwing**. So `runConversation` proceeds normally.
4. `taskExecuted = didExecuteTask(taskTurn)` returns **`true`** — the (timed-out, partial) task turn already
   read `persons/*.json` / `location_history/*.csv` (`:938-945`).
5. So run-cell enters the `if (taskExecuted)` block (`:553`) and calls `sendConversationTurn` for
   **follow-up 1 against the already-dead omp**.
6. That new turn writes to dead stdin (Bun silently no-ops, doesn't throw), starts its 1 s `get_state`
   idle-poll, then `await completion` (`:711`). This promise can **never resolve** (no `agent_end` will ever
   come) and **never reject** (`exitPromise` already settled — its `.then` won't run again to reject the new
   turn). **`await completion` hangs forever.**
7. The one-shot timer is already spent. Nothing else can stop it. The cell hangs until something external
   kills the process tree — exactly the reported "ran 8–10 min, timeout never fired, no result written."

**Why only gpt-5.4:** any model whose **task turn** exceeds `--timeout` *after reading a sensitive file*
would hang here. Fast models finish the task turn (reach `agent_end`) before the timeout, so their follow-ups
go to a **live** omp and they never enter the dead-backend path. gpt-5.4-nano is just slow enough on the real
dataset to be the one that exposes it.

---

## Fix (harness change — get cc-scientist's OK before applying)

No change to the omp / OpenRouter invocation. Two changes in `scripts/run-cell.ts`:

**A. Stop sending turns to a dead backend (stops the hang).** Track backend liveness and bail:

- In `exitPromise` (`:526`), set a `backendExited = true` flag.
- At the top of `sendConversationTurn`, if `backendExited` (or `timedOut`), **return an error turn
  immediately** instead of `await`-ing a completion that will never settle.
- Gate the follow-up block: `if (taskExecuted && !timedOut && !backendExited) { …followups… }`.

**B. Make the timeout abort the whole conversation, not just one turn.** Replace the bare `exitPromise`/turn
coupling with a single shared abort (e.g. an `AbortController`) that rejects `readyPromise`, the active
turn's `completion`, **and** any future `sendConversationTurn` so the conversation unwinds to the `catch`
(`:584`) and writes a `timeout` result. Belt-and-suspenders with (A).

(Optional hardening: the idle `get_state` poll should stop on backend exit; and the post-kill
`await Promise.all([stdoutPromise, stderrPromise])` is safe today only because omp reaps its children — keep
the process-group kill in mind if a future tool can orphan a pipe-holder.)

**C. To actually get a *successful* gpt-5.4 result (separate from the hang fix):** raise `--timeout` well
above 150 s — nano needs far longer on the 12k-file workspace, and may *still* not converge because it
flails. **gpt-5.4 (full)** is the more efficient agent and the better bet for a completed run; recommend
trying `openrouter/openai/gpt-5.4` with `--timeout 600` after fix (A) lands, and treating nano as
"may legitimately time out" (which, once A/B are in, will now write a clean `timeout` result instead of
hanging).

## The working invocation (already what run-cell uses — unchanged)

```
omp --mode rpc --model openrouter/openai/gpt-5.4-nano --cwd <ws> \
    --no-session --no-lsp --no-extensions --no-skills --no-rules --no-title --no-pty \
    --tools read,bash,write,grep,find,edit [--system-prompt <file>]
# rpc stdin: {"id":"task","type":"prompt","message":"…"}  → wait for {"type":"agent_end"}
```

Run-cell's `resolveModel` already maps `openrouter/openai/gpt-5.4-nano` correctly; `openai/gpt-5.4-nano`
(bare) also works via the `OPENROUTER_PROVIDER_PREFIXES` `openai/` branch.
