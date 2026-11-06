import { createHash } from "node:crypto";
import { mkdir, open, readFile, writeFile } from "node:fs/promises";
import { isAbsolute, join } from "node:path";
import { InputError } from "./route-input";

/** Exclusive durable claim: a crash or uncertain upstream write never permits a replay. */
export async function submitOnce<T>(tenant: string, user: string, key: string | null, body: unknown, run: () => Promise<T>): Promise<T> {
  const directory = process.env.WORKSPACE_SUBMISSIONS_DIR;
  if (!directory || !isAbsolute(directory)) throw new InputError("Tasks need the WORKSPACE_SUBMISSIONS_DIR setting on persistent shared storage. No work was started.", 503);
  if (!key || !/^[a-f0-9-]{36}$/i.test(key)) throw new InputError("Reload the workspace before submitting this task.");
  const digest = createHash("sha256").update(JSON.stringify(body)).digest("hex");
  const file = join(directory, createHash("sha256").update(JSON.stringify([tenant, user, key])).digest("hex") + ".json");
  try { await mkdir(directory, { recursive: true, mode: 0o700 }); }
  catch { throw new InputError("Task storage is unavailable. No work was started.", 503); }
  let handle;
  try { handle = await open(file, "wx", 0o600); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw new InputError("Task storage is unavailable. No work was started.", 503);
    try {
      const saved = JSON.parse(await readFile(file, "utf8"));
      if (saved.digest === digest && saved.state === "done") return saved.result as T;
    } catch { /* A partially written claim is still claimed. */ }
    throw new InputError("This task was already submitted. Reload tasks to check its status; do not submit it again.", 409);
  }
  try { await handle.writeFile(JSON.stringify({ digest, state: "started" })); await handle.sync(); }
  finally { await handle.close(); }
  const parent = await open(directory, "r");
  try { await parent.sync(); } finally { await parent.close(); }
  const result = await run();
  // Keep the original exclusive claim even if acknowledgement storage fails.
  await writeFile(file, JSON.stringify({ digest, state: "done", result }), { mode: 0o600 });
  const confirmed = await open(file, "r+");
  try { await confirmed.sync(); } finally { await confirmed.close(); }
  return result;
}
