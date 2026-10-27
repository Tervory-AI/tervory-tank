/** Weekly owner-update receipt page — target of protect.tervory.com/receipts/weekly/<tenant> links. */
export default async function WeeklyReceiptPage({
  params,
}: {
  params: Promise<{ tenant: string }> | { tenant: string };
}) {
  const resolved = await Promise.resolve(params);
  const tenant = resolved.tenant;
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 720 }}>
      <h1>Autumbra weekly receipts</h1>
      <p>Client: <code>{tenant}</code></p>
      <p>
        This page exists so every link in the owner update email points somewhere real.
        Receipts for this week are listed in the founder console and Watch
        <code> /ghost/autumbra/receipts</code> for this tenant.
      </p>
    </main>
  );
}
