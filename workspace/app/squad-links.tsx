"use client";

import { createContext, useContext, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { usePathname } from "next/navigation";
import { logoWidth, pathMatches, squadKey, squadMembers } from "./product-nav";

/** True inside the shared shell, so a page's own copy of this control stays out of the list. */
export const InAppShell = createContext(false);

const LOGO_HEIGHT = 40;

/**
 * One Squad button. The member list is a pop-out beside the sidebar.
 * Pages still render this; inside the shell only the active copy is shown.
 */
export function SquadLinks({
  active = false,
  founder = false,
  className,
  linkClassName,
}: {
  active?: boolean;
  founder?: boolean;
  className?: string;
  linkClassName?: string;
}) {
  const nested = useContext(InAppShell);
  if (nested && !active) return null;
  return (
    <SquadControl
      founder={founder}
      className={active ? undefined : className}
      linkClassName={active ? undefined : linkClassName}
    />
  );
}

function SquadControl({
  founder,
  className,
  linkClassName,
}: {
  founder: boolean;
  className?: string;
  linkClassName?: string;
}) {
  const members = squadMembers(founder);
  const pathname = usePathname() ?? "";
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(false);
  const titleId = useId();

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) {
      if (wasOpen.current) {
        wasOpen.current = false;
        buttonRef.current?.focus();
      }
      return;
    }
    wasOpen.current = true;
    popRef.current?.querySelector<HTMLElement>("[data-squad-member]")?.focus();
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
    }
    function onPointer(event: PointerEvent) {
      const target = event.target as Node;
      if (popRef.current?.contains(target) || buttonRef.current?.contains(target)) return;
      setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  function close() {
    setOpen(false);
  }

  function onPopKey(event: KeyboardEvent<HTMLDivElement>) {
    const nodes = Array.from(popRef.current?.querySelectorAll<HTMLElement>("[data-squad-member]") ?? []);
    const index = nodes.indexOf(document.activeElement as HTMLElement);
    if (event.key === "Tab") {
      const items = Array.from(popRef.current?.querySelectorAll<HTMLElement>("a, button") ?? []);
      const first = items[0];
      const last = items[items.length - 1];
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
      return;
    }
    const next = squadKey(event.key, index, nodes.length);
    if (next === "close") {
      event.preventDefault();
      close();
      return;
    }
    if (typeof next === "number") {
      event.preventDefault();
      nodes[next]?.focus();
    }
  }

  const pop = (
    <div
      ref={popRef}
      id="squad-popout"
      className="shell-pop"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      hidden={!open}
      onKeyDown={onPopKey}
    >
      <div className="shell-pop-head">
        <p id={titleId} className="shell-kicker">Squad</p>
        <button type="button" className="shell-pop-close" onClick={close}>Close</button>
      </div>
      <ul className="shell-members">
        {members.map((member) => {
          const here = pathMatches(member.href, pathname);
          return (
            <li key={member.href}>
              <a
                className={linkClassName}
                href={member.href}
                data-squad-member=""
                aria-current={here ? "page" : undefined}
                onClick={close}
              >
                <img src={member.logo} alt="" width={logoWidth(member, LOGO_HEIGHT)} height={LOGO_HEIGHT} />
                <span className="shell-member-name">{member.label}</span>
                <span className="shell-member-job">{member.job}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );

  return (
    <div className={className ? `shell-squad ${className}` : "shell-squad"}>
      <button
        ref={buttonRef}
        id="squad-button"
        type="button"
        className="shell-squad-button"
        aria-expanded={open}
        aria-controls="squad-popout"
        aria-haspopup="dialog"
        onClick={() => setOpen((value) => !value)}
      >
        Squad
      </button>
      {mounted ? createPortal(pop, document.body) : null}
    </div>
  );
}
