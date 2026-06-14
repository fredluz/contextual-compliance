import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { RawResult, ToolCallCapture } from "./types";

type JsonObject = Record<string, unknown>;

type MutableToolCall = {
  tool: string;
  input?: unknown;
  output_summary?: string;
};

const MAX_FINAL_TEXT_CHARS = 500 * 1024;
const MAX_TOOL_SUMMARY_CHARS = 2 * 1024;

export function extractCapturedOutput(stdout: string, stderr: string): Pick<RawResult, "tool_calls" | "final_text_response"> {
  const values = parseJsonLines(stdout);
  const callsById = new Map<string, MutableToolCall>();
  const callsInOrder: MutableToolCall[] = [];
  let finalText = "";

  for (const value of values) {
    if (!isObject(value)) {
      continue;
    }

    const event = value;
    const type = stringField(event, "type");

    if (type === "tool_execution_start") {
      const id = stringField(event, "toolCallId") || `tool:${callsInOrder.length}`;
      const tool = stringField(event, "toolName");
      if (tool.length > 0) {
        upsertToolCall(callsById, callsInOrder, id, tool, event.args);
      }
      continue;
    }

    if (type === "tool_execution_end") {
      const id = stringField(event, "toolCallId") || `tool:${callsInOrder.length}`;
      const tool = stringField(event, "toolName");
      const call = tool.length > 0 ? upsertToolCall(callsById, callsInOrder, id, tool, undefined) : callsById.get(id);
      if (call !== undefined) {
        call.output_summary = summarizeToolResult(event.result);
      }
      continue;
    }

    if (type === "message_end" || type === "turn_end") {
      const message = objectField(event, "message");
      if (message !== undefined) {
        finalText = extractAssistantText(message) || finalText;
        captureMessageToolCalls(message, callsById, callsInOrder);
      }
      continue;
    }

    if (type === "result") {
      const result = stringField(event, "result");
      if (result.length > 0) {
        finalText = result;
      }
      continue;
    }

    const message = objectField(event, "message");
    if (message !== undefined) {
      captureMessageToolCalls(message, callsById, callsInOrder);
    }
  }

  if (finalText.length === 0) {
    finalText = extractFallbackText(values, stdout, stderr);
  }

  return {
    tool_calls: callsInOrder.map((call) => {
      const captured: ToolCallCapture = { tool: call.tool };
      if (call.input !== undefined) {
        captured.input = call.input;
      }
      if (call.output_summary !== undefined) {
        captured.output_summary = call.output_summary;
      }
      return captured;
    }),
    final_text_response: truncateText(finalText.trim(), MAX_FINAL_TEXT_CHARS),
  };
}

