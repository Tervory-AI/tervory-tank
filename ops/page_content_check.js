// One function, run inside the browser on a rendered page. Returns a list of reasons;
// an empty list means the page shows real content. Used by ops/signed_in_check.mjs
// on the live site and by tests/test_signed_in_check.py on saved HTML fixtures.
// Reads the page only: never clicks, types or submits.
(config) => {
  const reasons = [];
  const add = (reason) => { if (!reasons.includes(reason)) reasons.push(reason); };
  const visible = (el) => {
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    return el.getClientRects().length > 0;
  };
  const textOf = (el) => (el ? (el.innerText || '').replace(/\s+/g, ' ').trim() : '');
  const status = Number(config.status || 0);
  const signIn = Boolean(config.signIn);

  // 1. Server errors: the document status, failed same-site requests, and error pages.
  if (status >= 500) add(`HTTP ${status}`);
  for (const code of config.failedRequests || []) add(`A request on the page returned HTTP ${code}`);
  const body = textOf(document.body);
  const title = (document.title || '').trim();
  const serverError = /\b(50[0-9])\b[^.]{0,40}\b(service (temporarily )?unavailable|bad gateway|gateway time-?out|internal server error|server error)\b|\b(service (temporarily )?unavailable|bad gateway|gateway time-?out|internal server error)\b/i;
  const errorMatch = title.match(serverError) || body.slice(0, 2000).match(serverError);
  if (errorMatch) add(`Server error shown: ${errorMatch[0].slice(0, 60)}`);
  if (/application error|client-side exception/i.test(body)) add('Server error shown: application error');

  // 2. No sign-in provider name anywhere in sign-in text.
  const providers = /\b(zitadel|clerk|auth0|okta|keycloak|cognito|stytch|workos|next-?auth|authentik|fusionauth|supabase auth|firebase auth|ory kratos)\b/i;
  const signInText = signIn ? [title, body] : [title, ...[...document.querySelectorAll(
    'header, nav, [role="banner"], [aria-label*="account" i], [aria-label*="sign" i], [data-signin]')]
    .map(textOf)];
  for (const text of signInText) {
    const found = text.match(providers);
    if (found) add(`Sign-in text names the provider: ${found[0]}`);
  }
  const welcome = body.match(/welcome[^.!]{0,40}\badmin\b/i);
  if (welcome) add(`Sign-in text shows an admin greeting: ${welcome[0]}`);
  if (signIn) return reasons;

  // 3. The main element has real content.
  const main = document.querySelector('main, [role="main"]');
  if (!main || !visible(main)) {
    add('No main content on the page');
    return reasons;
  }
  const mainText = textOf(main);
  if (mainText.length < (config.minText || 40)) add(`Main content is nearly empty (${mainText.length} characters)`);
  const heading = main.querySelector('h1');
  if (!heading || !textOf(heading)) add('Main content has no page heading');
  for (const word of config.expect || []) {
    if (!mainText.toLowerCase().includes(String(word).toLowerCase())) add(`Missing expected text: ${word}`);
  }

  // 4. Placeholder text and error notices inside the main element.
  const placeholder = /\blorem ipsum\b|\b(TODO|TBD|FIXME)\b|\{\{[^}]*\}\}|\[object Object\]|(^|\s)(undefined|NaN)(\s|$)/;
  const shown = mainText.match(placeholder);
  if (shown) add(`Placeholder text: ${shown[0].trim()}`);
  for (const alert of main.querySelectorAll('[role="alert"]')) {
    const text = textOf(alert);
    if (text && visible(alert)) add(`Error notice: ${text.slice(0, 80)}`);
  }

  // 5. No heading with nothing under it, and no "— Support" stand-in for content.
  const controls = 'input, textarea, select, button, img, svg, canvas, table, video, iframe, picture';
  for (const h of main.querySelectorAll('h2, h3')) {
    if (!visible(h)) continue;
    const name = textOf(h);
    const box = h.closest('section, article, aside, fieldset, [role="region"]');
    let rest = '';
    let hasControl = false;
    if (box && box !== main && main.contains(box) && box.querySelector('h1, h2, h3, h4') === h) {
      rest = textOf(box).replace(name, '').trim();
      hasControl = [...box.querySelectorAll(controls)].some(visible);
    } else {
      const level = Number(h.tagName[1]);
      for (let node = h.nextElementSibling; node; node = node.nextElementSibling) {
        if (/^H[1-6]$/.test(node.tagName) && Number(node.tagName[1]) <= level) break;
        rest += ' ' + textOf(node);
        hasControl = hasControl || (node.matches(controls) || [...node.querySelectorAll(controls)].some(visible));
      }
      rest = rest.trim();
    }
    if (!rest && !hasControl) add(`Empty section: ${name}`);
    else if (/^[—–-]+(\s+\S+)?$/.test(rest)) add(`Section shows a placeholder: ${name} (${rest})`);
  }

  // 6. Page-specific parts that must not be empty (for example an answer box).
  for (const need of config.required || []) {
    const el = document.querySelector(need.selector);
    if (!el) { add(`Missing: ${need.name}`); continue; }
    const filled = textOf(el).length > 0 || el.children.length > 0;
    if (!filled) add(`Empty: ${need.name}`);
  }
  return reasons;
}
