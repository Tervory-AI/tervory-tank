import type { Card, Receipt, Snapshot, Thread } from "./contract";
export function clientText(text: string, modelNames: string[] = []): string {
  let result = text;
  for (const name of [...modelNames].sort((a, b) => b.length - a.length)) {
    if (name) result = result.replace(new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), "selected option");
  }
  return result.replace(/\b(?:Skala|Tank|ledger|evals?|gold|shadow|retire|rungs?|tenants?|region box)\b/gi, "service");
}
export function presentReceipt(receipt: Receipt, founder: boolean): Receipt {
  if (founder) return receipt;
  return { totals: receipt.totals, rows: receipt.rows.map(row => ({ step_id: row.step_id, ledger_id: row.ledger_id, cost_usd: row.cost_usd, baseline_cost_usd: row.baseline_cost_usd, saved_usd: row.saved_usd, auto_cost_usd: row.auto_cost_usd })) };
}
export function visibleCard(card: Card, founder: boolean) { return founder || card.kind === "paid_run" || card.kind === "other"; }
export function presentThread(thread: Thread, founder: boolean, models: string[] = []): Thread { return { ...thread, title: founder ? thread.title : clientText(thread.title, models) }; }
export function presentSnapshot(snapshot: Snapshot, founder: boolean, models: string[] = []): Snapshot {
  const clean = (value: string) => founder ? value : clientText(value, models);
  return { seq: snapshot.seq, thread: presentThread(snapshot.thread, founder, models),
    messages: snapshot.messages.map(message => ({ ...message, content: clean(message.content), receipt: message.receipt && presentReceipt(message.receipt, founder), attachments: message.attachments?.map(file => ({ name: clean(file.name), content_type: file.content_type, attachment_id: file.attachment_id, size: file.size })) })),
    steps: snapshot.steps.map(step => ({ ...step, label: clean(step.label), actor: clean(step.actor) })),
    job_receipts: snapshot.job_receipts?.map(receipt => presentReceipt(receipt, founder)),
    cards: snapshot.cards.filter(card => visibleCard(card, founder)).map(card => ({ ...card, summary: clean(card.summary) })),
  };
}
