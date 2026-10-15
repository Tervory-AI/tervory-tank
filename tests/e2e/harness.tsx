import { useState } from "react";
import { createRoot } from "react-dom/client";
import type { StartRequest } from "../../workspace/app/onboarding/csv";
import { Wizard, type RunProgress } from "../../workspace/app/onboarding/wizard";

function SignUp({ onDone }: { onDone: () => void }) {
  return (
    <form aria-label="Sign up" onSubmit={(event) => { event.preventDefault(); onDone(); }}>
      <h1>Create your account</h1>
      <p className="lede">Use your work email. You will create or join an organization next.</p>
      <label className="map-row">Email <input name="email" type="email" autoComplete="email" required /></label>
      <label className="map-row">Password <input name="password" type="password" autoComplete="new-password" required minLength={8} /></label>
      <div className="actions"><button className="primary" type="submit">Sign up</button></div>
    </form>
  );
}

function App() {
  const [phase, setPhase] = useState<"signup" | "app">("signup");
  const [org, setOrg] = useState<string | null>(null);
  const [uploads, setUploads] = useState(0);
  const [progress, setProgress] = useState<RunProgress | null>(null);
  if (phase === "signup") return <SignUp onDone={() => setPhase("app")} />;
  return (
    <div data-uploads={uploads}>
      <Wizard
        orgName={org}
        orgSlot={(
          <form
            aria-label="Create or join an organization"
            onSubmit={(event) => {
              event.preventDefault();
              const name = String(new FormData(event.currentTarget).get("org") || "").trim();
              if (name) setOrg(name);
            }}
          >
            <label className="map-row">Organization name <input name="org" type="text" required /></label>
            <div className="actions"><button className="primary" type="submit">Create organization</button></div>
          </form>
        )}
        engines={["ffl"]}
        enginesError={null}
        onRetryEngines={() => undefined}
        onStart={async (body: StartRequest) => {
          setUploads((count) => count + 1);
          const records = Array.from({ length: body.count }, (_, index) => ({
            status: index === 0 ? "running" : "queued",
            passes: index === 0 ? { "1a": { skill: "base.normalize" } } : {},
          }));
          setProgress({
            summary: { total: body.count, done: 0, failed: 0, pending: body.count },
            records,
          });
          return { batch: body.batch };
        }}
        progress={progress}
      />
    </div>
  );
}

const root = document.getElementById("root");
if (root) createRoot(root).render(<App />);
