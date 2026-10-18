import { MAIL } from "../lib/site";

export function SiteFooter() {
  return (
    <footer className="footer">
      <div className="footer-top">
        <div className="footer-brand">
          <img
            className="footer-logo"
            src="/brand/tervory-logo-reversed-display.png"
            width={167}
            height={31}
            alt="Tervory AI"
            loading="lazy"
          />
          <p>One window for the work. Every answer shows which model answered and what it cost.</p>
        </div>
        <div className="footer-columns">
          <div>
            <p className="footer-label">Product</p>
            <ul className="footer-col">
              <li>
                <a href="/#how">How it works</a>
              </li>
              <li>
                <a href="/#tank">Tank</a>
              </li>
              <li>
                <a href="/#squad">The Squad</a>
              </li>
              <li>
                <a href="/#ledger">Ledger</a>
              </li>
              <li>
                <a href="/#pricing">Pricing</a>
              </li>
            </ul>
          </div>
          <div>
            <p className="footer-label">Links</p>
            <ul className="footer-col">
              <li>
                <a href="/">tervory.com</a>
              </li>
              <li>
                <a href="https://app.tervory.com">app.tervory.com</a>
              </li>
              <li>
                <a href="/sign-up">Sign up</a>
              </li>
            </ul>
          </div>
          <div>
            <p className="footer-label">Contact</p>
            <ul className="footer-col">
              <li>
                <a href={MAIL}>hello@tervory.com (placeholder)</a>
              </li>
              <li>
                <p>Status</p>
              </li>
              <li>
                <p>Privacy · Terms</p>
              </li>
            </ul>
          </div>
        </div>
        <ul className="footer-links narrow-only">
          <li>
            <a href="/">tervory.com</a>
          </li>
          <li>
            <a href="https://app.tervory.com">app.tervory.com</a>
          </li>
          <li>
            <a href="/sign-up">Sign up</a>
          </li>
          <li>
            <a href={MAIL}>hello@tervory.com (placeholder)</a>
          </li>
          <li>
            <span>Privacy · Terms</span>
          </li>
        </ul>
      </div>
      <div className="footer-bottom">
        <p>© 2026 Tervory AI</p>
        <p className="footer-meta">Multi-tenant · each client organisation is its own isolated tenant</p>
      </div>
    </footer>
  );
}
