"use client";

import { useCallback, useRef, useState } from "react";

const SEED = `<h1>Base brief — Kauai Gun Company</h1>
<p>Open the FFL file for <strong>Kauai Gun Company</strong> (Kapaa, HI). Confirm the transfer desk hours, the 4473 staging shelf, and who signs outbound Form 3s this week.</p>
<p><span style="background:#fde68a;color:#78350f">Highlight:</span> weekend transfers need a second checker on the counter before the safe is opened.</p>
<ul>
<li>Website contact on file — confirm it still rings the shop floor.</li>
<li>Email aliases for receiving and for ATF correspondence stay separate.</li>
<li>Next batch: Capstone list refresh after Friday's intake.</li>
</ul>
<p>Colour the action items as you walk the floor. This page is the working brief — type into it.</p>`;

const COLOURS = [
  { label: "Ink", value: "#111827" },
  { label: "Ocean", value: "#0369a1" },
  { label: "Forest", value: "#166534" },
  { label: "Wine", value: "#9f1239" },
  { label: "Amber", value: "#b45309" },
];

const MARKS = [
  { label: "Clear", value: "transparent" },
  { label: "Yellow", value: "#fde68a" },
  { label: "Mint", value: "#bbf7d0" },
  { label: "Sky", value: "#bae6fd" },
  { label: "Rose", value: "#fecdd3" },
];

export function BaseDocument() {
  const ref = useRef<HTMLDivElement>(null);
  const [ink, setInk] = useState(COLOURS[0].value);
  const [mark, setMark] = useState(MARKS[1].value);

  const run = useCallback((cmd: string, value?: string) => {
    ref.current?.focus();
    document.execCommand(cmd, false, value);
  }, []);

  return (
    <main className="base-public" aria-label="Base document">
      <header className="base-public-head">
        <p className="base-public-eyebrow">Base</p>
        <h1>Typed brief</h1>
        <p className="base-public-lede">
          A working document with colour — write the brief, mark the floor notes, keep the file in one place.
        </p>
      </header>

      <div className="base-public-toolbar" role="toolbar" aria-label="Document tools">
        <button type="button" onClick={() => run("bold")}>Bold</button>
        <button type="button" onClick={() => run("italic")}>Italic</button>
        <button type="button" onClick={() => run("insertUnorderedList")}>List</button>
        <label>
          Ink
          <select
            value={ink}
            onChange={(e) => {
              setInk(e.target.value);
              run("foreColor", e.target.value);
            }}
          >
            {COLOURS.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </label>
        <label>
          Mark
          <select
            value={mark}
            onChange={(e) => {
              setMark(e.target.value);
              run("hiliteColor", e.target.value);
            }}
          >
            {MARKS.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div
        ref={ref}
        className="base-public-page"
        contentEditable
        suppressContentEditableWarning
        role="textbox"
        aria-multiline="true"
        aria-label="Base document body"
        dangerouslySetInnerHTML={{ __html: SEED }}
      />
    </main>
  );
}
