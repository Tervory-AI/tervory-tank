import { loadWeeklyReceipts } from "@/lib/autumbra-weekly";

/** Weekly owner-update receipt page — lists that week's receipts, each linked. */
export default async function WeeklyReceiptPage({
  params,
}: {
  params: Promise<{ tenant: string }>;
}) {
  const resolved = await params;
  const tenant = resolved.tenant;
  const { receipts, note } = await loadWeeklyReceipts(tenant);

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
      {note && receipts.length === 0 ? <p style={{ color: "#6b7280" }}>{note}</p> : null}
      {receipts.length === 0 ? (
        <p>No receipts for this week yet.</p>
      ) : (
        <ul style={{ paddingLeft: "1.25rem", lineHeight: 1.6 }}>
          {receipts.map((row) => {
            const id = row.id || "receipt";
            const href = row.url || `/autumbra/undo/${id}`;
            const label = [row.outcome, row.severity, row.site].filter(Boolean).join(" · ") || id;
            return (
              <li key={id} style={{ marginBottom: "0.75rem" }}>
                <a href={href}>{label}</a>
                {row.timestamp ? (
                  <span style={{ color: "#6b7280" }}> — {row.timestamp}</span>
                ) : null}
                {row.advisory_url ? (
                  <>
                    {" "}
                    · <a href={row.advisory_url}>public advisory</a>
                  </>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
      <p style={{ marginTop: "1.5rem", fontSize: "0.95rem", color: "#6b7280" }}>
        Nothing from your logs is kept — we read them, acted, and deleted them. If a shield
        caused a problem, use the Undo link in that same email.
      </p>
    </main>
  );
}
