# Persistent multi-turn mechanism investigation

Branch/context: `harness-build`. Investigation only; no harness rebuild in this document.

## Bottom line

Both active backends can be driven as one live process with retained in-process context, but not through the current `run-cell.ts` one-shot path.

- Claude CLI: use one `claude -p` process with `--input-format stream-json --output-format stream-json --verbose`, keep stdin open, write one JSONL user-message object per turn, and treat each `type:"result"` stdout event as the end of one external user turn.
- OMP: use one `omp --mode rpc` process, keep stdin open, write one JSONL RPC `prompt` command per turn, and wait until the agent is idle (`agent_end` or `get_state.isStreaming === false`) before sending the next dependent prompt.
- Do not use `--continue` / `--resume` for this experiment; those reload stored sessions. The proven mechanisms below are live stdin/stdout protocols on one still-running process.

## 1. Current harness is one-shot

Active path: `scripts/run-cell.ts`.

Evidence:

- `scripts/run-cell.ts:112-115` prepares the workspace, reads the scenario, builds `systemPrompt` and one `userMessage`, then calls `runModel(...)` once.
- OMP branch at `scripts/run-cell.ts:414-436` builds:

  ```text
  omp -p --model <model> --cwd <workspace> --mode json --no-session --no-lsp --tools read,bash,write,grep,find,edit [--system-prompt <file>] <userMessage>
  ```

- Claude branch at `scripts/run-cell.ts:438-461` builds:

  ```text
  claude -p --model <model> --output-format stream-json --verbose --no-session-persistence --safe-mode --strict-mcp-config --setting-sources "" --allowedTools Bash,Read,Write,Glob,Grep --dangerously-skip-permissions --add-dir <workspace> [--system-prompt <text>] -- <userMessage>
  ```

- `scripts/run-cell.ts:474-486` spawns with `stdin: "ignore"`, `stdout: "pipe"`, `stderr: "pipe"`.
- `scripts/run-cell.ts:487-498` buffers full stdout/stderr, awaits `proc.exited`, then returns one `CommandResult`.
- `scripts/run-cell.ts:120-149` parses the whole process output once into one `tool_calls` array and one `final_text_response`.
- `scripts/run-cell.ts:196-198` removes the temp workspace after the one run finishes.

Legacy runner files mirror the same lifecycle:

- `scripts/lib/runners/claude.ts:5-36`, `:51-70`: one `claude -p` argv, `stdin:"ignore"`, await process exit.
- `scripts/lib/runners/omp.ts:5-34`, `:49-68`: one `omp -p --mode json` argv, `stdin:"ignore"`, await process exit.

Current capture is process-scoped, not turn-scoped:

- `scripts/lib/capture.ts:37-112` parses one stdout blob and returns one `tool_calls` plus one `final_text_response`.
- It already understands useful events: OMP `tool_execution_start` / `tool_execution_end`, Claude/OMP message `tool_use` / `tool_result`, `message_end` / `turn_end`, and Claude `result`.

## 2. Claude CLI: proven live multi-turn protocol

Observed CLI version:

```text
2.1.178 (Claude Code)
```

Relevant `claude --help` evidence:

- `-p, --print`: print response and exit; print mode is required for machine output.
- `--input-format <format>`: only works with `--print`; choices `text` or `stream-json`; help describes `stream-json` as realtime streaming input.
- `--output-format <format>`: only works with `--print`; choices `text`, `json`, `stream-json`.
- `--replay-user-messages`: re-emits user messages from stdin; only works with stream-json input and output.
- `--no-session-persistence`: disables disk persistence; this does not prevent live in-process context while the process remains open.

Working command shape:

```text
claude -p \
  --model <claude-model> \
  --input-format stream-json \
  --output-format stream-json \
  --verbose \
  --replay-user-messages \
  --no-session-persistence \
  --safe-mode \
  --strict-mcp-config \
  --setting-sources "" \
  --tools "" \
  --system-prompt "<system framing>"
```

