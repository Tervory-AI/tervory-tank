import { site } from "@/lib/site";

export default function HomePage() {
  return (
    <section>
      <h1 className="font-heading text-3xl">{site.name}</h1>
      <p className="mt-3">Welcome.</p>
    </section>
  );
}
