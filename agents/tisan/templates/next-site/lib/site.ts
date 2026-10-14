export type PageLink = {
  href: string;
  label: string;
};

export const site: {
  name: string;
  locale: string;
  logoUrl: string | null;
  pages: PageLink[];
} = {
  name: "Next site",
  locale: "en",
  logoUrl: null,
  pages: [
    { href: "/", label: "Home" },
    { href: "/about", label: "About" },
    { href: "/contact", label: "Contact" },
    { href: "/privacy", label: "Privacy" },
  ],
};
