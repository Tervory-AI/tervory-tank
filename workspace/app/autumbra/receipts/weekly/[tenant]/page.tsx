/** Weekly owner-update receipt page — target of protect.tervory.com/autumbra/receipts/weekly/<tenant>. */
export default async function WeeklyReceiptPage({
  params,
}: {
  params: Promise<{ tenant: string }>;
}) {
  const resolved = await params;
  const tenant = resolved.tenant;
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 720 }}>
      <h1>Your Autumbra weekly update</h1>
      <p>
        This is the receipt page linked from your Autumbra owner email. It lists what Autumbra
        checked, what it found, and what it did for your site this week.
      </p>
      <p style={{ color: "#4b5563" }}>
        Client reference: <code>{tenant}</code>
      </p>
      <p>
        Open numbers in your email (threats found, critical items, addresses blocked) point here.
        Nothing from your logs is kept — we read them, acted, and deleted them.
      </p>
      <p style={{ marginTop: "1.5rem", fontSize: "0.95rem", color: "#6b7280" }}>
        If a shield caused a problem, use the Undo link in that same email.
      </p>
    </main>
  );
}