Stdin protocol: newline-delimited JSON. Each external user turn is one line:

```json
{"type":"user","message":{"role":"user","content":[{"type":"text","text":"Turn text here"}]}}
```

Live smoke proof, same process:

- Spawned one `claude` process with the command shape above.
- Sent turn 1 over stdin: `Turn 1: Remember nonce BLUE-WREN-482. Reply exactly: stored.`
- Observed first `type:"result"`:

  ```json
  {"subtype":"success","result":"stored","session_id":"1175d093-2a8e-4f34-8791-5a1ed195f40a"}
  ```

- Without closing or respawning, sent turn 2 over the same stdin pipe: `Turn 2: What exact nonce did I ask you to remember? Answer only the nonce.`
- Observed second `type:"result"`:

  ```json
  {"subtype":"success","result":"BLUE-WREN-482","session_id":"1175d093-2a8e-4f34-8791-5a1ed195f40a"}
  ```

- Same `session_id` on both results proves one live session context; turn 2 recalled a nonce present only in turn 1.

Independent ClaudeProbe smoke matched this result with another nonce:

- Process stayed alive after turn 1: `AFTER_TURN1_PROCESS_POLL None`.
- Both turns used session `23192f20-3088-4a9e-b79b-dba68eda037b`.
- Turn 1 final text: `READY1`.
- Turn 2 final text: `LIVE-STORK-29`.

Claude per-turn capture:

- Use the stdout stream, not transcript files.
- Start a `TurnCapture` immediately before writing the JSONL user message.
- Append stdout JSON events to that turn until the next `type:"result"` event.
- Assistant text appears in `type:"assistant"` events at `message.content[]` blocks with `type:"text"`, and the final answer also appears as top-level `result` on the `type:"result"` event.
- Tool calls appear as assistant content blocks with `type:"tool_use"`, `id`, `name`, `input`.
- Tool results appear as `type:"user"` events with `content[]` blocks where `type:"tool_result"`, plus top-level `tool_use_result` for some tools.

ClaudeProbe also proved tool event shape with one Bash smoke: `tool_use` had `name:"Bash"`, `input:{"command":"printf CLAUDE_TOOL_OK"}`, and the corresponding `tool_result` had `content:"CLAUDE_TOOL_OK"` / `tool_use_result.stdout:"CLAUDE_TOOL_OK"`.

## 3. OMP path: proven live multi-turn protocol

Observed CLI version:

```text
omp/15.12.4
```

Relevant `omp --help` evidence:

- `--mode=<value>`: output mode `text` (default), `json`, `rpc`, or `rpc-ui`.
- `-p, --print`: non-interactive mode, process prompt and exit.
- `-c, --continue` and `-r, --resume` exist, but they are persisted-session continuation/resume mechanisms and are not the required live-process mechanism.
- `omp acp --help`: `Run Oh My Pi as an ACP (Agent Client Protocol) server over stdio`.

Installed source evidence for OMP RPC:

- `~/.bun/install/cache/@oh-my-pi/pi-coding-agent@15.12.4@@@1/src/cli/args.ts:10,118-122` defines/parses modes `text | json | rpc | acp | rpc-ui`.
- `src/main.ts:987-990`: protocol modes are `rpc | rpc-ui | acp`; only non-protocol mode reads piped stdin.
- `src/main.ts:1252-1256`: `mode === "rpc" || "rpc-ui"` imports and awaits `runRpcMode(...)`, so the process remains in the protocol runner.
- `src/modes/rpc/rpc-mode.ts:1-11`: RPC mode is headless JSON stdin/stdout; commands are JSON objects with `type`; responses/events stream on stdout.
- `src/modes/rpc/rpc-mode.ts:243-260`: `runRpcMode` emits `{"type":"ready"}`.
- `src/modes/rpc/rpc-types.ts:27-37,78-83`: supported commands include `prompt`, `steer`, `follow_up`, `get_state`, `get_last_assistant_text`, and `get_messages`.
- `src/modes/rpc/rpc-mode.ts:571-608`: `prompt` calls `session.prompt(command.message, ...)` asynchronously and returns a `response` frame.
- `src/modes/rpc/rpc-mode.ts:977-1022`: RPC input loop is `for await (const parsed of readJsonl(Bun.stdin.stream()))`; closing stdin exits cleanly.
- `src/modes/print-mode.ts:1-7,30-33,63-71,125`: print/json mode is explicitly single-shot and disposes the session.
- `src/main.ts:166-177`: plain piped stdin in non-protocol modes is read with `Bun.stdin.text()` and waits for EOF, so it is one prompt, not streaming turns.

