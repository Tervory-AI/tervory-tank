/**
 * Gates 7+8 Workspace request path (live).
 *
 * Call chain — chat:
 *   app/api/chat/route.ts
 *     → lib/workspace-gates.ts chatWithMemory (this file)
 *       → Tank /v1/command/workspace/chat
 *         → integrations/tank/workspace.py _run_chat_with_memory
 *           → integrations/workspace/request_path.py run_chat_request
 *             → gates_memory.product_to_tank_agent_memory
 *               free: code_skill → recall → correction → identical_reuse
 *               paid: Tank agent route → remember → receipt
 *       (memory outage only: lib/tank.ts route → /v1/route with memory_unavailable)
 *
 * Call chain — tasks POST:
 *   app/api/tasks/route.ts
 *     → lib/workspace-gates.ts createTaskWithMemory (this file)
 *       → Tank /v1/command/workspace/task.create
 *         → integrations/tank/workspace.py _run_task_create_with_memory
 *           → integrations/workspace/request_path.py run_task_request
 *             → gates_memory.product_to_tank_agent_memory
 *               free steps then Tank agent create_task → receipt
 *       (memory outage only: lib/tank.ts createTask → /v1/tasks with memory_unavailable)
 *
 * Auth/scope errors (missing tenant/user, tenant-as-user) always refuse — no paid call.
 * Memory outage answers through the Tank agent path, marks memory unavailable, and
 * never serves identical_reuse or remembers.
 *
 * Memory controls (off/view/edit/forget) are per tenant+user via the existing
 * memory corridor (workspace.memory.* tools → MemoryClient → Hermes /memories
 * with the Workspace agent key). Never Tank /v1/memory and never the shared
 * TANK_API_KEY for writes.
 */
import "server-only";
import { InputError } from "@/lib/route-input";
import {
  COMMAND_LIMITS,
  createTask,
  route,
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

function memoryUnavailableBracket(reason: string) {
  return {
    memory_unavailable: true,
    memory_status: "memory unavailable",
    reason,
    answered_from_memory: false,
    identical_reuse: false,
    steps: [{ action: "memory_unavailable", reason }, { action: "tank_agent", status: "done" }],
  };
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
    const reason = err instanceof Error ? err.message : "memory unavailable";
    const routed = await route(identity.tenantId, taskType, messages);
    return {
      ...routed,
      memory_bracket: memoryUnavailableBracket(reason),
    };
  }
}

/** Task create through free steps then Tank agent path. Auth refuses; memory outage degrades. */
export async function createTaskWithMemory(
  tenantId: string,
  userId: string,
  title: string,
  taskType: string,
  request: string,
  options: { memoryControl?: MemoryControl } = {},
): Promise<Task & { memory_bracket?: Record<string, unknown> }> {
  const identity = refuseEmptyScope(tenantId, userId);
  try {
    return await commandWorkspace(identity, "task.create", {
      title,
      request,
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
        : new InputError(err instanceof Error ? err.message : "Task create failed.", 503);
    }
    const reason = err instanceof Error ? err.message : "memory unavailable";
    const created = await createTask(identity.tenantId, identity.userId, title, taskType, [
      { role: "user", content: request },
    ]);
    return {
      ...created,
      memory_bracket: memoryUnavailableBracket(reason),
    };
  }
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
