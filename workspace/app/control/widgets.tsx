"use client";
import { useState, useTransition } from "react";
import { pauseAction, switchAction } from "./actions";
export function ControlActions({ paused, taskType }: { paused?: boolean | null; taskType?: string }) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string>();
  return <div><button className={`dash-button ${taskType ? "primary" : "danger"}`} disabled={pending || (!taskType && paused == null)} onClick={() => {
    if (taskType && !window.confirm(`Switch ${taskType} to its proven cheaper candidate?`)) return;
    start(async () => { const result = taskType ? await switchAction(taskType) : await pauseAction(!paused); setError(result.error); });
  }}>{pending ? "Saving…" : taskType ? "Switch" : paused == null ? "Paid pause unavailable" : paused ? "Resume paid work" : "Pause all paid work"}</button>{error && <p role="alert" className="dash-problem">{error}</p>}</div>;
}
