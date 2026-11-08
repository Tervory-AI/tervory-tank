import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  // Bound build workers under CI so trace collection cannot hang the check harness.
  ...(process.env.CI || process.env.NEXT_TELEMETRY_DISABLED
    ? { experimental: { cpus: 1 } }
    : {}),
};

export default nextConfig;
