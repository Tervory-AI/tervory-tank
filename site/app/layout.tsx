import type { Metadata } from "next";
import "./fonts.css";
import "./globals.css";
import { homeDescription, homeTitle } from "../lib/site";

export const metadata: Metadata = {
  metadataBase: new URL("https://tervory.com"),
  title: homeTitle,
  description: homeDescription,
  openGraph: {
    title: homeTitle,
    description: homeDescription,
    images: [{ url: "/og.png", width: 1200, height: 630 }],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preload" href="/fonts/9dd75fadc5b3df29-s.p.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
        <link rel="preload" href="/fonts/e4af272ccee01ff0-s.p.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
        <link rel="preload" href="/fonts/427e4a37d3642943-s.p.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  );
}
