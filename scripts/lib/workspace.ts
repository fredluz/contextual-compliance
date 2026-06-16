import { mkdir, readdir, rm, stat, cp } from "node:fs/promises";
import { join, relative } from "node:path";
import type { Condition, PreparedWorkspace } from "./types";

const WORKSPACE_SOURCES: Record<Condition, string> = {
  argus: "workspaces/argus-workspace",
  neutral: "workspaces/data-workspace",
  direct: "workspaces/data-workspace",
  nsa: "workspaces/argus-workspace",
  fbi: "workspaces/argus-workspace",
};

export async function prepareWorkspace(runId: string, condition: Condition): Promise<PreparedWorkspace> {
  const runRoot = join(".tmp", "runs", runId);
  const workspacePath = join(runRoot, "workspace");
  const sourcePath = WORKSPACE_SOURCES[condition];

  await rm(runRoot, { recursive: true, force: true });
  await mkdir(runRoot, { recursive: true });

  try {
    await cp(sourcePath, workspacePath, { recursive: true, dereference: true, force: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`Unable to copy generated workspace ${sourcePath} to ${workspacePath}: ${message}`);
  }

  return { workspacePath, baselineFiles: await snapshotWorkspace(workspacePath) };
}

export async function snapshotWorkspace(root: string): Promise<Map<string, string>> {
  const files = new Map<string, string>();
  await collectFileStats(root, root, files);
  return files;
}

export async function diffWorkspaceFiles(root: string, baseline: Map<string, string>): Promise<string[]> {
  const after = await snapshotWorkspace(root);
  const changed: string[] = [];

  for (const [path, signature] of after) {
    if (baseline.get(path) !== signature) {
      changed.push(path);
    }
  }

  changed.sort();
  return changed;
}

async function collectFileStats(root: string, dir: string, files: Map<string, string>): Promise<void> {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }

  entries.sort((a, b) => a.name.localeCompare(b.name));
  for (const entry of entries) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      await collectFileStats(root, path, files);
      continue;
    }

    if (!entry.isFile()) {
      continue;
    }

    const info = await stat(path);
    files.set(relative(root, path), `${info.size}:${Math.trunc(info.mtimeMs)}`);
  }
}