export async function writeRawResult(result: RawResult): Promise<string> {
  await mkdir(join("results", "raw"), { recursive: true });
  const path = join("results", "raw", `${result.run_id}.json`);
  await writeFile(path, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  return path;
}

function parseJsonLines(text: string): unknown[] {
  const trimmed = text.trim();
  if (trimmed.length === 0) {
    return [];
  }

  try {
    return [JSON.parse(trimmed)];
  } catch {
    const values: unknown[] = [];
    for (const line of trimmed.split(/\r?\n/)) {
      const candidate = line.trim();
      if (candidate.length === 0) {
        continue;
      }
      try {
        values.push(JSON.parse(candidate));
      } catch {
        // OMP json mode is line-delimited JSON. Ignore non-JSON noise.
      }
    }
    return values;
  }
}

function captureMessageToolCalls(message: JsonObject, callsById: Map<string, MutableToolCall>, callsInOrder: MutableToolCall[]): void {
  const content = message.content;
  if (!Array.isArray(content)) {
    return;
  }

  for (const item of content) {
    if (!isObject(item)) {
      continue;
    }
    const type = stringField(item, "type").toLowerCase();
    if (type !== "toolcall" && type !== "tool_call" && type !== "tool_use") {
      continue;
    }
    const id = stringField(item, "id") || `message-tool:${callsInOrder.length}`;
    const tool = stringField(item, "name") || stringField(item, "tool") || stringField(item, "tool_name");
    const input = item.arguments ?? item.input ?? item.args;
    if (tool.length > 0) {
      upsertToolCall(callsById, callsInOrder, id, tool, input);
    }
  }
}

function upsertToolCall(callsById: Map<string, MutableToolCall>, callsInOrder: MutableToolCall[], id: string, tool: string, input: unknown): MutableToolCall {
  const existing = callsById.get(id);
  if (existing !== undefined) {
    if (input !== undefined && existing.input === undefined) {
      existing.input = sanitizeCaptureValue(input);
    }
    return existing;
  }

  const call: MutableToolCall = input === undefined ? { tool } : { tool, input: sanitizeCaptureValue(input) };
  callsById.set(id, call);
  callsInOrder.push(call);
  return call;
}

function extractAssistantText(message: JsonObject): string {
  if (stringField(message, "role") !== "assistant") {
    return "";
  }

  const content = message.content;
  if (typeof content === "string") {
    return content;
  }

  if (!Array.isArray(content)) {
    return "";
  }

  const chunks: string[] = [];
  for (const item of content) {
    if (!isObject(item) || stringField(item, "type") !== "text") {
      continue;
    }
    const text = stringField(item, "text");
    if (text.length > 0) {
      chunks.push(text);
    }
  }
  return chunks.join("");
}

function extractFallbackText(values: unknown[], stdout: string, stderr: string): string {
  for (let index = values.length - 1; index >= 0; index -= 1) {
    const value = values[index];
    if (!isObject(value)) {
      continue;
    }
    const result = stringField(value, "result");
    if (result.length > 0) {
      return result;
    }
    const message = objectField(value, "message");
    if (message !== undefined) {
      const text = extractAssistantText(message);
      if (text.length > 0) {
        return text;
      }
    }
  }

  const trimmedStdout = stdout.trim();
  if (trimmedStdout.length > 0 && values.length === 0) {
    return trimmedStdout;
  }
  return stderr.trim();
}

function summarizeToolResult(result: unknown): string {
  if (typeof result === "string") {
    return summarize(result);
  }

  if (isObject(result)) {
    const content = result.content;
    if (Array.isArray(content)) {
      const text = content
        .map((item) => isObject(item) ? stringField(item, "text") : "")
        .filter((part) => part.length > 0)
        .join("\n");
      if (text.length > 0) {
        return summarize(text);
      }
    }

    const display = objectField(result, "details")?.displayContent;
    if (isObject(display)) {
      const text = stringField(display, "text");
      if (text.length > 0) {
        return summarize(text);
      }
    }
  }

  try {
    return summarize(JSON.stringify(result));
  } catch {
    return "";
  }
}

function objectField(object: JsonObject, key: string): JsonObject | undefined {
  const value = object[key];
  return isObject(value) ? value : undefined;
}

function stringField(object: JsonObject, key: string): string {
  const value = object[key];
  return typeof value === "string" ? value : "";
}

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function sanitizeCaptureValue(value: unknown, depth = 0): unknown {
  if (typeof value === "string") {
    return truncateText(value, MAX_TOOL_SUMMARY_CHARS);
  }
  if (depth >= 4) {
    return isObject(value) || Array.isArray(value) ? "[truncated: nested value]" : value;
  }
  if (Array.isArray(value)) {
    const limit = Math.min(value.length, 50);
    const sanitized = value.slice(0, limit).map((item) => sanitizeCaptureValue(item, depth + 1));
    if (value.length > limit) {
      sanitized.push(`[truncated: ${value.length - limit} more items]`);
    }
    return sanitized;
  }
  if (isObject(value)) {
    const sanitized: JsonObject = {};
    for (const [key, entry] of Object.entries(value)) {
      sanitized[key] = sanitizeCaptureValue(entry, depth + 1);
    }
    return sanitized;
  }
  return value;
}

function truncateText(text: string, maxLength: number): string {
  return text.length <= maxLength ? text : `${text.slice(0, maxLength - 3)}...`;
}

function summarize(text: string, maxLength = MAX_TOOL_SUMMARY_CHARS): string {
  const compact = text.replace(/\s+/g, " ").trim();
  return compact.length <= maxLength ? compact : `${compact.slice(0, maxLength - 3)}...`;
}
