// Names from litellm/config.yaml. The env name is how we notice a missing key.
// This module never reads or returns a key value. The page imports it on the server only.

import type { ModelRow } from "./squads";

export const MODEL_ROSTER = [
  { name: "luna", env: "OPENAI_API_KEY" },
  { name: "sol", env: "OPENAI_API_KEY" },
  { name: "astra", env: "OPENAI_API_KEY" },
  { name: "flash-lite", env: "GEMINI_API_KEY" },
  { name: "flash", env: "GEMINI_API_KEY" },
  { name: "argon", env: "GEMINI_API_KEY" },
  { name: "grok", env: "XAI_API_KEY" },
  { name: "grok-top", env: "XAI_API_KEY" },
  { name: "grok-build", env: "XAI_API_KEY" },
  { name: "haiku", env: "ANTHROPIC_API_KEY" },
  { name: "sonnet", env: "ANTHROPIC_API_KEY" },
  { name: "opus", env: "ANTHROPIC_API_KEY" },
] as const;

export function modelRows(env: Record<string, string | undefined>): ModelRow[] {
  return MODEL_ROSTER.map((model) => ({
    name: model.name,
    keyMissing: !(env[model.env] ?? "").trim(),
  }));
}
