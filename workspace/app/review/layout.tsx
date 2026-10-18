import { inter, jost, mono } from "../brand-fonts";
import "../matters/matters.css";

export default function ReviewLayout({ children }: { children: React.ReactNode }) {
  return <div className={`zenas-page ${jost.variable} ${inter.variable} ${mono.variable}`}>{children}</div>;
}
