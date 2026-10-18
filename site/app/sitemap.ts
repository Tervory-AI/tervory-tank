import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: "https://tervory.com/", changeFrequency: "weekly", priority: 1 },
    { url: "https://tervory.com/sign-up", changeFrequency: "monthly", priority: 0.8 },
  ];
}
