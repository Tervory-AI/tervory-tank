import { NextResponse } from "next/server";
import { route, type ChatMessage } from "@/lib/tank";
import { currentTenant } from "@/lib/tenant";
import { KEY_NAMES } from "../../../market-lab/catalog";
import { loadMarketLab, scrubSecrets } from "../../../market-lab/load";
import { groundQuestion, type AnswerSource } from "../../../market-lab/plugins";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function secretValues(): string[] {
  const values: string[] = [];
  for (const name of KEY_NAMES) {
    const value = (process.env[name] ?? "").trim();
    if (value.length >= 8) values.push(value);
  }
  return values;
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => null)) as { messages?: ChatMessage[] } | null;
  const messages =
    body?.messages?.filter((message) => message && (message.role === "user" || message.role === "assistant") && typeof message.content === "string") ??
    [];
  if (!messages.some((message) => message.role === "user" && message.content.trim())) {
    return NextResponse.json({ error: "A question is required.", sources: [] }, { status: 400 });
  }

  const secrets = secretValues();
  let sources: AnswerSource[] = [];
  let context = "No Market Lab reading matched this question. If a figure is needed, say the feed has not been read.";
  try {
    const model = await loadMarketLab();
    const last = [...messages].reverse().find((message) => message.role === "user");
    const grounded = groundQuestion(model, last?.content ?? "");
    sources = grounded.sources;
    if (grounded.context) context = grounded.context;
  } catch {
    sources = [];
  }

  const safeContext = scrubSecrets(context, secrets);
  const safeMessages = scrubSecrets(messages, secrets).slice(-12);
  const outbound = safeMessages.map((message, index) => {
    if (index !== safeMessages.length - 1 || message.role !== "user") return message;
    return {
      role: "user" as const,
      content: `${message.content}\n\nMarket Lab records you may use. Do not invent figures.\n${safeContext}`,
    };
  });

  try {
    const { tenantId } = await currentTenant();
    const result = await route(tenantId, "tier0.answer", outbound);
    return NextResponse.json({
      content: scrubSecrets(result.content, secrets),
      sources: scrubSecrets(sources, secrets),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Tank unavailable";
    return NextResponse.json({ error: scrubSecrets(message, secrets), sources: [] }, { status: 502 });
  }
}
