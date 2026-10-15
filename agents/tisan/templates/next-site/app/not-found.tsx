import Link from "next/link";

export default function NotFound() {
  return (
    <section>
      <h1 className="font-heading text-3xl">Page not found</h1>
      <p className="mt-3">
        <Link href="/">Back to the home page</Link>
      </p>
    </section>
  );
}
