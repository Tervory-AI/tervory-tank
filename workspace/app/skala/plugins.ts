export const VAULT_OFF_MESSAGE = "This vault is off. Turn it on in Tank.";
export const LIBRARY_OFF_MESSAGE = "The skills library is off. Nothing can be linked or transferred.";
export const PLUGIN_TABS = ["API keys", "Files", "Source links", "MCP connections"] as const;
export type PluginTab = (typeof PLUGIN_TABS)[number];

export const STUB_KEY = "Add a key first. Nothing was stored.";
export const STUB_FILE = "Choose a file first. Nothing was saved.";
export const STUB_LINK = "Add a link first. Nothing was saved.";
export const STUB_MCP = "Add a name and a server URL first. Nothing was saved.";

export type SecretMeta = { name: string; purpose: string; mask: string; savedAt: string | null };
export type FileMeta = {
  id: string;
  name: string;
  type: string;
  size: number;
  rows: number | null;
  pages: number | null;
  uploadedAt: string;
  status: string;
};
export type LinkMeta = {
  id: string;
  url: string;
  label: string;
  frequency: string;
  lastChecked: string | null;
  status: string;
};
export type ConnectionMeta = {
  id: string;
  name: string;
  serverUrl: string;
  authType: string;
  status: string;
  lastUsed: string | null;
  hasToken: boolean;
};
export type PluginPanel = {
  enabled: boolean;
  message: string | null;
  secrets: SecretMeta[];
  files: FileMeta[];
  links: LinkMeta[];
  connections: ConnectionMeta[];
};

export type LibrarySkill = {
  skill_id: string;
  version: string;
  agent: string;
  description: string;
};

export type LibraryPanel = {
  enabled: boolean;
  message: string;
  skills: LibrarySkill[];
};

export function offPanel(message: string = VAULT_OFF_MESSAGE): PluginPanel {
  return { enabled: false, message, secrets: [], files: [], links: [], connections: [] };
}

export function offLibrary(message: string = LIBRARY_OFF_MESSAGE): LibraryPanel {
  return { enabled: false, message, skills: [] };
}

type WireSecret = { name?: string; purpose?: string; mask?: string; saved_at?: string; value?: string };
type WireFile = { id?: string; name?: string; type?: string; size?: number; rows?: number | null; pages?: number | null; uploaded_at?: string; status?: string; content?: string };
type WireLink = { id?: string; url?: string; label?: string; frequency?: string; last_checked?: string | null; status?: string };
type WireConnection = { id?: string; name?: string; server_url?: string; auth_type?: string; status?: string; last_used?: string | null; has_token?: boolean; token?: string };

/** Copy the fields the browser may see. Secret values and file bytes are dropped. */
export function mapVaultPayload(raw: {
  enabled?: boolean;
  message?: string | null;
  secrets?: WireSecret[];
  files?: WireFile[];
  links?: WireLink[];
  connections?: WireConnection[];
}): PluginPanel {
  if (!raw.enabled) return offPanel(raw.message || VAULT_OFF_MESSAGE);
  return {
    enabled: true,
    message: null,
    secrets: (raw.secrets ?? []).flatMap((row) =>
      row.name ? [{ name: row.name, purpose: row.purpose ?? "", mask: row.mask || "••••••••", savedAt: row.saved_at ?? null }] : [],
    ),
    files: (raw.files ?? []).flatMap((row) =>
      row.id && row.name
        ? [{
            id: row.id,
            name: row.name,
            type: row.type ?? "",
            size: row.size ?? 0,
            rows: row.rows ?? null,
            pages: row.pages ?? null,
            uploadedAt: row.uploaded_at ?? "",
            status: row.status ?? "ready",
          }]
        : [],
    ),
    links: (raw.links ?? []).flatMap((row) =>
      row.id && row.url
        ? [{
            id: row.id,
            url: row.url,
            label: row.label ?? row.url,
            frequency: row.frequency ?? "weekly",
            lastChecked: row.last_checked ?? null,
            status: row.status ?? "not checked",
          }]
        : [],
    ),
    connections: (raw.connections ?? []).flatMap((row) =>
      row.id && row.name
        ? [{
            id: row.id,
            name: row.name,
            serverUrl: row.server_url ?? "",
            authType: row.auth_type ?? "provider",
            status: row.status ?? "saved",
            lastUsed: row.last_used ?? null,
            hasToken: Boolean(row.has_token),
          }]
        : [],
    ),
  };
}

export function mapLibraryPayload(raw: {
  enabled?: boolean;
  message?: string | null;
  skills?: { skill_id?: string; version?: string; agent?: string; description?: string; value?: string }[];
}): LibraryPanel {
  if (!raw.enabled) return offLibrary();
  return {
    enabled: true,
    message: "",
    skills: (raw.skills ?? []).flatMap((row) =>
      row.skill_id && row.version
        ? [{ skill_id: row.skill_id, version: row.version, agent: row.agent ?? "", description: row.description ?? "" }]
        : [],
    ),
  };
}
