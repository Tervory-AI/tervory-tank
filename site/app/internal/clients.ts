export const internalClients = [
  { slug: "ammosync", name: "AmmoSync" },
  { slug: "lokd-security", name: "LOKD Security" },
  { slug: "custom-nation", name: "Custom Nation" },
  { slug: "shot-bonus", name: "Shot Bonus" },
  { slug: "tngo", name: "TNGO" },
] as const;

export type InternalSlug = (typeof internalClients)[number]["slug"];
