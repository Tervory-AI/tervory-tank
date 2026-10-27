import { UndoButton } from "../UndoButton";

/** One-tap undo landing — linked from the owner update email. Plain English. */
export default async function UndoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{ tenant?: string; site?: string; rule?: string }>;
}) {
  const resolved = await params;
  const query = searchParams ? await searchParams : {};
  const tenantId = typeof query.tenant === "string" ? query.tenant : "";
  const site = typeof query.site === "string" ? query.site : "coolify.tervory.com";
  const ruleId = typeof query.rule === "string" ? query.rule : "";

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 720 }}>
      <h1>Undo an Autumbra shield</h1>
      <p>
        Autumbra blocked an address that was attacking your site. If that caused a problem
        for you, tap the button below and we will remove that block.
      </p>
      <p style={{ color: "#4b5563" }}>
        Reference: <code>{resolved.id}</code>
      </p>
      <UndoButton
        receiptId={resolved.id}
        tenantId={tenantId}
        site={site}
        ruleId={ruleId}
      />
      <p style={{ marginTop: "2rem", fontSize: "0.95rem", color: "#6b7280" }}>
        Nothing from your logs is kept. If you need help, reply to your Autumbra update email.
      </p>
    </main>
  );
}
