"use client";
import { useEffect, useRef } from "react";

export function useDialog(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(close); closeRef.current = close;
  useEffect(() => {
    if (!open || !ref.current) return;
    const dialog = ref.current, previous = document.activeElement as HTMLElement | null;
    const menu = dialog.closest(".rig")?.querySelector<HTMLElement>(".menu");
    const controls = () => Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')).filter(node => node.getClientRects().length);
    controls()[0]?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); closeRef.current(); }
      if (event.key !== "Tab") return;
      const nodes = controls(), first = nodes[0], last = nodes.at(-1);
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
    };
    dialog.addEventListener("keydown", key);
    return () => { dialog.removeEventListener("keydown", key); const box = previous?.getBoundingClientRect();
      if (previous?.isConnected && previous.matches("button, a[href], input, select, textarea, [tabindex]") && box && box.right > 0 && box.left < innerWidth && box.bottom > 0 && box.top < innerHeight) previous.focus();
      else menu?.focus(); };
  }, [open]);
  return ref;
}
