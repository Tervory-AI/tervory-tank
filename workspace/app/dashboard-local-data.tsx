"use client";

import { useSyncExternalStore } from "react";

function subscribe(onChange: () => void) {
  let timer: ReturnType<typeof setTimeout>;
  const update = () => {
    clearTimeout(timer);
    onChange();
    const now = new Date();
    const nextHour = new Date(now);
    nextHour.setHours(now.getHours() + 1, 0, 0, 0);
    timer = setTimeout(update, nextHour.getTime() - now.getTime());
  };
  update();
  window.addEventListener("focus", update);
  document.addEventListener("visibilitychange", update);
  return () => {
    clearTimeout(timer);
    window.removeEventListener("focus", update);
    document.removeEventListener("visibilitychange", update);
  };
}

const localHour = () => new Date().getHours();
const serverHour = () => null;

export function DashboardGreeting({ firstName }: { firstName: string }) {
  const hour = useSyncExternalStore(subscribe, localHour, serverHour);
  // The server does not know the client's time zone. Reserve the frame's space
  // until the browser can supply it, without a guessed greeting or loading copy.
  const greeting = hour === null ? null : hour < 12 ? "Good morning, " : hour < 18 ? "Good afternoon, " : "Good evening, ";
  return <h1>{greeting === null ? null : greeting + firstName}</h1>;
}
