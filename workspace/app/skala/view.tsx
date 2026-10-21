"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { SquadLinks } from "../squad-links";
import { caseRecord, type EvalResult } from "./record";
import {
  agentChoices,
  applyApproval,
  applyEval,
  approvalRowText,
  confirmApprove,
  costLabel,
  scoreDate,
  scoreLabel,
  STATES,
  versionAction,
  visibleLibrary,
  type LibrarySkill,
} from "./library";

const TOP_LINKS = [
  { href: "/ledger", label: "Dashboard" },
  { href: "/tasks", label: "Projects" },
  { href: "/", label: "Chats" },
] as const;

const BOTTOM_LINKS = [
  { href: "/onboarding", label: "Settings" },
  { href: "/", label: "Support" },
] as const;

const SKALA_LOGO = { src: "/brand/skala-on-dark.png", width: 185, height: 44 };
const SKALA_MARK = { src: "/brand/skala-on-dark.png", width: 168, height: 40 };

type Notice = { tone: "ok" | "err"; text: string };

function SearchIcon() {
  return (
    <svg className="search-icon" width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <circle cx="7.5" cy="7.5" r="4.75" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M11.2 11.2 L15.5 15.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

async function readSkills(): Promise<LibrarySkill[] | null> {
  const response = await fetch("/api/skala");
  if (!response.ok) return null;
  const data: unknown = await response.json().catch(() => null);
  if (!Array.isArray(data)) return null;
  return data as LibrarySkill[];
}

export function SkalaApp({
  accountName,
  skills: initialSkills,
  loadError,
}: {
  accountName: string | null;
  skills: LibrarySkill[];
  loadError: string | null;
}) {
  const [skills, setSkills] = useState(initialSkills);
  const [menu, setMenu] = useState(false);
  const [narrow, setNarrow] = useState(false);
  const [query, setQuery] = useState("");
  const [agentId, setAgentId] = useState("");
  const [state, setState] = useState("");
  const [notice, setNotice] = useState<Notice | null>(loadError ? { tone: "err", text: loadError } : null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [pending, setPending] = useState<LibrarySkill | null>(null);
  const [rowRefusal, setRowRefusal] = useState<{ key: string; text: string } | null>(null);
  const [record, setRecord] = useState<{ key: string; result: EvalResult } | null>(null);
  const searchId = useId();
  const agentFilterId = useId();
  const stateFilterId = useId();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const account = accountName?.trim() || "Your account";

  useEffect(() => {
    const media = window.matchMedia("(max-width: 800px)");
    const apply = () => setNarrow(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setMenu(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (menu && narrow) closeRef.current?.focus();
  }, [menu, narrow]);

  function openApprove(skill: LibrarySkill) {
    setPending(skill);
  }

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || !pending || dialog.open) return;
    dialog.showModal();
  }, [pending]);

  function closeApprove() {
    dialogRef.current?.close();
    setPending(null);
  }

  async function refreshAfter(next: LibrarySkill[]) {
    setSkills(next);
    const live = await readSkills();
    if (live) setSkills(live);
  }

  async function run(skill: LibrarySkill, action: "evals" | "approve" | "retire") {
    const key = `${skill.id}@${skill.version}:${action}`;
    setBusyKey(key);
    setNotice(null);
    try {
      const response = await fetch("/api/skala", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ id: skill.id, version: skill.version, action }),
      });
      const payload = (await response.json().catch(() => null)) as Record<string, unknown> | null;
      if (response.status === 404) {
        setNotice({ tone: "err", text: "That action was refused. Sign in as a founder and try again." });
        return;
      }
      if (response.status === 403) {
        setNotice({ tone: "err", text: "That action was refused. Reload the page and try again." });
        return;
      }
      if (!response.ok || !payload) {
        const refused = action === "approve" ? approvalRowText(response.status, payload?.error) : null;
        if (refused) {
          setRowRefusal({ key: `${skill.id}@${skill.version}`, text: refused });
          closeApprove();
          return;
        }
        setNotice({ tone: "err", text: failureText(action, response.status) });
        return;
      }
      if (action === "approve") {
        setRowRefusal(null);
        await refreshAfter(applyApproval(skills, skill.id, skill.version));
        setNotice({ tone: "ok", text: `${skill.id} ${skill.version} is approved. The previous approved version is retired.` });
        closeApprove();
        return;
      }
      if (action === "retire") {
        await refreshAfter(skills.map((row) => (
          row.id === skill.id && row.version === skill.version ? { ...row, state: "retired" } : row
        )));
        setNotice({ tone: "ok", text: `${skill.id} ${skill.version} is retired.` });
        return;
      }
      const result = payload as Partial<EvalResult>;
      if (typeof result.score !== "number" || typeof result.state !== "string" || !result.details) {
        setNotice({ tone: "err", text: "Evals could not be run. Reload the page and try again." });
        return;
      }
      const evalResult = result as EvalResult;
      const at = new Date().toISOString();
      await refreshAfter(applyEval(skills, skill.id, skill.version, evalResult.score, evalResult.state, at));
      setRecord({ key: `${skill.id}@${skill.version}`, result: evalResult });
      const passed = evalResult.gate === "passed";
      setNotice({
        tone: passed ? "ok" : "err",
        text: passed
          ? `${skill.id} ${skill.version} passed and is now ${evalResult.state}.`
          : `${skill.id} ${skill.version} did not pass. It stays ${evalResult.state}. Review the cases below.`,
      });
    } catch {
      setNotice({ tone: "err", text: "The library could not be reached. Try again in a moment." });
    } finally {
      setBusyKey(null);
    }
  }

  const groups = visibleLibrary(skills, query, agentId, state);
  const filtered = Boolean(query.trim() || agentId || state);
  const panelHidden = narrow && !menu;

  return (
    <div className={menu ? "skala menu-open" : "skala"}>
      <header className="sk-top">
        <img src={SKALA_MARK.src} alt="Skala" width={SKALA_MARK.width} height={SKALA_MARK.height} />
        <button
          type="button"
          className="sk-menu"
          aria-expanded={menu}
          aria-controls="sk-panel"
          onClick={() => setMenu((open) => !open)}
        >
          {menu ? "Close" : "Menu"}
        </button>
      </header>
      <button className="sk-dim" type="button" hidden={!menu} aria-label="Close menu" onClick={() => setMenu(false)} />
      <aside id="sk-panel" className="sk-panel" aria-label="Skala" aria-hidden={panelHidden || undefined} inert={panelHidden ? true : undefined}>
        <img className="sk-logo" src={SKALA_LOGO.src} alt="Skala" width={SKALA_LOGO.width} height={SKALA_LOGO.height} />
        <button ref={closeRef} className="sk-close" type="button" onClick={() => setMenu(false)}>Close</button>
        <nav className="sk-nav" aria-label="Account" onClick={() => setMenu(false)}>
          <p className="sk-account">{account}</p>
          {TOP_LINKS.map((link) => (
            <a key={link.label} href={link.href}>{link.label}</a>
          ))}
        </nav>
        <SquadLinks className="sk-nav squad-nav" />
        <div className="sk-rule" />
        <nav className="sk-nav" aria-label="Library">
          <button type="button" className="on" aria-current="page" onClick={() => setMenu(false)}>Library</button>
        </nav>
        <div className="sk-spacer" />
        <div className="sk-rule" />
        <div className="sk-foot">
          <img className="sk-tervory" src="/brand/tervory-logo-reversed.png" alt="Tervory" width={186} height={34} />
          <nav className="sk-nav" aria-label="Workspace" onClick={() => setMenu(false)}>
            {BOTTOM_LINKS.map((link) => (
              <a key={link.label} href={link.href}>{link.label}</a>
            ))}
          </nav>
        </div>
      </aside>

      <div className="sk-main" data-scroll-root>
        <div className="sk-body">
          <header className="sk-header">
            <div>
              <h1>Skala</h1>
              <p>Every skill, with its versions and scores.</p>
            </div>
            <a className="sk-examples" href="/skala/gold">Check examples</a>
          </header>

          <form className="sk-search" role="search" onSubmit={(event: FormEvent) => event.preventDefault()}>
            <SearchIcon />
            <label className="sk-sr" htmlFor={searchId}>Search skills</label>
            <input
              id={searchId}
              type="search"
              value={query}
              placeholder="Search skills"
              onChange={(event) => setQuery(event.target.value)}
            />
          </form>

          <div className="sk-filters">
            <label htmlFor={agentFilterId}>
              Agent
              <select id={agentFilterId} value={agentId} onChange={(event) => setAgentId(event.target.value)}>
                <option value="">All agents</option>
                {agentChoices(skills).map((choice) => (
                  <option key={choice.id} value={choice.id}>{choice.label}</option>
                ))}
              </select>
            </label>
            <label htmlFor={stateFilterId}>
              State
              <select id={stateFilterId} value={state} onChange={(event) => setState(event.target.value)}>
                <option value="">All states</option>
                {STATES.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </label>
          </div>

          {notice ? <p className={notice.tone === "err" ? "sk-err" : "sk-note"} role={notice.tone === "err" ? "alert" : "status"}>{notice.text}</p> : null}

          {loadError ? null : groups.length === 0 ? (
            <p className="sk-empty">{query.trim() ? "Nothing matches that search." : filtered ? "Nothing matches those filters." : "No skills yet."}</p>
          ) : (
            <div className="sk-library">
              {groups.map((group) => (
                <section key={group.id} className="sk-group" aria-label={group.label}>
                  <div className="sk-group-head">
                    {group.logo ? (
                      <div className="sk-group-mark">
                        <img src={group.logo} alt="" width={group.logoWidth} height={group.logoHeight} />
                      </div>
                    ) : null}
                    <h2>{group.label}</h2>
                  </div>
                  <ul className="sk-skills">
                    {group.skills.map((skill) => (
                      <li key={skill.id} className="sk-skill">
                        <h3>{skill.id}</h3>
                        <p>{skill.description}</p>
                        <ul className="sk-versions">
                          {skill.versions.map((version) => {
                            const action = versionAction(version);
                            const key = `${version.id}@${version.version}`;
                            const shown = record?.key === key ? caseRecord(record.result) : null;
                            return (
                              <li key={key} className="sk-version">
                                <span className="sk-meta">{version.version}</span>
                                <span className={version.state === "approved" ? "sk-state approved" : "sk-state"}>{version.state}</span>
                                <span className="sk-meta">{scoreLabel(version.last_eval_score)}</span>
                                {scoreDate(version.last_eval_at) ? <span className="sk-meta">{scoreDate(version.last_eval_at)}</span> : null}
                                <span className="sk-meta">{costLabel(version)}</span>
                                {!version.present && version.state !== "approved" ? <span className="sk-gone">This version is no longer in the folder.</span> : null}
                                {action === "evals" ? (
                                  <button type="button" disabled={busyKey !== null} onClick={() => run(version, "evals")}>
                                    {busyKey === `${key}:evals` ? "Running evals…" : "Run evals"}
                                  </button>
                                ) : null}
                                {action === "approve" ? (
                                  <>
                                    <button type="button" className="primary" disabled={busyKey !== null} onClick={() => openApprove(version)}>
                                      Approve
                                    </button>
                                    {rowRefusal?.key === key ? <p className="sk-err sk-row-err" role="alert">{rowRefusal.text}</p> : null}
                                  </>
                                ) : null}
                                {action === "retire" ? (
                                  <button type="button" disabled={busyKey !== null} onClick={() => run(version, "retire")}>
                                    {busyKey === `${key}:retire` ? "Retiring…" : "Retire"}
                                  </button>
                                ) : null}
                                {shown?.ok ? (
                                  <div className="sk-cases">
                                    <p>Cases</p>
                                    {shown.cases.map((line) => (
                                      <article key={line.key}>
                                        <p>{line.name} · {line.passed ? "passed" : "failed"}</p>
                                        <p>Goal</p>
                                        <pre>{line.goal}</pre>
                                        <p>Result</p>
                                        <pre>{line.result}</pre>
                                      </article>
                                    ))}
                                  </div>
                                ) : shown ? <p className="sk-err">{shown.message} Run evals again.</p> : null}
                              </li>
                            );
                          })}
                        </ul>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </div>
      </div>

      <dialog ref={dialogRef} className="sk-dialog" aria-labelledby="approve-title" onClose={() => setPending(null)}>
        <h2 id="approve-title">{pending ? confirmApprove(pending.id, pending.version) : "Approve this version?"}</h2>
        <div className="sk-dialog-actions">
          <button type="button" className="primary" disabled={!pending || busyKey !== null} onClick={() => pending && run(pending, "approve")}>
            {pending && busyKey === `${pending.id}@${pending.version}:approve` ? "Approving…" : "Approve"}
          </button>
          <button type="button" onClick={closeApprove}>Cancel</button>
        </div>
      </dialog>
    </div>
  );
}

function failureText(action: "evals" | "approve" | "retire", status: number): string {
  if (action === "approve" && status === 409) return "That version is not in staging. Run evals until it is, then approve it.";
  if (action === "evals") return "Evals could not be run. Reload the page and try again.";
  if (action === "approve") return "Approve could not be saved. Reload the page and try again.";
  return "Retire could not be saved. Reload the page and try again.";
}
