export default function ContactPage() {
  return (
    <section>
      <h1 className="font-heading text-3xl">Contact</h1>
      <form action="/api/contact" method="post" className="mt-4 grid max-w-md gap-3">
        <label htmlFor="contact-name">Name</label>
        <input
          id="contact-name"
          name="name"
          type="text"
          autoComplete="name"
          required
          className="border border-line bg-paper px-3 py-2"
        />
        <label htmlFor="contact-email">Email</label>
        <input
          id="contact-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          className="border border-line bg-paper px-3 py-2"
        />
        <label htmlFor="contact-message">Message</label>
        <textarea
          id="contact-message"
          name="message"
          required
          rows={5}
          className="border border-line bg-paper px-3 py-2"
        />
        <button type="submit" className="bg-accent px-4 py-2 text-paper">
          Send
        </button>
      </form>
    </section>
  );
}
