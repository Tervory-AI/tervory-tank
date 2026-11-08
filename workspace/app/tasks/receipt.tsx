type Amount = number | string | null | undefined;
function dollars(value: Amount): string {
  if (value == null || value === "" || !Number.isFinite(Number(value)) || Number(value) < 0) return "—";
  const amount = Number(value);
  return amount > 0 && amount < 0.000001 ? "<$0.000001" : `$${amount.toFixed(6)}`;
}

export function TaskReceipt({ cost, baseline, status, ledgerId }: {
  cost: Amount; baseline: Amount; status?: string | null; ledgerId: string | null;
}) {
  return <section aria-label="Run receipt" className="meta">
    <dl>
      <dt>Cost</dt><dd>{ledgerId ? dollars(cost) : "—"}</dd>
      <dt>Would have cost</dt><dd>{ledgerId ? dollars(baseline) : "—"}</dd>
    </dl>
    <p>{!ledgerId ? "Add and complete a task to fill this receipt." : status === "estimated" ? "Estimated paid default comparison." : baseline == null ? "Paid default comparison pending." : "Compared with the paid default model."}</p>
  </section>;
}
