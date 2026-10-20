export type StudyStat = { value: string; label: string };

export type Study = {
  slug: string;
  name: string;
  headline: string;
  paragraphs: string[];
  stats?: StudyStat[];
};

const tenantLine = (name: string) =>
  `${name} is a current tenant. It runs in its own isolated tenant.`;

export const studies: Study[] = [
  {
    slug: "ammosync",
    name: "AmmoSync",
    headline: "77,438 licensed firearms dealers. Under $15 of model spend.",
    paragraphs: [
      "AmmoSync needed the full ATF federal firearms licensee list turned into a usable contact database. A credit-based tool run over the same data returned about 800 usable records. Base went state by state through the entire list — 77,438 records across 55 states and territories, every field with a source and a confidence score — for under $15 of model spend, all of it visible in the Ledger.",
    ],
    stats: [
      { value: "77,438", label: "records enriched" },
      { value: "55", label: "states and territories" },
      { value: "< $15", label: "of model spend" },
      { value: "100%", label: "of fields with a source and confidence" },
      { value: "~800", label: "from a credit-based tool, same data" },
    ],
  },
  {
    slug: "lokd-security",
    name: "LOKD Security",
    headline: "LOKD Security",
    paragraphs: [tenantLine("LOKD Security")],
  },
  {
    slug: "custom-nation",
    name: "Custom Nation",
    headline: "Custom Nation",
    paragraphs: [tenantLine("Custom Nation")],
  },
  {
    slug: "shot-bonus",
    name: "Shot Bonus",
    headline: "Shot Bonus",
    paragraphs: [tenantLine("Shot Bonus")],
  },
  {
    slug: "tngo",
    name: "TNGO",
    headline: "TNGO",
    paragraphs: [tenantLine("TNGO")],
  },
];
