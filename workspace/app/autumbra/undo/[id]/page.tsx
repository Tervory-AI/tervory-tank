import { UndoButton } from "../UndoButton";

/** One-tap undo landing — linked from the owner update email. Token is the credential. */
export default async function UndoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{ token?: string }>;
}) {
  const resolved = await params;
  const query = searchParams ? await searchParams : {};
  const token = typeof query.token === "string" ? query.token : "";

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
      <UndoButton receiptId={resolved.id} token={token} />
      <p style={{ marginTop: "2rem", fontSize: "0.95rem", color: "#6b7280" }}>
        Nothing from your logs is kept. If you need help, reply to your Autumbra update email.
      </p>
    </main>
  );
}
