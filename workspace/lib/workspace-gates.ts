/**
 * Tank /v1/command/workspace/chat runs code_skill → recall → correction → reuse.
 * Genuine memory outages return memory_unavailable from Tank, never a client retry.
 * Workspace uses authenticated Tank Command tools for memory and model work.
 * Task submission proposes an existing Command card; only explicit Confirm
 * queues work. The board observes real completion and its paid receipt.
 * Tank owns pre-dispatch outage handling. An uncertain response never triggers
 * a second client-side paid request. Personal controls use the memory corridor.
 */
import "server-only";
import { InputError } from "@/lib/route-input";
import {
  COMMAND_LIMITS,
  commandRequest,
  type ChatMessage,
  type RouteResult,
  type Task,
  boundedFetch,
} from "@/lib/tank";

const TANK_URL = process.env.TANK_URL ?? "http://tank:8000";
const TANK_API_KEY = process.env.TANK_API_KEY ?? "";

export type MemoryControl = "off" | "view" | "edit" | "forget";

function refuseEmptyScope(tenantId: string | undefined | null, userId: string | undefined | null): {
  tenantId: string;
  userId: string;
} {
  if (!tenantId || !String(tenantId).trim()) throw new InputError("Signed-in tenant required.");
  if (!userId || !String(userId).trim()) throw new InputError("Signed-in user required.");
  if (String(tenantId) === String(userId)) throw new InputError("Tenant-as-user identity is refused.");
  return { tenantId: String(tenantId), userId: String(userId) };
}

function isAuthOrScopeFailure(err: unknown): boolean {
  if (err instanceof InputError) {
    const msg = err.message.toLowerCase();
    return (
      err.status === 401 ||
      err.status === 403 ||
      msg.includes("signed-in") ||
      msg.includes("tenant") ||
      msg.includes("user") ||
      msg.includes("refused") ||
      msg.includes("scope")
    );
  }
  if (err instanceof Error) {
    const msg = err.message.toLowerCase();
    return (
      msg.includes("workspace_command_401") ||
      msg.includes("workspace_command_403") ||
      msg.includes("authenticated") ||
      msg.includes("scope")
    );
  }
  return false;
}

/** Only typed/availability failures map to outage — never TypeError-like bugs or auth. */
function isMemoryOutageFailure(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const name = err.name || "";
  const msg = err.message.toLowerCase();
  if (name === "MemoryOutageError" || name === "MemoryUnavailable") return true;
  if (name === "TypeError" || name === "RangeError" || name === "SyntaxError") return false;
  if (msg.includes("workspace_command_401") || msg.includes("workspace_command_403")) return false;
  if (msg.includes("workspace_command_503") || msg.includes("workspace_command_502")) return true;
  return (
    msg.includes("econnrefused") ||
    msg.includes("enotfound") ||
    msg.includes("etimedout") ||
    msg.includes("timeout") ||
    msg.includes("timed out") ||
    msg.includes("unreachable") ||
    msg.includes("memory unavailable") ||
    msg.includes("bracket unavailable") ||
    msg.includes("hermes unreachable")
  );
}

/** Exported for unit/static tests of the narrow outage mapping. */
export function classifyWorkspaceCommandFailure(err: unknown): "auth" | "outage" | "error" {
  if (isAuthOrScopeFailure(err)) return "auth";
  if (isMemoryOutageFailure(err)) return "outage";
  return "error";
}


async function commandWorkspace<T>(
  identity: { tenantId: string; userId: string },
  toolPath: string,
  body: Record<string, unknown>,
): Promise<T> {
  const headers = new Headers({
    "content-type": "application/json",
    "x-tank-key": TANK_API_KEY,
    "x-tervory-tenant": identity.tenantId,
    "x-tervory-user": identity.userId,
    "x-tervory-home-region": process.env.TANK_REGION === "za" ? "za" : "us-east",
  });
  return boundedFetch(
    `${TANK_URL}/v1/command/workspace/${toolPath}`,
    { method: "POST", headers, body: JSON.stringify(body), cache: "no-store" },
    COMMAND_LIMITS.bodyMs ?? 60_000,
    async (response) => {
      if (!response.ok) {
        throw new Error(`workspace_command_${response.status}`);
      }
      return (await response.json()) as T;
    },
  );
}

