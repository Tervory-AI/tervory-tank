"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { SquadLinks } from "../squad-links";
import { clientText, visibleCard } from "./presentation";
import { dollars, readEvents, safeLink, upsert, type Attachment, type Card, type Message, type ModelOption, type Receipt, type Snapshot, type Step, type Thread } from "./contract";
import "./window.css";

async function api(path: string, init: RequestInit = {}) {
  const response = await fetch(`/chats/api/${path}`, { ...init, headers: { "Content-Type": "application/json" }, cache: "no-store" });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.error ?? "Your request could not be completed."); }
  return response;
}
const problem = (error: unknown) => error instanceof Error ? error.message : "Your request could not be completed.";
const statusLabel = { planned: "Planned", running: "Running", done: "Done", failed: "Failed" };

function CostReceipt({ receipt, founder, threadId, messageId }: { receipt: Receipt; founder: boolean; threadId: string; messageId: string }) {
  const rows = <div className="cw-receipt-rows">{receipt.rows.map((row, index) => <a className="cw-receipt-row" key={`${row.ledger_id}-${index}`} href={`/chats/evidence/${encodeURIComponent(threadId)}/${encodeURIComponent(row.ledger_id)}`}>
    <span>{founder ? row.step_id : `Step ${index + 1}`}</span>
    {founder && <span>{row.model === "code" ? "code (no model)" : row.model}<small>{row.tokens_in ?? "—"} in · {row.tokens_out ?? "—"} out</small></span>}
    <span>Cost {dollars(row.cost_usd)}</span><span>{founder && row.baseline_model ? `${row.baseline_model} ` : "Would have cost "}{dollars(row.baseline_cost_usd)}</span><span className="cw-saving">Saved {dollars(row.saved_usd)}</span>
    {founder && <small>{row.ledger_id}</small>}
  </a>)}<div className="cw-receipt-total"><span>Total</span><span>Cost {dollars(receipt.totals.cost_usd)}</span><span>Would have cost {dollars(receipt.totals.baseline_cost_usd)}</span><span>Saved {dollars(receipt.totals.saved_usd)}</span>{receipt.totals.auto_cost_usd !== undefined && <span>Auto would have cost {dollars(receipt.totals.auto_cost_usd)}</span>}</div></div>;
  return <section className="cw-receipt" id={`cost-${messageId}`} aria-label="Answer cost"><div className="cw-receipt-desktop"><header><strong>Receipt</strong><small>Each step links to its cost details</small></header>{rows}</div><details className="cw-receipt-mobile"><summary>Receipt · {dollars(receipt.totals.cost_usd)} · would have cost {dollars(receipt.totals.baseline_cost_usd)} · saved {dollars(receipt.totals.saved_usd)}</summary>{rows}</details></section>;
}

