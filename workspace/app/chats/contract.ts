// COMMAND-1 Lane A wire contract; server-free so streaming can be tested offline.
export type Money = number | null;
export type Totals = { cost_usd: Money; baseline_cost_usd: Money; saved_usd: Money; auto_cost_usd?: Money };
export type ReceiptRow = Totals & { step_id: string; model?: string; baseline_model?: string; tokens_in?: number; tokens_out?: number; ledger_id: string };
export type Receipt = { rows: ReceiptRow[]; totals: Totals };
export type Attachment = { name: string; content_type: string; text?: string; attachment_id?: string; size?: number };
export type Message = { message_id: string; role: "user" | "assistant"; content: string; receipt?: Receipt; attachments?: Attachment[] };
export type Step = { step_id: string; label: string; actor: string; status: "planned" | "running" | "done" | "failed"; link?: string };
export type Card = { card_id: string; kind: "approve_skill" | "paid_run" | "build" | "retire" | "other"; summary: string; cost_estimate_usd?: Money; status?: string };
export type Thread = { thread_id: string; title: string; updated_at: string; spent_usd: Money; saved_usd: Money };
export type Snapshot = { thread: Thread; messages: Message[]; steps: Step[]; cards: Card[]; seq?: number; receipts?: ReceiptRow[]; job_receipts?: Receipt[] };
export type ModelOption = { value: string; label: string; inputPerM: Money; outputPerM: Money };
export type Event = { type: string; data: Record<string, unknown>; seq?: number };
export function dollars(value: Money | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? `$${value.toFixed(value !== 0 && Math.abs(value) < .01 ? 6 : 2)}` : "Unavailable";
}
export function safeLink(value: string | undefined): string | undefined {
  if (!value || /[\\\u0000-\u0020]/.test(value)) return;
  if (value.startsWith("/") && !value.startsWith("//")) return value;
  try { const url = new URL(value); if (url.protocol === "https:" && !url.username && !url.password) return url.href; } catch { /* Not a link. */ }
}
/** Decode UTF-8 incrementally; SSE records can be split at any byte boundary. */
export async function readEvents(stream: ReadableStream<Uint8Array>, receive: (event: Event) => void) {
  const reader = stream.getReader(); const decoder = new TextDecoder(); let buffer = "";
  function dispatch(record: string) {
    let type = "message"; let id: number | undefined; const data: string[] = [];
    for (const line of record.split(/\r?\n/)) {
      if (line.startsWith("event:")) type = line.slice(6).trim();
      if (line.startsWith("id:")) { const n = Number(line.slice(3).trim()); if (Number.isSafeInteger(n) && n >= 0) id = n; }
      if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    if (!data.length) return;
    const payload = JSON.parse(data.join("\n")) as Record<string, unknown>;
    receive({ type, data: payload, seq: typeof payload.seq === "number" ? payload.seq : id });
  }
  try {
    while (true) {
      const { value, done } = await reader.read(); buffer += decoder.decode(value, { stream: !done });
      let boundary: RegExpMatchArray | null;
      while ((boundary = /\r?\n\r?\n/.exec(buffer))) { dispatch(buffer.slice(0, boundary.index)); buffer = buffer.slice(boundary.index! + boundary[0].length); }
      if (buffer.length > 2_000_000) throw new Error("The response was too large. Reopen the chat to continue.");
      if (done) { if (buffer.trim()) dispatch(buffer); break; }
    }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
export function upsert<T>(rows: T[], row: T, key: keyof T): T[] {
  return rows.some(item => item[key] === row[key]) ? rows.map(item => item[key] === row[key] ? row : item) : [...rows, row];
}

/** Lane A persists receipt rows separately, keyed to the answer by step_id. */
export function normalizeSnapshot(snapshot: Snapshot): Snapshot {
  const rows = snapshot.receipts ?? [];
  const sum = (items: ReceiptRow[], key: "cost_usd" | "baseline_cost_usd" | "saved_usd") => items.every(row => typeof row[key] === "number") ? items.reduce((total, row) => total + row[key]!, 0) : null;
  const receiptFor = (items: ReceiptRow[]): Receipt => ({ rows: items, totals: { cost_usd: sum(items, "cost_usd"), baseline_cost_usd: sum(items, "baseline_cost_usd"), saved_usd: sum(items, "saved_usd") } });
  const messages = snapshot.messages.map(message => {
    const matches = rows.filter(row => row.step_id === message.message_id);
    return { ...message, receipt: message.receipt ?? (matches.length ? receiptFor(matches) : undefined) };
  });
  const attached = new Set(messages.flatMap(message => message.receipt?.rows.map(row => row.ledger_id) ?? []));
  return { ...snapshot, messages, job_receipts: snapshot.job_receipts ?? rows.filter(row => !attached.has(row.ledger_id)).map(row => receiptFor([row])) };
}