/** Chat through free steps then Tank agent path. Auth refuses; memory outage degrades. */
export async function chatWithMemory(
  tenantId: string,
  userId: string,
  messages: ChatMessage[],
  options: { taskType?: string; memoryControl?: MemoryControl } = {},
): Promise<RouteResult & { memory_bracket?: Record<string, unknown> }> {
  const identity = refuseEmptyScope(tenantId, userId);
  const taskType = options.taskType ?? "tier0.answer";
  try {
    return await commandWorkspace(identity, "chat", {
      messages,
      task_type: taskType,
      ...(options.memoryControl ? { memory_control: options.memoryControl } : {}),
    });
  } catch (err) {
    if (isAuthOrScopeFailure(err)) {
      throw err instanceof InputError
        ? err
        : new InputError(err instanceof Error ? err.message : "Signed-in tenant and user required.", 401);
    }
    if (!isMemoryOutageFailure(err)) {
      throw err instanceof InputError
        ? err
        : new InputError(err instanceof Error ? err.message : "Chat failed.", 503);
    }
    throw new InputError("Workspace could not finish this action. Check its receipt before trying again.", 503);
  }
}

/** Propose through Command; the existing approved card owns explicit Confirm. */
export async function createTaskWithMemory(
  tenantId: string, userId: string, title: string, taskType: string, request: string,
  options: { memoryControl?: MemoryControl } = {},
): Promise<{ confirmation_required: true; thread_id: string; card_id: string }> {
  const identity = refuseEmptyScope(tenantId, userId);
  const thread = await (await commandRequest(identity, "threads", { method: "POST", body: "{}" })).json();
  const card = await (await commandRequest(identity, `threads/${thread.thread_id}/actions`, {
    method: "POST", body: JSON.stringify({ tool: "workspace.task.create", arguments: {
      title, request, task_type: taskType,
      ...(options.memoryControl ? { memory_control: options.memoryControl } : {}),
    } }),
  })).json();
  return { confirmation_required: true, thread_id: thread.thread_id, card_id: card.card_id };
}

/** The normal board poll observes completed work through its owned adapter. */
export async function listTasksWithMemory(tenantId: string, userId: string): Promise<Task[]> {
  const response = await commandRequest(refuseEmptyScope(tenantId, userId), "workspace/tasks");
  return (await response.json()).tasks;
}

export async function setWorkspaceMemoryControl(
  tenantId: string,
  userId: string,
  control: MemoryControl,
): Promise<{ memory_control: MemoryControl }> {
  const identity = refuseEmptyScope(tenantId, userId);
  return commandWorkspace(identity, "memory.control", { control });
}

export async function viewWorkspaceMemory(
  tenantId: string,
  userId: string,
  taskKey = "memory_control",
  memoryId?: string,
): Promise<{ memories: unknown[]; memory_control: MemoryControl }> {
  const identity = refuseEmptyScope(tenantId, userId);
  const url = new URL(`/v1/command/workspace/memory.view`, TANK_URL);
  url.searchParams.set("task_key", taskKey);
  url.searchParams.set("memory_control", "view");
  if (memoryId) url.searchParams.set("memory_id", memoryId);
  const headers = new Headers({
    "x-tank-key": TANK_API_KEY,
    "x-tervory-tenant": identity.tenantId,
    "x-tervory-user": identity.userId,
  });
  return boundedFetch(url, { method: "GET", headers, cache: "no-store" }, 30_000, async (response) => {
    if (!response.ok) throw new InputError("Memory view unavailable.");
    return (await response.json()) as { memories: unknown[]; memory_control: MemoryControl };
  });
}

export async function forgetWorkspaceMemory(
  tenantId: string,
  userId: string,
  memoryId: string,
): Promise<{ forgotten: boolean }> {
  const identity = refuseEmptyScope(tenantId, userId);
  return commandWorkspace(identity, "memory.forget", { memory_id: memoryId, memory_control: "forget" });
}

/** Edit the content of one memory entry (requires edit/forget control). */
export async function editWorkspaceMemory(
  tenantId: string,
  userId: string,
  memoryId: string,
  text: string,
): Promise<{ id: string; updated: boolean }> {
  const identity = refuseEmptyScope(tenantId, userId);
  if (!text || !String(text).trim()) throw new InputError("Memory edit requires non-empty text.");
  return commandWorkspace(identity, "memory.edit", { memory_id: memoryId, text: String(text).trim() });
}
