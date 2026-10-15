import { site } from "@/lib/site";

export default function AboutPage() {
  return (
    <section>
      <h1 className="font-heading text-3xl">About</h1>
      <p className="mt-3">{site.name} publishes this site.</p>
    </section>
  );
}
