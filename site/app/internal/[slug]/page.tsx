import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { internalClients } from "../clients";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return internalClients.map((client) => ({ slug: client.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const client = internalClients.find((item) => item.slug === slug);
  if (!client) return {};
  return {
    title: client.name,
    description: "Internal page. Not published.",
    robots: { index: false, follow: false },
  };
}

export default async function InternalCaseStudy({ params }: Props) {
  const { slug } = await params;
  const client = internalClients.find((item) => item.slug === slug);
  if (!client) notFound();

  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="internal-bar">
        <a href="/">
          <img className="logo" src="/brand/tervory-logo-display.png" width={186} height={34} alt="Tervory AI" />
        </a>
      </header>
      <main id="main" className="internal">
        <p className="eyebrow">Internal</p>
        <h1>{client.name}</h1>
        <p className="lead">This page is not published. It is not linked from the public site.</p>
      </main>
    </>
  );
}
