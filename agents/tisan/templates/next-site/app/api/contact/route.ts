// Placeholder. The form posts here. Nothing is stored or forwarded.
export async function POST(): Promise<Response> {
  return Response.json({ ok: true }, { status: 202 });
}
