import localFont from "next/font/local";

// Latin files in ./fonts. next/font/google downloads CSS during `next build`.
// Google sometimes returns a font URL with no file extension, and the loader
// then crashes (vercel/next.js#99114). That failed the Workspace check.
// Paths must be written as literals; the font loader does not accept variables.

export const jost = localFont({
  src: "./fonts/jost-latin-300.woff2",
  weight: "300",
  display: "swap",
  variable: "--font-jost",
});

export const inter = localFont({
  src: "./fonts/inter-latin.woff2",
  weight: "100 900",
  display: "swap",
  variable: "--font-inter",
});

export const mono = localFont({
  src: "./fonts/jetbrains-mono-latin.woff2",
  weight: "400 800",
  display: "swap",
  variable: "--font-mono",
});

export const onbBody = localFont({
  src: "./fonts/inter-latin.woff2",
  weight: "100 900",
  variable: "--onb-body",
});

export const onbHeading = localFont({
  src: "./fonts/jost-latin-300.woff2",
  weight: "300",
  variable: "--onb-heading",
});

export const onbMono = localFont({
  src: "./fonts/jetbrains-mono-latin.woff2",
  weight: "400 800",
  variable: "--onb-mono",
});
