import { rigCall } from "../../rig-server";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: { op?: string } = {};
  try {
    body = (await request.json()) as { op?: string };
  } catch {
    return Response.json({ error: "Rig did not answer. Try again." }, { status: 400 });
  }
  const op = body.op ?? "";
  if (op !== "search" && op !== "graph" && op !== "compare" && op !== "ask") {
    return Response.json({ error: "Rig did not answer. Try again." }, { status: 400 });
  }
  try {
    const result = await rigCall(op, body as Record<string, unknown>);
    return Response.json(result);
  } catch {
    return Response.json({ error: "Rig did not answer. Try again." }, { status: 502 });
  }
}
