import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { studies } from "../clients";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return studies.map((study) => ({ slug: study.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const study = studies.find((item) => item.slug === slug);
  if (!study) return {};
  return {
    title: study.name,
    description: study.paragraphs[0],
    robots: { index: false, follow: false },
  };
}

export default async function InternalCaseStudy({ params }: Props) {
  const { slug } = await params;
  const study = studies.find((item) => item.slug === slug);
  if (!study) notFound();

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
      <main id="main" className="study">
        <p className="eyebrow">Case study · {study.name}</p>
        <h1>{study.headline}</h1>
        {study.paragraphs.map((paragraph) => (
          <p key={paragraph} className="lead">
            {paragraph}
          </p>
        ))}
        {study.stats ? (
          <div className="study-stats">
            {study.stats.map((stat) => (
              <article key={stat.label}>
                <p className="stat-value">{stat.value}</p>
                <p>{stat.label}</p>
              </article>
            ))}
          </div>
        ) : null}
      </main>
    </>
  );
}
