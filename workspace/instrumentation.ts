// Next.js calls register() once per server start (instrumentation is stable since Next 15.0).
// Node runtime only. The client reconcile runs in the background: start-up never waits on it
// and never fails because of it.
export function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    void import("./lib/client-roster")
      .then(({ reconcileClients }) => reconcileClients())
      .catch((error: unknown) => {
        console.warn("client_reconcile_failed", { error: error instanceof Error ? error.constructor.name : typeof error });
      });
  }
}