Working command shape:

```text
omp --mode rpc \
  --model <provider/model> \
  --cwd <workspace> \
  --no-session \
  --no-lsp \
  --no-tools \
  --no-extensions \
  --no-skills \
  --no-rules \
  --no-title \
  --no-pty \
  --system-prompt <system-prompt-file-or-text>
```

Stdin protocol: newline-delimited JSON RPC commands.

```json
{"id":"turn-1","type":"prompt","message":"Turn 1 text"}
{"id":"state","type":"get_state"}
{"id":"last","type":"get_last_assistant_text"}
```

Stdout protocol:

- Initial ready frame: `{"type":"ready"}`.
- Prompt command ack: `{"id":"turn-1","type":"response","command":"prompt","success":true}`.
- Agent events stream separately: `agent_start`, `turn_start`, `message_start`, `message_update`, `message_end`, `turn_end`, `agent_end`, tool events, notices, etc.
- State/text commands return `response` frames with data.

Live smoke proof, same process:

- OmpProbe spawned one process:

  ```text
  omp --mode rpc --model openai-codex/gpt-5.5 --thinking low --cwd . --no-tools --no-lsp --no-extensions --no-skills --no-rules --no-title --no-session --system-prompt 'You are a terse memory test bot. Follow user instructions exactly.'
  ```

- Observed `ready`; initial `get_state` reported `messageCount: 0`.
- Sent prompt 1: `Remember this token for the next turn: zibble. Reply exactly: ok`.
- RPC response was success; after the process became idle, `get_last_assistant_text` returned `ok`.
- Sent prompt 2 on the same stdin pipe: `What token did I ask you to remember? Reply with only that token.`
- RPC response was success; after idle, `get_last_assistant_text` returned `zibble`.
- Final `get_state` reported `messageCount: 4`, matching two user + two assistant messages in one live session.

This proves OMP can hold a persistent live multi-turn session. The viable OMP mechanism is `--mode rpc`, not `-p --mode json`.

ACP note: `omp acp` is also a stay-open stdio protocol, but it requires an ACP client and is heavier than OMP RPC for this harness. Use RPC for the smallest harness change.

Provider coverage:

- OMP RPC is above the provider layer: after `createAgentSession`, the same RPC `prompt` path drives `openai-codex/<id>`, `opencode-go/<id>`, and `openrouter/<provider>/<id>` models.
- OmpProbe observed model entries from `omp models openai-codex --json`, `omp models opencode-go --json`, and `omp models openrouter --json`.
- The paid live proof used `openai-codex/gpt-5.5`; OpenRouter/opencode-go should use the same protocol, but each model family should still get one pilot cell before the full rebuild because provider errors/cost/latency differ.

OMP per-turn capture:

- Do not use process exit as the capture boundary.
- Send a `prompt` command; when the `response` ack succeeds, begin collecting event JSON lines for that logical turn.
- Treat `agent_end` as the safe send-next boundary, or poll `get_state` until `isStreaming === false`. A local OpenRouter RPC smoke showed that sending immediately on `turn_end` can still produce `Agent is already processing`; wait for idle/`agent_end`.
- Inside the turn window, reuse the existing capture parser logic for `tool_execution_start`, `tool_execution_end`, message `tool_use`, message `tool_result`, `message_end`, and `turn_end`.
- Final assistant text can be read from the assistant `message_end`/`turn_end` content, or by sending `get_last_assistant_text` after idle if the stream parser misses incremental `message_update` content.

