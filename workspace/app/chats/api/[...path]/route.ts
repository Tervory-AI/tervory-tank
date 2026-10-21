import { activeTenant } from "@/lib/tenant";
import { isFounder } from "@/lib/admin";
import { commandRequest, listRoster } from "@/lib/tank";
import { modelValue } from "../../models";
import { clientText, presentReceipt, presentSnapshot, presentThread, visibleCard } from "../../presentation";
import { readEvents, type Card, type Receipt, type Snapshot, type Thread } from "../../contract";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
type Context = { params: Promise<{ path: string[] }> };
const json = (data: unknown, status = 200) => Response.json(data, { status, headers: { "Cache-Control": "no-store" } });
async function handle(request: Request, context: Context): Promise<Response> {
  try {
    if (request.method !== "GET" && request.headers.get("origin") !== new URL(request.url).origin) return json({ error: "This request must come from your workspace." }, 403);
    const identity = await activeTenant();
    if (!identity) return json({ error: "Please sign in and choose your workspace." }, 401);
    const founder = isFounder(identity.userId);
    const { path } = await context.params;
    if (path.some(part => !/^[a-zA-Z0-9_-]+$/.test(part))) return json({ error: "Unknown request." }, 404);
    const target = path.join("/");
    const method = request.method;
    const valid = (target === "threads" && ["GET", "POST"].includes(method))
      || (/^threads\/[\w-]+$/.test(target) && ["GET", "PATCH"].includes(method))
      || (/^threads\/[\w-]+\/turn$/.test(target) && method === "POST")
      || (/^threads\/[\w-]+\/events$/.test(target) && method === "GET")
      || (/^cards\/[\w-]+$/.test(target) && method === "POST");
    if (!valid) return json({ error: "Unknown request." }, 404);
    const roster = await listRoster();
    const names = roster.flatMap(model => [model.name, model.providerModel]).filter(Boolean);
    let body: Record<string, unknown> | undefined;
    if (method !== "GET") {
      const raw = await request.text();
      if (raw.length > 8_000_000) return json({ error: "Files must total less than 5 MB." }, 413);
      const input = JSON.parse(raw);
      if (target.startsWith("cards/")) {
        if (!["confirm", "cancel"].includes(input.action)) return json({ error: "Choose Confirm or Cancel." }, 400);
        body = { action: input.action };
      } else if (target.endsWith("/turn")) {
        if (typeof input.text !== "string" || !input.text.trim() || input.text.length > 20000) return json({ error: "Write a message of up to 20,000 characters." }, 400);
        const model = !input.model || input.model === "auto" ? "auto" : roster.find(row => modelValue(row.name) === input.model)?.name;
        if (!model) return json({ error: "That option is no longer available. Choose another." }, 400);
        const attachments = input.attachments ?? [];
        if (!Array.isArray(attachments) || attachments.length > 5 || attachments.some(file => !file || typeof file.name !== "string" || file.name.length > 200 || typeof file.content_type !== "string" || typeof file.data_base64 !== "string" || !/^[A-Za-z0-9+/]*={0,2}$/.test(file.data_base64))) return json({ error: "The attached files could not be read." }, 400);
        if (attachments.reduce((sum, file) => sum + Buffer.byteLength(file.data_base64, "base64"), 0) > 5 * 1024 * 1024) return json({ error: "Files must total less than 5 MB." }, 413);
        body = { text: input.text.trim(), model, attachments: attachments.map(file => ({ name: file.name, content_type: file.content_type, data_base64: file.data_base64 })) };
      } else {
        if (input.title !== undefined && (typeof input.title !== "string" || !input.title.trim() || input.title.length > 160)) return json({ error: "Use a chat name of 1 to 160 characters." }, 400);
        body = input.title ? { title: input.title.trim() } : {};
      }
    }
    let query = "";
    if (target.endsWith("/events")) {
      const after = new URL(request.url).searchParams.get("after") ?? "0";
      if (!/^\d+$/.test(after)) return json({ error: "Invalid update position." }, 400);
      query = `?after=${after}`;
    }
    const upstream = await commandRequest(identity, target + query, { method, body: body ? JSON.stringify(body) : undefined, signal: request.signal });
    if (upstream.headers.get("content-type")?.includes("text/event-stream")) {
      if (!upstream.body) throw new Error("Missing stream");
      const encoder = new TextEncoder();
      const stream = new ReadableStream<Uint8Array>({
        async start(controller) {
          let pendingText = "";
          const emit = (type: string, data: unknown, seq?: number) => controller.enqueue(encoder.encode(`${seq === undefined ? "" : `id: ${seq}\n`}event: ${type}\ndata: ${JSON.stringify(data)}\n\n`));
          const flush = () => { if (pendingText) { emit("token", { text: clientText(pendingText, names) }); pendingText = ""; } };
          try {
            await readEvents(upstream.body!, event => {
              let data: unknown = event.data;
              if (event.type === "error") data = { message: "The response was interrupted. Reopen this chat before sending again." };
              if (!founder) {
                if (event.type === "token") {
                  pendingText += String(event.data.text ?? "");
                  // Retain an unfinished sentence so names split across chunks cannot leak.
                  const end = Math.max(pendingText.lastIndexOf("\n"), pendingText.lastIndexOf(". "));
                  if (end >= 0) { emit("token", { text: clientText(pendingText.slice(0, end + 1), names) }, event.seq); pendingText = pendingText.slice(end + 1); }
                  return;
                }
                if (["done", "receipt", "error"].includes(event.type)) flush();
                if (event.type === "receipt") data = presentReceipt(event.data as unknown as Receipt, false);
                if (event.type === "step") data = { ...event.data, label: clientText(String(event.data.label), names), actor: clientText(String(event.data.actor), names) };
                if (event.type === "card") { if (!visibleCard(event.data as unknown as Card, false)) return; data = { ...event.data, summary: clientText(String(event.data.summary), names) }; }
              }
              if (["token", "step", "card", "receipt", "done", "error"].includes(event.type)) emit(event.type, data, event.seq);
            });
            flush();
          } catch { emit("error", { message: "The response was interrupted. Reopen this chat before sending again." }); }
          finally { controller.close(); }
        },
      });
      return new Response(stream, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-store, no-transform", "X-Accel-Buffering": "no" } });
    }
    if (upstream.status === 204) return json({ ok: true });
    const result = await upstream.json();
    if (method === "GET" && target === "threads") return json((result as Thread[]).map(row => presentThread(row, founder, names)));
    if (method === "GET" && path.length === 2 && path[0] === "threads") return json(presentSnapshot(result as Snapshot, founder, names));
    // Writes only acknowledge success; authoritative state is refreshed from the thread.
    return json(target === "threads" && method === "POST" ? { thread_id: result.thread_id } : { ok: true });
  } catch { return json({ error: "This request could not be completed. Reload the chat before trying again." }, 502); }
}
export const GET = handle;
export const POST = handle;
export const PATCH = handle;
