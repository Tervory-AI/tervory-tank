"use client";
import { useEffect, useState } from "react";
import type { AccessQueueItem } from "@/lib/tank";
/** Small integration for the conversation window and founder control page. */
export function AccessQueueNotice() {
  const [items, setItems] = useState<AccessQueueItem[]>([]);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const response = await fetch("/access/api/queue", { cache: "no-store" });
        if (!response.ok) throw new Error();
        const result = await response.json() as AccessQueueItem[];
        if (active) { setItems(result); setUnavailable(false); }
      } catch { if (active) setUnavailable(true); }
    }
    void load(); const timer = setInterval(() => void load(), 15000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  return <aside aria-live="polite" style={{ padding: "10px 18px", borderBottom: "1px solid #B8BFD0", background: "#F4F6FB", color: "#001840", fontSize: 12 }}>
    <a href="/access" style={{ color: "inherit" }}>{unavailable ? "Human checks could not be loaded" : items.length ? `Needs a person · ${items.length}` : "Connections · no human checks waiting"}</a>
    {items.length > 0 && <span> — {items.slice(0,3).map(item => new URL(item.site).hostname).join(", ")}</span>}
  </aside>;
}
