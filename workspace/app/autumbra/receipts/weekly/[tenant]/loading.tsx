/** Stream the existing receipt shape while authentication and the data read finish. */
export default function LoadingReceipts() {
  return <section aria-busy="true" style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 720, overflowWrap: "anywhere" }}>
    <h1>Your Autumbra weekly update</h1>
    <p>This is the receipt page linked from your Autumbra owner email. It lists what Autumbra
      checked, what it found, and what it did for your site this week.</p>
    <p>— recorded</p>
    <dl><dt>Cost</dt><dd>—</dd><dt>Would have cost</dt><dd>—</dd></dl>
  </section>;
}