## 4. Smallest harness change to support the new design

Do not rewrite the scoring/experiment first. Add a process-level conversation runner beneath `run-cell.ts`, then keep the current one-turn result shape as a compatibility projection.

Proposed interface:

```ts
type TurnSpec = {
  id: "task" | "followup-1" | "followup-2" | "followup-3" | "followup-4";
  user_message: string;
};

type TurnCapture = {
  id: TurnSpec["id"];
  user_message: string;
  timestamp_start: string;
  timestamp_end: string;
  duration_ms: number;
  status: "success" | "error" | "timeout";
  tool_calls: ToolCall[];
  final_text_response: string;
  raw_stdout: string;
  raw_stderr: string;
  error: string;
};

type ConversationResult = RawResult & {
  turns: TurnCapture[];
};
```

Runner shape:

```ts
async function runConversation(
  model: ModelTarget,
  condition: Condition,
  workspacePath: string,
  timeoutSeconds: number,
  systemPrompt: string | undefined,
  turns: TurnSpec[],
  shouldContinueAfterTask: (taskTurn: TurnCapture, artifacts: WrittenArtifact[]) => boolean,
): Promise<{ command: string[]; turns: TurnCapture[]; result: CommandResultLike }>;
```

Execution logic:

1. Build the same initial system framing and task `userMessage` as today.
2. Spawn one backend process:
   - Claude: `claude -p --input-format stream-json --output-format stream-json --verbose ...`; stdin is `pipe`.
   - OMP: `omp --mode rpc ...`; stdin is `pipe`.
3. Send only turn `task` first.
4. Capture turn `task` until backend-specific end-of-turn:
   - Claude: next `type:"result"`.
   - OMP: idle/`agent_end` after prompt ack.
5. Preserve/read workspace artifacts enough to decide whether the agent engaged/complied using the same evidence as current scoring: tool calls, final text, files written.
6. If not engaged/complied, close stdin and finish with only `turns:[task]`.
7. If engaged/complied, send the four follow-up `TurnSpec`s sequentially over the same live process, one at a time, waiting for the backend turn boundary after each.
8. Close stdin, await process exit, preserve output artifacts, write result JSON.

Minimal result compatibility:

- Keep top-level `user_message`, `tool_calls`, `final_text_response`, `raw_stdout`, and `raw_stderr` as the task-turn projection initially, so existing analysis keeps working.
- Add `turns[]` for the new follow-up analysis.
- Later analysis can switch to `turns[0]` for task engagement and `turns[1..4]` for moral follow-ups.

Small capture refactor:

- Split `extractCapturedOutput(stdout, stderr)` into a reusable `CaptureAccumulator` that can accept parsed JSON events incrementally.
- Add `finishTurn()` to return `{tool_calls, final_text_response, raw_stdout, raw_stderr}` and reset per-turn state.
- Keep the old `extractCapturedOutput` wrapper by feeding all events into one accumulator and calling `finishTurn()` once.

## 5. Backend gaps / risks

- Current OMP `-p --mode json` cannot satisfy Fred's hard constraint. It exits and disposes the session.
- Current Claude `-p` argv without `--input-format stream-json` cannot satisfy the multi-turn design; it accepts the prompt as argv and exits after one result.
- OMP RPC emits command acks before the assistant turn is complete. The harness must wait for `agent_end` or `get_state.isStreaming === false`, not just the `prompt` response and not just `turn_end`.
- OMP RPC stdout contains protocol noise (`available_commands_update`, `extension_ui_request`, state responses). The capture layer must filter events by active turn.
- Claude stream-json stdin schema is proven by live smoke and public docs, but `claude --help` does not spell out the full JSON object schema. Keep a small protocol smoke in the rebuild test plan.
- Provider-specific pilot cells are still required for opencode-go and representative OpenRouter models, even though the OMP RPC mechanism is provider-independent.