export function CommandWindow({ initialThreads, models, founder, account, initialError = "" }: { initialThreads: Thread[]; models: ModelOption[]; founder: boolean; account: string; initialError?: string }) {
  const [threads, setThreads] = useState(initialThreads);
  const [selected, setSelected] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [query, setQuery] = useState("");
  const [text, setText] = useState("");
  const [model, setModel] = useState("auto");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [error, setError] = useState(initialError);
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [cardBusy, setCardBusy] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const [work, setWork] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState("");
  const generation = useRef(0);
  const streamAbort = useRef<AbortController | null>(null);
  const sendingRef = useRef(false);
  const active = useRef<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const workButton = useRef<HTMLButtonElement>(null);
  const workClose = useRef<HTMLButtonElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const menuClose = useRef<HTMLButtonElement>(null);
  const clean = (value: string) => founder ? value : clientText(value);

  async function refreshThreads() { const rows = await (await api("threads")).json() as Thread[]; setThreads(rows); }
  async function load(id: string, version = generation.current) {
    const next = await (await api(`threads/${encodeURIComponent(id)}`)).json() as Snapshot;
    if (generation.current !== version || active.current !== id) return;
    setSnapshot(next); setThreads(rows => upsert(rows, next.thread, "thread_id"));
  }
  async function choose(id: string) {
    if (sendingRef.current) return;
    const version = ++generation.current;
    active.current = id; setSelected(id); setSnapshot(null); setBusy(true); setError(""); setMenu(false); setRenaming(false);
    window.history.replaceState(null, "", `/chats?thread=${encodeURIComponent(id)}`);
    try { await load(id, version); } catch (err) { if (version === generation.current) setError(problem(err)); }
    finally { if (version === generation.current) setBusy(false); }
  }
  useEffect(() => {
    const id = new URL(window.location.href).searchParams.get("thread");
    if (id) void choose(id);
    return () => { generation.current++; streamAbort.current?.abort(); };
    // A saved URL is loaded once; subsequent changes use choose to reject stale reads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!selected || sending) return;
    let stopped = false; let timer: ReturnType<typeof setTimeout>;
    const version = generation.current;
    const tick = async () => {
      if (stopped) return;
      if (document.visibilityState === "visible" && !sendingRef.current) {
        try { await load(selected, version); } catch { if (!stopped) setError("Live updates are unavailable. Your last saved work is still shown."); }
      }
      if (!stopped) timer = setTimeout(tick, 4000);
    };
    timer = setTimeout(tick, 4000);
    return () => { stopped = true; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, sending]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: "end" }); }, [snapshot?.messages.length, sending]);
  useEffect(() => { if (work) workClose.current?.focus(); }, [work]);
  useEffect(() => { if (menu) menuClose.current?.focus(); }, [menu]);
  function closeWork() { setWork(false); workButton.current?.focus(); }
  function closeMenu() { setMenu(false); menuButton.current?.focus(); }

  async function newThread() {
    if (busy || sendingRef.current) return;
    setBusy(true); setError("");
    try { const created = await (await api("threads", { method: "POST", body: "{}" })).json(); await refreshThreads(); await choose(created.thread_id); setText(""); setAttachments([]); }
    catch (err) { setError(problem(err)); } finally { setBusy(false); }
  }
  async function rename(event: FormEvent) {
    event.preventDefault(); if (!selected || busy) return;
    setBusy(true); setError("");
    try { await api(`threads/${selected}`, { method: "PATCH", body: JSON.stringify({ title }) }); await load(selected); await refreshThreads(); setRenaming(false); }
    catch (err) { setError(problem(err)); } finally { setBusy(false); }
  }
  async function decide(card: Card, action: "confirm" | "cancel") {
    if (cardBusy || !selected || sendingRef.current) return;
    setCardBusy(card.card_id); setError("");
    try { await api(`cards/${encodeURIComponent(card.card_id)}`, { method: "POST", body: JSON.stringify({ action }) }); await load(selected); }
    catch (err) { setError(problem(err)); } finally { setCardBusy(null); }
  }
  async function attach(files: FileList | null) {
    if (!files) return;
    const combinedSize = attachments.reduce((n, file) => n + (file.size ?? 0), 0) + Array.from(files).reduce((n, file) => n + file.size, 0);
    if (attachments.length + files.length > 5 || combinedSize > 5 * 1024 * 1024) { setError("Attach up to five files, totaling no more than 5 MB."); return; }
    setBusy(true);
    try {
      const additions = await Promise.all(Array.from(files).map(file => new Promise<Attachment>((resolve, reject) => {
        const reader = new FileReader(); reader.onerror = () => reject(new Error("A file could not be read."));
        reader.onload = () => resolve({ name: file.name, content_type: file.type || "application/octet-stream", size: file.size, data_base64: String(reader.result).split(",")[1] }); reader.readAsDataURL(file);
      })));
      setAttachments(current => [...current, ...additions]);
    } catch (err) { setError(problem(err)); } finally { setBusy(false); }
  }
  async function send(event: FormEvent) {
    event.preventDefault(); if (!text.trim() || sendingRef.current || busy || !snapshot || !selected) return;
    const id = selected; const requestText = text; const files = attachments;
    sendingRef.current = true; setSending(true); setError("");
    // Invalidate any snapshot already in flight before the new stream starts.
    const version = ++generation.current;
    const controller = new AbortController(); streamAbort.current = controller;
    const localId = `pending-${Date.now()}`; let completed = false; let lastSeq = -1;
    setSnapshot(current => current && ({ ...current, messages: [...current.messages, { message_id: `${localId}-user`, role: "user", content: requestText, attachments: files }, { message_id: localId, role: "assistant", content: "" }] }));
    try {
      const response = await api(`threads/${id}/turn`, { method: "POST", body: JSON.stringify({ text: requestText, model, attachments: files }), signal: controller.signal });
      if (!response.body || !response.headers.get("content-type")?.includes("text/event-stream")) throw new Error("The live response is unavailable. Reopen this chat before sending again.");
      setText(""); setAttachments([]);
      await readEvents(response.body, event => {
        if (generation.current !== version) return;
        if (event.seq !== undefined) { if (event.seq <= lastSeq) return; lastSeq = event.seq; }
        const data = event.data;
        if (event.type === "error") throw new Error(String(data.message));
        if (event.type === "done") completed = true;
        setSnapshot(current => {
          if (!current) return current;
          if (event.type === "step") return { ...current, steps: upsert(current.steps, data as unknown as Step, "step_id") };
          if (event.type === "card" && visibleCard(data as unknown as Card, founder)) return { ...current, cards: upsert(current.cards, data as unknown as Card, "card_id") };
          if (event.type === "token" || event.type === "receipt") return { ...current, messages: current.messages.map(message => message.message_id !== localId ? message : { ...message, ...(event.type === "token" ? { content: message.content + String(data.text ?? "") } : { receipt: data as unknown as Receipt }) }) };
          return current;
        });
      });
      if (!completed) throw new Error("The connection ended before the answer finished. Reopen this chat before sending again.");
      await load(id, version); await refreshThreads();
    } catch (err) {
      if (!controller.signal.aborted) { setError(problem(err)); await load(id, version).catch(() => {}); }
    } finally { sendingRef.current = false; setSending(false); streamAbort.current = null; }
  }

  const done = snapshot?.steps.filter(step => step.status === "done").length ?? 0;
  const steps = snapshot?.steps ?? [];
  const cards = snapshot?.cards.filter(card => visibleCard(card, founder) && (!card.status || ["pending", "awaiting_confirmation"].includes(card.status))) ?? [];
  const lastAnswer = snapshot?.messages.filter(message => message.role === "assistant").at(-1)?.message_id;
  const confirmation = cards.map(card => <section className="cw-confirm" key={card.card_id}><strong className="cw-eyebrow">NEEDS YOUR OK</strong><p>{clean(card.summary)}</p>{card.cost_estimate_usd !== undefined && <p className="cw-meta">Estimated {dollars(card.cost_estimate_usd)}</p>}<p className="cw-note">Nothing runs until you confirm.</p><div className="cw-actions"><button className="cw-primary" disabled={!!cardBusy || sending} onClick={() => void decide(card, "confirm")}>{cardBusy === card.card_id ? "Saving…" : "Confirm"}</button><button disabled={!!cardBusy || sending} onClick={() => void decide(card, "cancel")}>Cancel</button></div></section>);
  return <div className={`command-window${menu ? " cw-menu-open" : ""}${work ? " cw-work-open" : ""}`} onKeyDown={event => { if (event.key === "Escape") { if (work) closeWork(); if (menu) closeMenu(); } }}>
    <a className="cw-skip" href="#cw-message">Skip to message</a>
    <header className="cw-mobile-top"><img src="/brand/tervory-logo-reversed.png" alt="Tervory" /><button ref={menuButton} aria-expanded={menu} aria-controls="cw-sidebar" onClick={() => setMenu(true)}>Menu</button></header>
    <aside className="cw-sidebar" id="cw-sidebar" aria-label="Chats and navigation" inert={work ? true : undefined}>
      <div className="cw-brand"><img src="/brand/tervory-logo-reversed.png" alt="Tervory" /><button className="cw-mobile-only" ref={menuClose} onClick={closeMenu}>Close</button></div>
      <a className="cw-account" href="/onboarding">{account}</a>
      <nav aria-label="Workspace"><a href="/control">Dashboard</a><a href="/matters">Projects</a><a href="/chats" aria-current="page">Chats</a><SquadLinks active founder={founder} /></nav>
      <p className="cw-eyebrow">CHATS</p><button className="cw-new" disabled={busy || sending} onClick={() => void newThread()}>+ New chat</button>
      <input type="search" aria-label="Search chats" placeholder="Search chats" value={query} onChange={event => setQuery(event.target.value)} />
      <div className="cw-threads">{threads.filter(thread => thread.title.toLowerCase().includes(query.toLowerCase())).map(thread => <button key={thread.thread_id} className={selected === thread.thread_id ? "selected" : ""} disabled={sending} aria-current={selected === thread.thread_id ? "page" : undefined} onClick={() => void choose(thread.thread_id)}><span>{clean(thread.title)}</span><small>Spent {dollars(thread.spent_usd)} · saved {dollars(thread.saved_usd)}</small></button>)}{!threads.length && <p className="cw-note">Your saved chats will appear here.</p>}</div>
      <nav className="cw-bottom-nav">{founder && <a href="/ledger">Ledger</a>}<a href="/billing">Billing</a><a href="/data">Files</a><a href="/onboarding">Settings</a></nav>
    </aside>
    <main className="cw-chat" inert={menu || work ? true : undefined}>
      <header className="cw-thread-header"><div><h1>{snapshot ? clean(snapshot.thread.title) : selected ? "Loading chat…" : "A new conversation"}</h1>{snapshot && <button className="cw-rename" disabled={sending || busy} onClick={() => { setTitle(snapshot.thread.title); setRenaming(true); }}>Rename</button>}</div><button className="cw-work-tab" ref={workButton} onClick={() => setWork(true)} aria-expanded={work}>Work {done}/{steps.length}</button><div className="cw-totals"><a href="#cw-costs">Spent {dollars(snapshot?.thread.spent_usd)}</a><a className="cw-saving" href="#cw-costs">Saved {dollars(snapshot?.thread.saved_usd)}</a></div></header>
      {renaming && <form className="cw-rename-form" onSubmit={rename}><label>Chat name<input autoFocus value={title} maxLength={160} required onChange={event => setTitle(event.target.value)} /></label><button disabled={busy}>Save</button><button type="button" onClick={() => setRenaming(false)}>Cancel</button></form>}
      {error && <div className="cw-error" role="alert">{error}<button disabled={sending || busy} onClick={() => { setError(""); void (selected ? load(selected) : refreshThreads()).catch(err => setError(problem(err))); }}>Reload</button></div>}
      <div className="cw-messages" aria-label="Conversation" aria-busy={sending || busy}>
        {!selected && <section className="cw-empty"><h2>What would you like to do?</h2><p>Start a chat to ask a question or give your team some work. Your conversation and progress stay together.</p><button disabled={busy} onClick={() => void newThread()}>Start a new chat</button></section>}
        <span id="cw-costs" className="cw-anchor" />
        {snapshot?.messages.map(message => <article key={message.message_id} className={`cw-message cw-${message.role}`}><div className="cw-message-text">{clean(message.content) || (sending && message.role === "assistant" ? "Working…" : "")}</div>{message.attachments?.length ? <ul className="cw-files">{message.attachments.map((file, i) => <li key={i}>{clean(file.name)}</li>)}</ul> : null}{message.role === "assistant" && (message.receipt ? <CostReceipt receipt={message.receipt} founder={founder} threadId={selected!} messageId={message.message_id} /> : <p className="cw-note">{sending ? "Cost details arrive when this answer is complete." : "Cost details are not available for this answer."}</p>)}{message.message_id === lastAnswer && confirmation}</article>)}
        {!lastAnswer && confirmation}<div ref={bottom} />
      </div>
      <form className="cw-composer" onSubmit={send}><div className="cw-input"><textarea id="cw-message" aria-label="Message Tervory" placeholder="Ask Tervory, or describe a change to build…" maxLength={20000} value={text} disabled={!snapshot || sending} onChange={event => setText(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} /><label className="cw-attach">Attach<input type="file" multiple aria-label="Attach files" disabled={!snapshot || busy || sending} onChange={event => { void attach(event.target.files); event.currentTarget.value = ""; }} /></label><button className="cw-send" disabled={!snapshot || !text.trim() || sending || busy}>{sending ? "Sending…" : "Send"}</button></div><div className="cw-composer-meta"><label>{founder ? "Model" : "Answer option"}<select aria-label={founder ? "Model" : "Answer option"} value={model} disabled={sending} onChange={event => setModel(event.target.value)}><option value="auto">Auto</option>{models.map(option => <option key={option.value} value={option.value}>{option.label} · {dollars(option.inputPerM)} in / {dollars(option.outputPerM)} out per million tokens</option>)}</select></label><small>Auto chooses the cheapest proven option. Every answer shows its cost.</small></div>{!!attachments.length && <ul className="cw-files">{attachments.map((file, i) => <li key={i}>{clean(file.name)} <button type="button" aria-label={`Remove ${file.name}`} disabled={sending} onClick={() => setAttachments(files => files.filter((_, index) => index !== i))}>×</button></li>)}</ul>}</form>
    </main>
    <aside className="cw-work" aria-label="Work" inert={menu ? true : undefined}><header><h2>Work</h2><span className="cw-meta">{done} of {steps.length} done</span><button className="cw-mobile-only" ref={workClose} aria-label="Close work" onClick={closeWork}>×</button></header>{!steps.length && <p className="cw-note">The steps for this chat will appear here when work begins.</p>}<ol>{steps.map(step => <li className={`cw-step cw-step-${step.status}`} key={step.step_id}><span className="cw-status-dot" aria-hidden="true" /><div><strong>{clean(step.label)}</strong><small>{clean(step.actor)}</small>{safeLink(step.link) && <a href={safeLink(step.link)} target="_blank" rel="noreferrer">Open result ↗</a>}</div><span className="cw-step-state">{statusLabel[step.status]}</span></li>)}</ol><p className="cw-live" role="status">{sending ? "Receiving your answer…" : busy ? "Loading…" : "Progress is saved with this chat."}</p></aside>
  </div>;
}
