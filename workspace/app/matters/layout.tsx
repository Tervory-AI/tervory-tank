import { Inter, JetBrains_Mono, Jost } from "next/font/google";
import "./matters.css";

const jost = Jost({ subsets: ["latin"], weight: "300", variable: "--font-jost", display: "swap" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono", display: "swap" });

export default function MattersLayout({ children }: { children: React.ReactNode }) {
  return <div className={`zenas-page ${jost.variable} ${inter.variable} ${mono.variable}`}>{children}</div>;
}
