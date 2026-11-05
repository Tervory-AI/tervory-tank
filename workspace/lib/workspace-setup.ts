/** Configuration names only: never send setting values to a page or log. */
export const workspaceSettings = ["TANK_URL", "TANK_API_KEY", "TRIGGER_SIGNIN_WORKSPACE_SECRET"] as const;

export function missingWorkspaceSettings(env: NodeJS.ProcessEnv = process.env): string[] {
  return workspaceSettings.filter(name => !env[name]?.trim());
}

export function workspaceSetupMessage(env: NodeJS.ProcessEnv = process.env, session = true): string | null {
  const missing = missingWorkspaceSettings(env).filter(name => session || name !== "TRIGGER_SIGNIN_WORKSPACE_SECRET");
  if (missing.length) return `Workspace needs these settings: ${missing.join(", ")}.`;
  try {
    const url = new URL(env.TANK_URL!);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw Error();
  } catch { return "Workspace needs a valid TANK_URL setting."; }
  return null;
}
