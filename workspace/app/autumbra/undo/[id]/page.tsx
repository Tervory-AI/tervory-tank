/** One-tap undo landing — linked from owner email. */
export default async function UndoPage({
  params,
}: {
  params: Promise<{ id: string }> | { id: string };
}) {
  const resolved = await Promise.resolve(params);
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 720 }}>
      <h1>Undo Autumbra shield</h1>
      <p>Receipt: <code>{resolved.id}</code></p>
      <p>Use Watch <code>/ghost/autumbra/queue/undo</code> with a ThreatPayload to undo.</p>
    </main>
  );
}
