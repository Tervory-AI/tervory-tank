"use client";

import { useState } from "react";
import { DEMO_BANNER, type DemoProduct } from "@/lib/demo-fixtures";

export function DemoView({ product }: { product: DemoProduct }) {
  const [sectionId, setSectionId] = useState(product.sections[0]?.id ?? "");
  const section = product.sections.find((s) => s.id === sectionId) ?? product.sections[0];
  const [itemId, setItemId] = useState(section?.items[0]?.id ?? "");
  const selected = section?.items.find((i) => i.id === itemId) ?? section?.items[0];

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px", color: "#001840" }}>
      <div role="status" style={{ background: "#F4F6FB", border: "1px solid #B8BFD0", padding: "8px 12px", fontFamily: "var(--font-mono, monospace)", fontSize: 13 }}>
        {DEMO_BANNER}
      </div>
      <h1 style={{ fontWeight: 300, marginBottom: 4 }}>{product.name}</h1>
      <p style={{ marginTop: 0 }}>{product.tagline}</p>
      <div role="tablist" style={{ display: "flex", gap: 8, margin: "16px 0" }}>
        {product.sections.map((s) => (
          <button
            key={s.id}
            role="tab"
            aria-selected={s.id === section?.id}
            onClick={() => {
              setSectionId(s.id);
              setItemId(s.items[0]?.id ?? "");
            }}
            style={{ padding: "6px 12px", border: "1px solid #B8BFD0", background: s.id === section?.id ? "#001840" : "#fff", color: s.id === section?.id ? "#fff" : "#001840", cursor: "pointer" }}
          >
            {s.label}
          </button>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr)", gap: 16 }}>
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {section?.items.map((i) => (
            <li key={i.id} style={{ marginBottom: 8 }}>
              <button
                onClick={() => setItemId(i.id)}
                aria-pressed={i.id === selected?.id}
                style={{ width: "100%", textAlign: "left", padding: 12, border: `1px solid ${i.id === selected?.id ? "#001840" : "#B8BFD0"}`, background: "#fff", cursor: "pointer", color: "#001840" }}
              >
                <strong>{i.title}</strong>
                <div style={{ fontSize: 13 }}>{i.meta} · {i.status}</div>
              </button>
            </li>
          ))}
        </ul>
        <section aria-label="Detail" style={{ border: "1px solid #B8BFD0", padding: 16, background: "#F4F6FB" }}>
          {selected && (
            <>
              <h2 style={{ fontWeight: 300, marginTop: 0 }}>{selected.title}</h2>
              <p style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 13 }}>{selected.meta} · {selected.status}</p>
              {selected.detail.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </>
          )}
        </section>
      </div>
      <p style={{ marginTop: 24 }}>
        <a href="/sign-in">Sign in to use your own data</a>
      </p>
    </main>
  );
}
